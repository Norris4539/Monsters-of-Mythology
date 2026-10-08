'use strict';
// ─────────────────────────────────────────────────────────────────────────────
// Tactical battles — a Fire Emblem Awakening style grid fight.
//
//   startBattle(opt) → Promise<{ win, retreat, rout }>
//
// opt = {
//   title, theme: BTHEMES key, siege: 'enemy' | 'player' | null (who has walls),
//   player: { units, lead, hero, power: { kind, name, desc } | null, powerUses },
//   enemy:  { units, lead, hero },
// }
// Unit objects are the persistent army units, so HP/XP/deaths carry back to the
// adventure map automatically.
// ─────────────────────────────────────────────────────────────────────────────

const BW = 15, BH = 10, BT = 48;
const SIDE_COLOR = { p: '#2f6fd6', e: '#c43c3c' };

let B = null; // the active battle

function startBattle(opt) {
  return new Promise(resolve => {
    B = {
      opt, resolve, turn: 1, phase: 'p', mode: 'idle', busy: false,
      map: genBattleMap(opt.theme, opt.siege), units: [], floats: [],
      sel: null, orig: null, reach: null, targets: [], target: null, hover: null,
      danger: new Set(), showDanger: false, powerUses: opt.player.powerUses || 0, log: [],
      raf: 0, menuEl: null,
    };
    deploy('p', opt.player);
    deploy('e', opt.enemy);
    showScreen('battle');
    buildBattleUI();
    loop();
    banner('Player Phase', SIDE_COLOR.p);
    blog(`⚔️ ${opt.title}`);
    refreshSide();
  });
}

// ── Map generation ──────────────────────────────────────────────────────────
function genBattleMap(theme, siege) {
  const TH = BTHEMES[theme] || BTHEMES.grass;
  for (let tries = 0; tries < 40; tries++) {
    const t = Array(BW * BH).fill('plain');
    const clusters = rint(5, 9);
    for (let i = 0; i < clusters; i++) {
      const f = pick(TH.mix);
      let x = rint(3, BW - 4), y = rint(0, BH - 1);
      for (let k = rint(1, 5); k > 0; k--) {
        t[y * BW + x] = f;
        if (chance(50)) x = clamp(x + pick([-1, 1]), 3, BW - 4); else y = clamp(y + pick([-1, 1]), 0, BH - 1);
      }
    }
    if (chance(60)) t[rint(1, BH - 2) * BW + rint(5, 9)] = 'fort';
    if (siege) {
      const wx = siege === 'enemy' ? BW - 5 : 4, fx = siege === 'enemy' ? BW - 2 : 1;
      for (let y = 0; y < BH; y++) t[y * BW + wx] = 'wall';
      t[3 * BW + wx] = 'gate'; t[6 * BW + wx] = 'gate';
      for (let y = 0; y < BH; y++) for (const dx of [-1, 1]) if (t[y * BW + wx + dx] === 'water') t[y * BW + wx + dx] = 'plain';
      t[2 * BW + fx] = 'fort'; t[7 * BW + fx] = 'fort';
    }
    for (let y = 0; y < BH; y++) for (const x of [0, 1, BW - 2, BW - 1]) {
      const i = y * BW + x; if (t[i] !== 'fort') t[i] = 'plain';
    }
    if (battleConnected(t, 'foot') && battleConnected(t, 'horse')) return t;
  }
  return Array(BW * BH).fill('plain');
}
function battleConnected(t, mv) {
  const seen = new Uint8Array(BW * BH), q = [Math.floor(BH / 2) * BW];
  seen[q[0]] = 1;
  while (q.length) {
    const i = q.pop(), x = i % BW, y = (i / BW) | 0;
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nx = x + dx, ny = y + dy, j = ny * BW + nx;
      if (nx < 0 || ny < 0 || nx >= BW || ny >= BH || seen[j] || BTER[t[j]].cost[mv] >= 99) continue;
      seen[j] = 1; q.push(j);
    }
  }
  return !!seen[Math.floor(BH / 2) * BW + BW - 1];
}

function deploy(side, army) {
  const enemyWalls = side === 'e' && B.opt.siege === 'enemy';
  const cols = side === 'p' ? [1, 0, 2] : enemyWalls ? [BW - 3, BW - 2, BW - 4, BW - 1] : [BW - 2, BW - 1, BW - 3];
  const rows = [4, 5, 3, 6, 2, 7, 1, 8, 0, 9];
  const cells = [];
  for (const x of cols) for (const y of rows) if (BTER[B.map[y * BW + x]].cost.foot < 99) cells.push([x, y]);
  const ranged = u => { const T = UNITS[u.type]; return T.weapon === 'staff' || T.range[0] > 1; };
  const list = army.units.filter(u => u.hp > 0);
  const front = list.filter(u => !ranged(u)), back = list.filter(ranged);
  const order = [...front, ...back];
  if (army.lead) order.splice(Math.min(order.length, front.length), 0, army.lead);
  order.forEach((u, i) => {
    const [x, y] = cells[i % cells.length];
    u.bonus = armyBonus(army.hero, u === army.lead);
    u.hp = maxHp(u);
    B.units.push({ u, T: UNITS[u.type], side, x, y, px: x * BT, py: y * BT, ox: 0, oy: 0, acted: false, alive: true, lead: u === army.lead, alpha: 1, flash: 0 });
  });
}

// ── Queries ─────────────────────────────────────────────────────────────────
const bIdx = (x, y) => y * BW + x;
const inB = (x, y) => x >= 0 && y >= 0 && x < BW && y < BH;
const bTerr = (x, y) => BTER[B.map[bIdx(x, y)]];
const unitAt = (x, y) => B.units.find(c => c.alive && c.x === x && c.y === y);
const alive = side => B.units.filter(c => c.alive && c.side === side);
const foes = c => B.units.filter(o => o.alive && o.side !== c.side);
const N4 = [[1, 0], [-1, 0], [0, 1], [0, -1]];
const combatCtx = {
  terr: (x, y) => bTerr(x, y),
  support: (c, x, y) => B.units.some(o => o.alive && o !== c && o.side === c.side && manh(o.x, o.y, x, y) === 1),
};

// Dijkstra over the grid for c's movement. Allies can be passed through.
function reachOf(c, limit = st(c.u, 'mov')) {
  const dist = new Map([[bIdx(c.x, c.y), 0]]), prev = new Map(), h = new Heap();
  h.push(bIdx(c.x, c.y), 0);
  while (h.size) {
    const i = h.pop(), x = i % BW, y = (i / BW) | 0, d = dist.get(i);
    for (const [dx, dy] of N4) {
      const nx = x + dx, ny = y + dy;
      if (!inB(nx, ny)) continue;
      const o = unitAt(nx, ny);
      if (o && o.side !== c.side) continue;
      const nd = d + bTerr(nx, ny).cost[c.T.move];
      const j = bIdx(nx, ny);
      if (nd > limit || nd >= (dist.get(j) ?? 1e9)) continue;
      dist.set(j, nd); prev.set(j, i); h.push(j, nd);
    }
  }
  return { dist, prev };
}
const standable = (c, i) => { const o = unitAt(i % BW, (i / BW) | 0); return !o || o === c; };
function tilesInRange(x, y, [lo, hi]) {
  const out = [];
  for (let dy = -hi; dy <= hi; dy++) for (let dx = -hi; dx <= hi; dx++) {
    const d = Math.abs(dx) + Math.abs(dy);
    if (d >= lo && d <= hi && inB(x + dx, y + dy)) out.push(bIdx(x + dx, y + dy));
  }
  return out;
}
function threatTiles(c) {
  const out = new Set();
  if (c.T.weapon === 'staff') return out;
  for (const [i] of reachOf(c).dist) if (standable(c, i)) for (const j of tilesInRange(i % BW, (i / BW) | 0, c.T.range)) out.add(j);
  return out;
}
const attackTargetsFrom = (c, x, y) => c.T.weapon === 'staff' ? [] : foes(c).filter(o => canAttackAt(c.T, manh(x, y, o.x, o.y)));
const healTargetsFrom = (c, x, y) => !c.T.abil.includes('heal') ? [] :
  B.units.filter(o => o.alive && o !== c && o.side === c.side && manh(x, y, o.x, o.y) === 1 && o.u.hp < maxHp(o.u));

// ── Rendering ───────────────────────────────────────────────────────────────
function loop() {
  if (!B) return;
  drawBattle();
  B.raf = requestAnimationFrame(loop);
}
function drawBattle() {
  const cv = document.getElementById('bcanvas'), g = cv.getContext('2d');
  const TH = BTHEMES[B.opt.theme] || BTHEMES.grass;
  g.clearRect(0, 0, cv.width, cv.height);
  g.textAlign = 'center'; g.textBaseline = 'middle';
  for (let y = 0; y < BH; y++) for (let x = 0; x < BW; x++) {
    const t = B.map[bIdx(x, y)], X = x * BT, Y = y * BT;
    g.fillStyle = (x + y) % 2 ? TH.alt : TH.plain;
    if (t === 'water') g.fillStyle = (x + y) % 2 ? '#4579b3' : '#4a7fba';
    if (t === 'wall') g.fillStyle = '#6b6560';
    if (t === 'gate') g.fillStyle = '#8a6a44';
    if (t === 'dune') g.fillStyle = '#cfb36e';
    g.fillRect(X, Y, BT, BT);
    if (t === 'wall') { g.fillStyle = '#58524d'; for (let k = 0; k < 3; k++) g.fillRect(X + 2, Y + 4 + k * 15, BT - 4, 3); }
    if (t === 'water') { g.strokeStyle = 'rgba(255,255,255,.25)'; g.beginPath(); g.moveTo(X + 8, Y + 20); g.quadraticCurveTo(X + 16, Y + 14, X + 24, Y + 20); g.stroke(); }
    if (t === 'dune') { g.strokeStyle = 'rgba(120,90,40,.35)'; g.beginPath(); g.arc(X + 24, Y + 40, 18, Math.PI * 1.15, Math.PI * 1.85); g.stroke(); }
    const icon = TH.feats[t] ?? (t === 'gate' ? '🚪' : null);
    if (icon) { g.font = '30px serif'; g.globalAlpha = 0.95; g.fillText(icon, X + BT / 2, Y + BT / 2 + 2); g.globalAlpha = 1; }
  }
  // grid
  g.strokeStyle = 'rgba(0,0,0,.12)'; g.lineWidth = 1;
  for (let x = 0; x <= BW; x++) { g.beginPath(); g.moveTo(x * BT + .5, 0); g.lineTo(x * BT + .5, BH * BT); g.stroke(); }
  for (let y = 0; y <= BH; y++) { g.beginPath(); g.moveTo(0, y * BT + .5); g.lineTo(BW * BT, y * BT + .5); g.stroke(); }

  const tint = (i, col) => { g.fillStyle = col; g.fillRect((i % BW) * BT + 1, ((i / BW) | 0) * BT + 1, BT - 2, BT - 2); };
  if (B.showDanger) for (const i of B.danger) tint(i, 'rgba(200,40,140,.22)');
  if (B.mode === 'selected' && B.reach) {
    const atk = new Set();
    for (const [i] of B.reach.dist) if (standable(B.sel, i)) {
      tint(i, 'rgba(60,120,255,.38)');
      if (B.sel.T.weapon !== 'staff') for (const j of tilesInRange(i % BW, (i / BW) | 0, B.sel.T.range)) atk.add(j);
      else for (const j of tilesInRange(i % BW, (i / BW) | 0, [1, 1])) atk.add(j);
    }
    for (const j of atk) if (!B.reach.dist.has(j) || !standable(B.sel, j)) tint(j, B.sel.T.weapon === 'staff' ? 'rgba(60,200,90,.30)' : 'rgba(230,50,50,.30)');
  }
  if (B.mode === 'enemyRange' && B.inspect) for (const i of B.inspect.tiles) tint(i, 'rgba(230,50,50,.30)');
  if (B.mode === 'target' || B.mode === 'heal' || B.mode === 'power') {
    for (const c of B.targets) tint(bIdx(c.x, c.y), B.mode === 'heal' ? 'rgba(60,200,90,.45)' : 'rgba(230,50,50,.45)');
  }
  if (B.hover && inB(B.hover.x, B.hover.y)) {
    g.strokeStyle = '#ffe27a'; g.lineWidth = 3;
    g.strokeRect(B.hover.x * BT + 2, B.hover.y * BT + 2, BT - 4, BT - 4);
  }
  // units
  for (const c of B.units) {
    if (!c.alive && c.alpha <= 0) continue;
    const X = c.px + c.ox + BT / 2, Y = c.py + c.oy + BT / 2;
    g.globalAlpha = c.alpha;
    g.beginPath(); g.arc(X, Y, 19, 0, Math.PI * 2);
    g.fillStyle = c.acted && B.phase === c.side ? '#6d6d6d' : SIDE_COLOR[c.side];
    g.fill();
    g.lineWidth = c.lead ? 3 : 2; g.strokeStyle = c.lead ? '#ffd24a' : 'rgba(0,0,0,.45)'; g.stroke();
    if (c === B.sel) { g.strokeStyle = '#fff'; g.lineWidth = 2; g.beginPath(); g.arc(X, Y, 22, 0, Math.PI * 2); g.stroke(); }
    g.font = '22px serif'; g.fillStyle = '#fff';
    g.fillText(c.T.icon, X, Y + 1);
    if (c.flash > 0) { g.fillStyle = `rgba(255,255,255,${c.flash})`; g.beginPath(); g.arc(X, Y, 19, 0, Math.PI * 2); g.fill(); c.flash = Math.max(0, c.flash - 0.08); }
    // HP bar
    const w = 34, frac = clamp(c.u.hp / maxHp(c.u), 0, 1);
    g.fillStyle = 'rgba(0,0,0,.6)'; g.fillRect(X - w / 2, Y + 15, w, 5);
    g.fillStyle = frac > .5 ? '#5fd35f' : frac > .25 ? '#e8c440' : '#e85040';
    g.fillRect(X - w / 2 + 1, Y + 16, (w - 2) * frac, 3);
    if (c.lead) { g.font = '12px serif'; g.fillText('⭐', X + 15, Y - 15); }
    g.globalAlpha = 1;
  }
  // floating combat text
  const now = performance.now();
  B.floats = B.floats.filter(f => now - f.t0 < f.dur);
  for (const f of B.floats) {
    const k = (now - f.t0) / f.dur;
    g.globalAlpha = 1 - k * k;
    g.font = `bold ${f.size || 18}px system-ui, sans-serif`;
    g.lineWidth = 4; g.strokeStyle = 'rgba(0,0,0,.75)';
    g.strokeText(f.text, f.x, f.y - k * 26); g.fillStyle = f.color; g.fillText(f.text, f.x, f.y - k * 26);
    g.globalAlpha = 1;
  }
}
function floatText(c, text, color = '#fff', size = 18, dur = 1100) {
  B.floats.push({ x: c.px + BT / 2, y: c.py + 4, text, color, size, dur, t0: performance.now() });
}

async function tween(ms, fn) {
  const t0 = performance.now();
  return new Promise(res => {
    const step = () => {
      const k = Math.min(1, (performance.now() - t0) / ms);
      fn(k);
      if (k < 1) requestAnimationFrame(step); else res();
    };
    step();
  });
}
async function animMove(c, path) {
  for (const i of path) {
    const sx = c.px, sy = c.py, tx = (i % BW) * BT, ty = ((i / BW) | 0) * BT;
    await tween(70, k => { c.px = sx + (tx - sx) * k; c.py = sy + (ty - sy) * k; });
  }
}
function pathTo(reach, start, goal) {
  const path = []; let i = goal;
  while (i !== start && i !== undefined) { path.unshift(i); i = reach.prev.get(i); }
  return path;
}
async function moveUnit(c, x, y) {
  const goal = bIdx(x, y);
  if (goal === bIdx(c.x, c.y)) return;
  const r = reachOf(c, 999);
  const path = pathTo(r, bIdx(c.x, c.y), goal);
  c.x = x; c.y = y;
  await animMove(c, path);
  c.px = x * BT; c.py = y * BT;
}

// ── Combat resolution ───────────────────────────────────────────────────────
const powerLevel = u => u.lvl + (UNITS[u.type].tier || 4) * 2;

function forecast(a, d) {
  const dist = manh(a.x, a.y, d.x, d.y);
  const fa = strikeStats(a, d, a.x, a.y, d.x, d.y, combatCtx);
  const fd = canAttackAt(d.T, dist) ? strikeStats(d, a, d.x, d.y, a.x, a.y, combatCtx) : null;
  return { fa, fd };
}

async function strike(s, t, f, label) {
  if (!s.alive || !t.alive) return;
  const dx = Math.sign(t.x - s.x) * 10, dy = Math.sign(t.y - s.y) * 10;
  await tween(110, k => { s.ox = dx * k; s.oy = dy * k; });
  const hit = chance(f.hit);
  if (label) floatText(s, label, '#ffe27a', 14, 900);
  if (!hit) {
    floatText(t, 'Miss', '#cfd8e3');
  } else {
    const crit = chance(f.crit);
    const dmg = f.dmg * (crit ? 3 : 1);
    t.u.hp = Math.max(0, t.u.hp - dmg);
    t.flash = 0.8;
    floatText(t, crit ? `${dmg}!` : `${dmg}`, crit ? '#ffcf3a' : '#ff6a5a', crit ? 24 : 19);
    if (crit) floatText(s, 'Critical!', '#ffcf3a', 15, 900);
    s.dealt = (s.dealt || 0) + dmg;
    if (s.T.abil.includes('lifesteal') && dmg > 0) {
      const heal = Math.min(Math.ceil(dmg / 2), maxHp(s.u) - s.u.hp);
      if (heal > 0) { s.u.hp += heal; floatText(s, `+${heal}`, '#7cf07c', 15); }
    }
  }
  await tween(110, k => { s.ox = dx * (1 - k); s.oy = dy * (1 - k); });
  s.ox = s.oy = 0;
  if (t.u.hp <= 0) await killUnit(t, s);
  await sleep(120);
}
async function killUnit(c, killer) {
  c.alive = false;
  blog(`${c.side === 'p' ? '💀' : '☠️'} ${c.T.name}${c.lead ? ' (commander)' : ''} has fallen.`);
  if (killer) killer.kills = (killer.kills || []).concat(c);
  await tween(380, k => { c.alpha = 1 - k; });
}

async function doCombat(a, d) {
  B.busy = true;
  const { fa, fd } = forecast(a, d);
  const aN = fa.brave ? 2 : 1, dN = fd && fd.brave ? 2 : 1;
  a.dealt = d.dealt = 0; a.kills = d.kills = [];
  blog(`${a.T.name} attacks ${d.T.name}.`);
  for (let i = 0; i < aN; i++) await strike(a, d, fa);
  // Dual Strike: an adjacent ally may join in.
  if (a.alive && d.alive) {
    const partner = B.units.find(o => o.alive && o !== a && o.side === a.side && o.T.weapon !== 'staff' && manh(o.x, o.y, a.x, a.y) === 1);
    if (partner && chance(25 + Math.floor(st(partner.u, 'skl') / 2))) {
      const fp = strikeStats(partner, d, partner.x, partner.y, d.x, d.y, combatCtx);
      partner.dealt = 0; partner.kills = [];
      await strike(partner, d, fp, 'Dual Strike!');
      if (partner.side === 'p') awardXp(partner, d);
    }
  }
  if (fd) for (let i = 0; i < dN; i++) await strike(d, a, fd);
  if (fa.doubles) for (let i = 0; i < aN; i++) await strike(a, d, fa);
  if (fd && fd.doubles) for (let i = 0; i < dN; i++) await strike(d, a, fd);
  for (const c of [a, d]) if (c.side === 'p' && c.alive) awardXp(c, c === a ? d : a);
  B.busy = false;
}
function awardXp(c, foe) {
  const diff = powerLevel(foe.u) - powerLevel(c.u);
  let xp = c.dealt > 0 ? clamp(10 + diff * 2, 2, 40) : 1;
  if (c.kills && c.kills.length) xp += clamp(25 + diff * 3, 8, 80);
  applyXp(c, xp);
}
function applyXp(c, xp) {
  const ups = gainXp(c.u, xp);
  for (const g of ups) {
    floatText(c, 'LEVEL UP!', '#7fd4ff', 16, 1500);
    const txt = Object.keys(g).map(s => `${STAT_NAMES[s]}+1`).join(' ');
    blog(`⬆️ ${c.T.name} reached level ${c.u.lvl}: ${txt}`);
    toast(`${c.T.icon} ${c.T.name} → Lv ${c.u.lvl}<br><small>${txt}</small>`);
  }
}
async function doHeal(h, t) {
  B.busy = true;
  const amt = Math.min(st(h.u, 'mag') + 10, maxHp(t.u) - t.u.hp);
  await tween(150, k => { h.oy = -6 * Math.sin(k * Math.PI); });
  t.u.hp += amt;
  floatText(t, `+${amt}`, '#7cf07c', 20);
  blog(`${h.T.name} heals ${t.T.name} for ${amt}.`);
  if (h.side === 'p') applyXp(h, 12);
  await sleep(250);
  B.busy = false;
}

// God powers — the hero's patron deity intervenes once (twice with a Temple).
async function usePower(target) {
  const P = B.opt.player.power, en = alive('e');
  B.busy = true; B.powerUses--;
  blog(`✨ ${P.name}!`);
  const flashAll = list => list.forEach(c => { c.flash = 1; });
  const hurt = async (c, dmg) => {
    c.u.hp = Math.max(0, c.u.hp - dmg); c.flash = 1;
    floatText(c, `${dmg}`, '#ffd84a', 22);
    if (c.u.hp <= 0) await killUnit(c, null);
  };
  if (P.kind === 'bolt') await hurt(target, 20);
  if (P.kind === 'hammer') {
    await hurt(target, 14);
    for (const o of en) if (o !== target && o.alive && manh(o.x, o.y, target.x, target.y) === 1) await hurt(o, 7);
  }
  if (P.kind === 'flare') { flashAll(en); for (const o of en) await hurt(o, 8); }
  if (P.kind === 'dawn') for (const o of alive('p')) { const amt = maxHp(o.u) - o.u.hp; o.u.hp = maxHp(o.u); o.flash = 1; if (amt) floatText(o, `+${amt}`, '#7cf07c', 20); }
  await sleep(500);
  B.busy = false;
}

// ── Player input ────────────────────────────────────────────────────────────
function bTileFromEvent(e) {
  const cv = document.getElementById('bcanvas'), r = cv.getBoundingClientRect();
  return { x: Math.floor((e.clientX - r.left) / r.width * BW), y: Math.floor((e.clientY - r.top) / r.height * BH) };
}
function select(c) {
  B.sel = c; B.mode = 'selected'; B.orig = { x: c.x, y: c.y }; B.reach = reachOf(c); B.target = null;
  hideMenu(); refreshSide();
}
function deselect() {
  B.sel = null; B.mode = 'idle'; B.reach = null; B.targets = []; B.target = null;
  hideMenu(); refreshSide();
}
function bestAttackTile(c, foe) {
  let best = null, bestScore = -1e9;
  for (const [i] of B.reach.dist) {
    if (!standable(c, i)) continue;
    const x = i % BW, y = (i / BW) | 0;
    if (!canAttackAt(c.T, manh(x, y, foe.x, foe.y))) continue;
    const t = bTerr(x, y);
    const score = (i === bIdx(c.x, c.y) ? 50 : 0) + t.avo + t.def * 10 - B.reach.dist.get(i);
    if (score > bestScore) { bestScore = score; best = { x, y }; }
  }
  return best;
}

async function onBattleClick(e) {
  if (!B || B.busy || B.phase !== 'p') return;
  const { x, y } = bTileFromEvent(e);
  if (!inB(x, y)) return;
  const c = unitAt(x, y), i = bIdx(x, y);
  switch (B.mode) {
    case 'idle':
    case 'enemyRange':
      if (c && c.side === 'p' && !c.acted) select(c);
      else if (c && c.side === 'e') { B.mode = 'enemyRange'; B.inspect = { c, tiles: threatTiles(c) }; refreshSide(); }
      else { B.mode = 'idle'; refreshSide(); }
      break;
    case 'selected': {
      const s = B.sel;
      if (c === s) { openMenu(); }
      else if (c && c.side === 'p' && !c.acted) select(c);
      else if (c && c.side === 'e') {
        const t = bestAttackTile(s, c);
        if (!t) { B.mode = 'enemyRange'; B.inspect = { c, tiles: threatTiles(c) }; B.sel = null; refreshSide(); break; }
        B.busy = true; await moveUnit(s, t.x, t.y); B.busy = false;
        B.targets = attackTargetsFrom(s, s.x, s.y); B.mode = 'target'; showForecast(c);
      } else if (c && c.side === 'p' && c.acted && s.T.abil.includes('heal')) {
        deselect();
      } else if (B.reach.dist.has(i) && standable(s, i)) {
        B.busy = true; await moveUnit(s, x, y); B.busy = false;
        openMenu();
      } else deselect();
      break;
    }
    case 'target':
      if (c && B.targets.includes(c)) {
        if (B.target === c) await confirmAttack(); else showForecast(c);
      }
      break;
    case 'heal':
      if (c && B.targets.includes(c)) { hideMenu(); await doHeal(B.sel, c); finishUnit(B.sel); }
      break;
    case 'power':
      if (c && B.targets.includes(c)) { B.mode = 'idle'; B.targets = []; await usePower(c); afterAction(); }
      break;
  }
}
function onBattleHover(e) {
  if (!B) return;
  const t = bTileFromEvent(e);
  if (!B.hover || B.hover.x !== t.x || B.hover.y !== t.y) { B.hover = t; refreshInfo(); }
}
function cancelBattle() {
  if (!B || B.busy || B.phase !== 'p') return;
  if (B.mode === 'target' || B.mode === 'heal') { B.target = null; openMenu(); }
  else if (B.mode === 'menu') {
    const s = B.sel; s.x = B.orig.x; s.y = B.orig.y; s.px = s.x * BT; s.py = s.y * BT;
    select(s);
  } else if (B.mode === 'power') { B.mode = 'idle'; B.targets = []; refreshSide(); }
  else deselect();
}

function openMenu() {
  const s = B.sel;
  B.mode = 'menu'; B.reach = null; B.targets = []; B.target = null;
  const items = [];
  const atk = attackTargetsFrom(s, s.x, s.y), heal = healTargetsFrom(s, s.x, s.y);
  if (atk.length) items.push(['⚔️ Attack', () => { B.mode = 'target'; B.targets = atk; hideMenu(); refreshSide(); if (atk.length === 1) showForecast(atk[0]); }]);
  if (heal.length) items.push(['✚ Heal', () => { B.mode = 'heal'; B.targets = heal; hideMenu(); refreshSide(); }]);
  items.push(['⏸ Wait', () => { hideMenu(); finishUnit(s); }]);
  items.push(['↩ Cancel', () => cancelBattle()]);
  showMenu(s, items);
  refreshSide();
}
function showMenu(c, items) {
  hideMenu();
  const wrap = document.getElementById('bwrap'), cv = document.getElementById('bcanvas');
  const r = cv.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
  const sx = r.width / (BW * BT);
  const m = el('div', { className: 'bmenu' }, items.map(([label, fn]) => el('button', { onClick: ev => { ev.stopPropagation(); fn(); } }, label)));
  const left = (c.x + 1) * BT * sx + (r.left - wr.left) + 6, top = c.y * BT * sx + (r.top - wr.top);
  m.style.left = `${Math.min(left, wr.width - 130)}px`;
  m.style.top = `${Math.max(0, Math.min(top, wr.height - items.length * 38 - 8))}px`;
  wrap.append(m); B.menuEl = m;
}
function hideMenu() { if (B && B.menuEl) { B.menuEl.remove(); B.menuEl = null; } }

function showForecast(foe) { B.target = foe; refreshSide(); }
async function confirmAttack() {
  const s = B.sel, foe = B.target;
  B.targets = []; B.target = null; B.mode = 'busy';
  hideMenu(); refreshSide();
  await doCombat(s, foe);
  if (s.alive) finishUnit(s); else { B.sel = null; afterAction(); }
}
function finishUnit(c) {
  c.acted = true; B.sel = null; B.mode = 'idle'; B.reach = null; B.targets = [];
  afterAction();
}
function afterAction() {
  refreshSide();
  if (checkEnd()) return;
  if (alive('p').every(c => c.acted)) endPlayerPhase();
}
async function endPlayerPhase() {
  if (B.phase !== 'p' || B.busy) return;
  hideMenu();
  B.phase = 'e'; B.mode = 'busy'; B.sel = null; B.showDanger = false;
  refreshSide();
  await banner('Enemy Phase', SIDE_COLOR.e);
  await startOfTurn('e');
  if (checkEnd()) return;
  await enemyPhase();
  if (checkEnd()) return;
  B.turn++;
  B.phase = 'p'; B.mode = 'idle';
  for (const c of B.units) c.acted = false;
  await banner(`Turn ${B.turn} — Player Phase`, SIDE_COLOR.p);
  await startOfTurn('p');
  if (checkEnd()) return;
  refreshSide();
}
async function startOfTurn(side) {
  for (const c of alive(side)) {
    let pct = 0;
    if (c.T.abil.includes('regen')) pct += 20;
    pct += bTerr(c.x, c.y).heal || 0;
    const amt = Math.min(Math.ceil(maxHp(c.u) * pct / 100), maxHp(c.u) - c.u.hp);
    if (amt > 0) { c.u.hp += amt; floatText(c, `+${amt}`, '#7cf07c', 16); }
  }
  for (const c of B.units) c.acted = false;
  await sleep(200);
}

// ── Enemy AI ────────────────────────────────────────────────────────────────
async function enemyPhase() {
  const order = alive('e').sort((a, b) => (a.T.weapon === 'staff') - (b.T.weapon === 'staff'));
  const field = distanceField(alive('p'));
  for (const c of order) {
    if (!c.alive || !alive('p').length) continue;
    await enemyAct(c, field);
    c.acted = true;
    if (checkEnd(true)) return;
  }
}
function distanceField(sources) {
  // Multi-source walk distance per movement type, ignoring other units.
  const fields = {};
  for (const mv of Object.keys(MOVE_TYPES)) {
    const d = new Array(BW * BH).fill(1e9), h = new Heap();
    for (const s of sources) { d[bIdx(s.x, s.y)] = 0; h.push(bIdx(s.x, s.y), 0); }
    while (h.size) {
      const i = h.pop(), x = i % BW, y = (i / BW) | 0;
      for (const [dx, dy] of N4) {
        const nx = x + dx, ny = y + dy; if (!inB(nx, ny)) continue;
        const j = bIdx(nx, ny), c = BTER[B.map[i]].cost[mv];
        if (c >= 99) continue;
        if (d[i] + c < d[j]) { d[j] = d[i] + c; h.push(j, d[j]); }
      }
    }
    fields[mv] = d;
  }
  return fields;
}
async function enemyAct(c, field) {
  const r = reachOf(c);
  const tiles = [...r.dist.keys()].filter(i => standable(c, i));
  if (c.T.weapon === 'staff') {
    let best = null;
    for (const i of tiles) for (const t of healTargetsFrom(c, i % BW, (i / BW) | 0)) {
      const need = maxHp(t.u) - t.u.hp;
      if (!best || need > best.need) best = { i, t, need };
    }
    if (best) {
      await moveUnit(c, best.i % BW, (best.i / BW) | 0);
      await doHeal(c, best.t);
      return;
    }
  }
  let best = null;
  for (const i of tiles) {
    const x = i % BW, y = (i / BW) | 0, terr = bTerr(x, y);
    for (const p of alive('p')) {
      if (!canAttackAt(c.T, manh(x, y, p.x, p.y))) continue;
      const fa = strikeStats(c, p, x, y, p.x, p.y, combatCtx);
      const fd = canAttackAt(p.T, manh(x, y, p.x, p.y)) ? strikeStats(p, c, p.x, p.y, x, y, combatCtx) : null;
      const n = (fa.brave ? 2 : 1) * (fa.doubles ? 2 : 1);
      const exp = fa.dmg * n * fa.hit / 100;
      const kill = fa.dmg * n >= p.u.hp && fa.hit > 30;
      const counter = fd ? fd.dmg * (fd.brave ? 2 : 1) * (fd.doubles ? 2 : 1) * fd.hit / 100 : 0;
      const score = exp + (kill ? 40 : 0) + (p.lead ? 12 : 0) + (fa.dmg > 0 ? 5 : -20) - counter * 0.5 + terr.avo * 0.08 - r.dist.get(i) * 0.05;
      if (!best || score > best.score) best = { i, p, score };
    }
  }
  if (best) {
    await moveUnit(c, best.i % BW, (best.i / BW) | 0);
    await doCombat(c, best.p);
    return;
  }
  // No attack possible: advance, unless the player is still far away early on
  // (defenders hold their walls until approached).
  const f = field[c.T.move];
  const here = f[bIdx(c.x, c.y)];
  const holdLimit = st(c.u, 'mov') * 2 + c.T.range[1] + (B.opt.siege === 'enemy' ? 0 : 2);
  if (here > holdLimit && B.turn < (B.opt.siege === 'enemy' ? 99 : 3)) return;
  let goal = null;
  for (const i of tiles) if (!goal || f[i] < f[goal]) goal = i;
  if (goal != null && f[goal] < here) await moveUnit(c, goal % BW, (goal / BW) | 0);
}

// ── End of battle ───────────────────────────────────────────────────────────
function checkEnd() {
  if (!B || B.ended) return true;
  const p = alive('p'), e = alive('e');
  const pLead = B.units.find(c => c.lead && c.side === 'p'), eLead = B.units.find(c => c.lead && c.side === 'e');
  if (!e.length) return endBattle(true, false, false), true;
  if (eLead && !eLead.alive) return endBattle(true, false, true), true;
  if (!p.length || (pLead && !pLead.alive)) return endBattle(false, false, false), true;
  return false;
}
function endBattle(win, retreat, rout) {
  if (B.ended) return;
  B.ended = true;
  hideMenu();
  const lost = B.units.filter(c => c.side === 'p' && !c.alive);
  const slain = B.units.filter(c => c.side === 'e' && !c.alive);
  if (win) {
    for (const c of alive('p')) applyXp(c, 15);  // victory bonus
  }
  if (rout) for (const c of alive('e')) { c.u.hp = 0; c.alive = false; }
  if (retreat) for (const c of B.units) if (c.side === 'p' && !c.lead) c.u.hp = 0;
  for (const c of B.units) delete c.u.bonus;
  const title = win ? (rout ? 'Victory — the enemy routs!' : 'Victory!') : retreat ? 'Retreat' : 'Defeat';
  const body = el('div', null,
    el('p', null, win ? 'The field is yours.' : retreat ? 'Your hero escapes, but the army is scattered.' : 'Your forces have been overwhelmed.'),
    el('p', null, el('b', null, 'Enemies slain: '), slain.length ? slain.map(c => c.T.icon).join(' ') : 'none'),
    el('p', null, el('b', null, 'Fallen: '), lost.length ? lost.map(c => `${c.T.icon} ${c.T.name}`).join(', ') : 'none'),
  );
  setTimeout(() => {
    modal(title, body, [['Continue', () => {
      cancelAnimationFrame(B.raf);
      const res = B.resolve; B = null;
      res({ win, retreat, rout });
    }]], { cls: win ? 'win' : 'lose', noClose: true });
  }, 500);
}
function retreatBattle() {
  if (!B || B.busy || B.phase !== 'p') return;
  confirmModal('Retreat?', 'Your hero will flee the battle. All other units in the army will be lost.', () => endBattle(false, true, false));
}

// ── Side panel UI ───────────────────────────────────────────────────────────
function banner(text, color) {
  const b = el('div', { className: 'banner', style: { borderColor: color } }, text);
  document.getElementById('bwrap').append(b);
  return sleep(900).then(() => b.remove());
}
function blog(msg) {
  if (!B) return;
  B.log.unshift(msg); B.log.length = Math.min(B.log.length, 40);
  const l = document.getElementById('b-log');
  if (l) l.innerHTML = B.log.map(m => `<div>${m}</div>`).join('');
}
function buildBattleUI() {
  const top = document.getElementById('btop');
  top.innerHTML = '';
  top.append(el('div', { className: 'btitle' }, B.opt.title),
    el('div', { id: 'b-phase', className: 'bphase' }));
  const side = document.getElementById('bside');
  side.innerHTML = '';
  side.append(
    el('div', { className: 'bbtns' },
      el('button', { className: 'btn primary', id: 'b-end', onClick: () => endPlayerPhase() }, 'End Turn'),
      el('button', { className: 'btn', id: 'b-power', onClick: () => activatePower() }, '✨ God'),
      el('button', { className: 'btn', id: 'b-danger', onClick: () => { B.showDanger = !B.showDanger; if (B.showDanger) { B.danger = new Set(); for (const c of alive('e')) for (const i of threatTiles(c)) B.danger.add(i); } refreshSide(); } }, '☠ Danger'),
      el('button', { className: 'btn ghost', onClick: () => retreatBattle() }, '🏳 Retreat')),
    el('div', { id: 'b-forecast' }),
    el('div', { id: 'b-info', className: 'card' }),
    el('div', { id: 'b-log', className: 'log' }),
  );
  const cv = document.getElementById('bcanvas');
  cv.width = BW * BT; cv.height = BH * BT;
}
function activatePower() {
  if (!B || B.busy || B.phase !== 'p' || B.powerUses <= 0 || !B.opt.player.power) return;
  const P = B.opt.player.power;
  if (B.mode === 'menu' || B.mode === 'target' || B.mode === 'heal') return;
  deselect();
  if (P.kind === 'bolt' || P.kind === 'hammer') { B.mode = 'power'; B.targets = alive('e'); refreshSide(); toast(`${P.name}: choose a target`); }
  else confirmModal(P.name, P.desc, async () => { await usePower(null); afterAction(); });
}
function refreshSide() {
  if (!B) return;
  const ph = document.getElementById('b-phase');
  if (ph) ph.textContent = `Turn ${B.turn} · ${B.phase === 'p' ? 'Player Phase' : 'Enemy Phase'} · ${alive('p').length} vs ${alive('e').length}`;
  const pw = document.getElementById('b-power'), P = B.opt.player.power;
  if (pw) {
    pw.disabled = !P || B.powerUses <= 0 || B.phase !== 'p';
    pw.textContent = P ? `✨ ${P.name} (${B.powerUses})` : '✨ No god';
    pw.title = P ? P.desc : '';
  }
  document.getElementById('b-end').disabled = B.phase !== 'p';
  document.getElementById('b-danger').classList.toggle('on', B.showDanger);
  const fc = document.getElementById('b-forecast');
  fc.innerHTML = '';
  if (B.mode === 'target' && B.target) fc.append(forecastCard(B.sel, B.target));
  else if (B.mode === 'target') fc.append(el('div', { className: 'hint' }, 'Choose a target (red). Right-click / Esc to cancel.'));
  else if (B.mode === 'heal') fc.append(el('div', { className: 'hint' }, 'Choose an ally to heal (green).'));
  else if (B.mode === 'power') fc.append(el('div', { className: 'hint' }, `${P.name}: choose an enemy.`));
  else if (B.mode === 'selected') fc.append(el('div', { className: 'hint' }, 'Blue: move · Red: attack range. Click an enemy to attack, or a tile to move.'));
  else if (B.phase === 'p' && B.mode === 'idle') fc.append(el('div', { className: 'hint' }, 'Select a blue unit. Click enemies to see their range. Adjacent allies grant +10 Hit/Avoid and may Dual Strike.'));
  refreshInfo();
}
function forecastCard(a, d) {
  const { fa, fd } = forecast(a, d);
  const row = (c, f, other) => {
    const mult = f ? (f.brave ? 2 : 1) * (f.doubles ? 2 : 1) : 0;
    const after = Math.max(0, other.u.hp);
    return el('div', { className: 'fc-side ' + c.side },
      el('div', { className: 'fc-name' }, `${c.T.icon} ${c.T.name}`),
      el('div', null, `HP ${c.u.hp}/${maxHp(c.u)}`),
      el('div', null, `Dmg ${f ? f.dmg : '—'}${mult > 1 ? ` ×${mult}` : ''}${f && f.eff ? ' ⚡' : ''}`),
      el('div', null, `Hit ${f ? f.hit : '—'}`),
      el('div', null, `Crit ${f ? f.crit : '—'}`),
      f && f.tri ? el('div', { className: f.tri > 0 ? 'up' : 'down' }, f.tri > 0 ? '▲ advantage' : '▼ disadvantage') : null,
    );
  };
  return el('div', { className: 'card forecast' },
    el('div', { className: 'fc-title' }, 'Combat Forecast'),
    el('div', { className: 'fc-grid' }, row(a, fa, d), row(d, fd, a)),
    el('div', { className: 'fc-btns' },
      el('button', { className: 'btn primary', onClick: () => confirmAttack() }, 'Attack!'),
      el('button', { className: 'btn ghost', onClick: () => cancelBattle() }, 'Back')));
}
function refreshInfo() {
  const box = document.getElementById('b-info');
  if (!box || !B) return;
  box.innerHTML = '';
  const h = B.hover;
  const c = h && inB(h.x, h.y) ? unitAt(h.x, h.y) : null;
  const show = c || B.sel;
  if (show) box.append(unitCard(show.u, show.side, show.lead));
  if (h && inB(h.x, h.y)) {
    const t = bTerr(h.x, h.y);
    box.append(el('div', { className: 'terr' }, `${t.name} · Avo +${t.avo} · Def +${t.def}${t.heal ? ` · Heal ${t.heal}%` : ''}`));
  }
}
function unitCard(u, side, lead) {
  const T = UNITS[u.type], W = WEAPONS[T.weapon];
  const s = k => { const b = (u.bonus && u.bonus[k]) || 0; return `${st(u, k)}${b ? `<sup>+${b}</sup>` : ''}`; };
  return el('div', { className: 'ucard ' + (side || '') },
    el('div', { className: 'uc-head' },
      el('span', { className: 'uc-icon' }, T.icon),
      el('div', null, el('div', { className: 'uc-name' }, T.name + (lead ? ' ⭐' : '')),
        el('div', { className: 'uc-sub' }, `Lv ${u.lvl} · XP ${u.xp} · ${MOVE_TYPES[T.move]}${T.tier ? ` · Tier ${T.tier}` : ' · Hero'}`))),
    el('div', { className: 'uc-hp', html: `HP <b>${u.hp}</b>/${maxHp(u)}` }),
    el('div', { className: 'uc-stats', html: ['str', 'mag', 'skl', 'spd', 'lck', 'def', 'res', 'mov'].map(k => `<span>${STAT_NAMES[k]} <b>${k === 'mov' ? u.stats.mov : s(k)}</b></span>`).join('') }),
    el('div', { className: 'uc-wpn' }, T.weapon === 'staff' ? `✚ Staff · heals ${st(u, 'mag') + 10}` : `${W.name} · Mt ${T.mt} · Hit ${T.hit} · Crit ${T.crit} · Rng ${T.range[0] === T.range[1] ? T.range[0] : T.range.join('-')}`),
    T.abil.length ? el('div', { className: 'uc-abil' }, T.abil.map(a => ABILITIES[a].split(' — ')[0]).join(' · ')) : null,
  );
}

document.addEventListener('DOMContentLoaded', () => {
  const cv = document.getElementById('bcanvas');
  cv.addEventListener('click', onBattleClick);
  cv.addEventListener('pointermove', onBattleHover);
  cv.addEventListener('contextmenu', e => { e.preventDefault(); cancelBattle(); });
  document.addEventListener('keydown', e => {
    if (!B) return;
    if (e.key === 'Escape') cancelBattle();
    if (e.key.toLowerCase() === 'e' && B.mode === 'idle') endPlayerPhase();
  });
});
