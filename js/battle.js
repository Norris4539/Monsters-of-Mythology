'use strict';
// ─────────────────────────────────────────────────────────────────────────────
// Tactical battles: Heroes 3 stacks on a grid.
//
//   startBattle(opt) → Promise<{ win, retreat, xp, lost }>
//
// opt = {
//   title, theme: BTHEMES key, siege: 'enemy' | 'player' | null (who has walls),
//   player: { units: stacks, hero, power: { kind, name, desc } | null, powerUses },
//   enemy:  { units: stacks, hero },
// }
// Every attack hits. Damage = creatures × damage roll, scaled by Attack vs
// Defence (+5% per point above, −2.5% per point below), with ±2 Attack from the
// weapon triangle. Each stack retaliates once per round. Heroes stay off the
// field: their Attack and Defence add to every stack, and Power fuels the god
// power. Large creatures fill 2×2 tiles.
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
      raf: 0, menuEl: null, xp: 0,
    };
    deploy('p', opt.player);
    deploy('e', opt.enemy);
    showScreen('battle');
    buildBattleUI();
    loop();
    (async () => { await banner('Round 1', SIDE_COLOR.p); await startOfPhase('p'); refreshSide(); })();
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
    for (let y = 0; y < BH; y++) for (const x of [0, 1, 2, BW - 3, BW - 2, BW - 1]) {
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
  const cols = side === 'p' ? [0, 1, 2] : enemyWalls ? [BW - 4, BW - 3, BW - 2, BW - 1] : [BW - 3, BW - 2, BW - 1];
  const rows = [4, 2, 6, 0, 8, 3, 5, 1, 7, 9];
  const hero = army.hero || null;
  const list = army.units.filter(s => s.n > 0).sort((a, b) => UNITS[b.type].size - UNITS[a.type].size);
  for (const s of list) {
    const T = UNITS[s.type], sz = T.size;
    const xs = side === 'p' ? cols.slice(0, cols.length - sz + 1) : cols.slice(sz - 1).map(x => x - sz + 1).reverse();
    let spot = null;
    for (const y of rows) {
      for (const x of xs) {
        if (y + sz > BH || x < 0 || x + sz > BW) continue;
        const cl = cellsAt(x, y, sz);
        if (cl.every(([cx, cy]) => BTER[B.map[bIdx(cx, cy)]].cost.foot < 99 && !unitAt(cx, cy))) { spot = [x, y]; break; }
      }
      if (spot) break;
    }
    if (!spot) continue;
    const [x, y] = spot;
    B.units.push({
      s, T, side, x, y, size: sz, px: x * BT, py: y * BT, ox: 0, oy: 0, acted: false, alive: true, alpha: 1, flash: 0,
      hero, startN: s.n, startHp: stackHp(s), retaliated: false, moved: 0, defMalus: 0, buff: { att: 0, mov: 0 },
    });
  }
}

// ── Geometry ────────────────────────────────────────────────────────────────
const bIdx = (x, y) => y * BW + x;
const inB = (x, y) => x >= 0 && y >= 0 && x < BW && y < BH;
const bTerr = (x, y) => BTER[B.map[bIdx(x, y)]];
const cellsAt = (x, y, sz) => { const o = []; for (let dy = 0; dy < sz; dy++) for (let dx = 0; dx < sz; dx++) o.push([x + dx, y + dy]); return o; };
const cellsOf = c => cellsAt(c.x, c.y, c.size);
const unitAt = (x, y) => B.units.find(c => c.alive && x >= c.x && x < c.x + c.size && y >= c.y && y < c.y + c.size);
const alive = side => B.units.filter(c => c.alive && c.side === side);
const foes = c => B.units.filter(o => o.alive && o.side !== c.side);
const N4 = [[1, 0], [-1, 0], [0, 1], [0, -1]];
function rectDist(ax, ay, as, bx, by, bs) {
  const dx = Math.max(0, bx - (ax + as - 1), ax - (bx + bs - 1)), dy = Math.max(0, by - (ay + as - 1), ay - (by + bs - 1));
  return dx + dy;
}
const distC = (a, b, ax = a.x, ay = a.y) => rectDist(ax, ay, a.size, b.x, b.y, b.size);
// Best (lowest) defensive terrain under a stack.
function terrOf(c, x = c.x, y = c.y) {
  let best = BTER.plain;
  for (const [cx, cy] of cellsAt(x, y, c.size)) { const t = bTerr(cx, cy); if (t.def + t.avo / 10 > best.def + best.avo / 10) best = t; }
  return best;
}

// Dijkstra over anchor positions (top-left cell). Allies can be passed through.
function reachOf(c, limit = movOf(c)) {
  const sz = c.size, dist = new Map([[bIdx(c.x, c.y), 0]]), prev = new Map(), h = new Heap();
  h.push(bIdx(c.x, c.y), 0);
  while (h.size) {
    const i = h.pop(), x = i % BW, y = (i / BW) | 0, d = dist.get(i);
    for (const [dx, dy] of N4) {
      const nx = x + dx, ny = y + dy;
      if (nx < 0 || ny < 0 || nx + sz > BW || ny + sz > BH) continue;
      let cost = 0, blocked = false;
      for (const [cx, cy] of cellsAt(nx, ny, sz)) {
        const o = unitAt(cx, cy);
        if (o && o !== c && o.side !== c.side) { blocked = true; break; }
        cost = Math.max(cost, bTerr(cx, cy).cost[c.T.move]);
      }
      if (blocked || cost >= 99) continue;
      const nd = d + cost, j = bIdx(nx, ny);
      if (nd > limit || nd >= (dist.get(j) ?? 1e9)) continue;
      dist.set(j, nd); prev.set(j, i); h.push(j, nd);
    }
  }
  return { dist, prev };
}
const standable = (c, i) => cellsAt(i % BW, (i / BW) | 0, c.size).every(([x, y]) => { const o = unitAt(x, y); return !o || o === c; });

// ── Effective stats ─────────────────────────────────────────────────────────
const adjacentAllies = c => B.units.filter(o => o.alive && o !== c && o.side === c.side && distC(c, o) === 1);
function movOf(c) { return c.T.mov + armyArtifact(c.hero, 'mov') + c.buff.mov; }
function attOf(a, d) {
  let v = a.T.att + heroStat(a.hero, 'att') + a.buff.att;
  if (a.T.abil.includes('bond')) v += adjacentAllies(a).filter(o => o.T.line === a.T.line).length;
  if (d) v += triangle(a.T.weapon, d.T.weapon) * 2;
  return v;
}
function defOf(d, x = d.x, y = d.y) {
  let v = d.T.def + heroStat(d.hero, 'def') - d.defMalus + terrOf(d, x, y).def;
  if (d.T.abil.includes('phalanx') && adjacentAllies(d).some(o => o.T.cls === 'heavy')) v += 2;
  if (d.T.abil.includes('bond')) v += adjacentAllies(d).filter(o => o.T.line === d.T.line).length;
  return Math.max(0, v);
}
const resOf = c => Math.min(.95, (c.T.res + armyArtifact(c.hero, 'res')) / 100);
// How a stack can strike a target from (x, y): 'melee', 'ranged', 'meleeHalf' or null.
function attackMode(a, t, x = a.x, y = a.y) {
  const d = distC(a, t, x, y), [lo, hi] = a.T.range;
  if (d === 1) return lo >= 2 ? 'meleeHalf' : 'melee';
  if (d >= Math.max(2, lo) && d <= hi) return 'ranged';
  return null;
}
const canStrike = c => c.T.weapon !== 'staff' || true;

// Heroes 3 damage with this game's modifiers. roll: 'rand' | 'min' | 'max' | 'avg'.
function calcDamage(a, d, mode, { roll = 'rand', moved = a.moved, x = a.x, y = a.y, splash = false } = {}) {
  const T = a.T;
  let D = defOf(d);
  if (T.abil.includes('pierce')) D = Math.floor(D / 2);
  let m = attDefMod(attOf(a, d), D);
  if (mode === 'meleeHalf') m *= .5;
  if (mode === 'ranged' && T.abil.includes('halfRange')) m *= .5;
  if (mode === 'melee' && T.abil.includes('charge')) m *= 1 + .05 * moved;
  if (B.opt.siege && T.abil.includes('siege')) m *= 1.25;
  if (T.weapon === 'staff') m *= .5;
  m *= 1 - terrOf(d).avo / 200;
  const hpPct = armyArtifact(d.hero, 'hpPct'); if (hpPct) m *= 100 / (100 + hpPct);
  if (splash) m *= .5;
  let lucky = false;
  if (roll === 'rand' && T.abil.includes('luck') && chance(20)) { m *= 2; lucky = true; }
  return { dmg: Math.max(1, Math.round(rollBase(T, a.s.n, roll) * m)), lucky };
}
function killsFor(t, dmg) {
  const H = t.T.hp, total = stackHp(t.s), left = Math.max(0, total - dmg);
  return t.s.n - Math.ceil(left / H);
}

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
  g.strokeStyle = 'rgba(0,0,0,.12)'; g.lineWidth = 1;
  for (let x = 0; x <= BW; x++) { g.beginPath(); g.moveTo(x * BT + .5, 0); g.lineTo(x * BT + .5, BH * BT); g.stroke(); }
  for (let y = 0; y <= BH; y++) { g.beginPath(); g.moveTo(0, y * BT + .5); g.lineTo(BW * BT, y * BT + .5); g.stroke(); }

  const tint = (x, y, col) => { g.fillStyle = col; g.fillRect(x * BT + 1, y * BT + 1, BT - 2, BT - 2); };
  if (B.showDanger) for (const i of B.danger) tint(i % BW, (i / BW) | 0, 'rgba(200,40,140,.22)');
  if ((B.mode === 'selected' || B.mode === 'canto') && B.reach) {
    const seen = new Set();
    for (const [i] of B.reach.dist) if (standable(B.sel, i)) for (const [x, y] of cellsAt(i % BW, (i / BW) | 0, B.sel.size)) { const k = bIdx(x, y); if (!seen.has(k)) { seen.add(k); tint(x, y, 'rgba(60,120,255,.36)'); } }
    if (B.mode === 'selected') for (const e of B.attackable || []) for (const [x, y] of cellsOf(e)) tint(x, y, 'rgba(230,50,50,.36)');
  }
  if (B.mode === 'enemyRange' && B.inspect) for (const i of B.inspect.tiles) tint(i % BW, (i / BW) | 0, 'rgba(230,50,50,.30)');
  if (B.mode === 'target' || B.mode === 'heal' || B.mode === 'power') {
    for (const c of B.targets) for (const [x, y] of cellsOf(c)) tint(x, y, B.mode === 'heal' ? 'rgba(60,200,90,.45)' : 'rgba(230,50,50,.45)');
  }
  if (B.hover && inB(B.hover.x, B.hover.y)) {
    g.strokeStyle = '#ffe27a'; g.lineWidth = 3;
    g.strokeRect(B.hover.x * BT + 2, B.hover.y * BT + 2, BT - 4, BT - 4);
  }
  for (const c of B.units) {
    if (!c.alive && c.alpha <= 0) continue;
    const R = c.size * BT, X = c.px + c.ox + R / 2, Y = c.py + c.oy + R / 2, rad = c.size === 2 ? 40 : 19;
    g.globalAlpha = c.alpha;
    g.beginPath(); g.arc(X, Y, rad, 0, Math.PI * 2);
    g.fillStyle = c.acted && B.phase === c.side ? '#6d6d6d' : SIDE_COLOR[c.side];
    g.fill();
    g.lineWidth = 2; g.strokeStyle = 'rgba(0,0,0,.45)'; g.stroke();
    if (c === B.sel) { g.strokeStyle = '#fff'; g.lineWidth = 2; g.beginPath(); g.arc(X, Y, rad + 3, 0, Math.PI * 2); g.stroke(); }
    g.font = `${c.size === 2 ? 46 : 22}px serif`; g.fillStyle = '#fff';
    g.fillText(c.T.icon, X, Y + 1);
    if (c.flash > 0) { g.fillStyle = `rgba(255,255,255,${c.flash})`; g.beginPath(); g.arc(X, Y, rad, 0, Math.PI * 2); g.fill(); c.flash = Math.max(0, c.flash - 0.08); }
    // level pips
    g.fillStyle = '#ffd24a';
    for (let k = 0; k < c.T.lvl; k++) { g.beginPath(); g.arc(X - rad + 5 + k * 6, Y - rad + 5, 2.4, 0, Math.PI * 2); g.fill(); }
    // count badge
    if (c.alive) {
      const txt = String(c.s.n); g.font = 'bold 12px system-ui, sans-serif';
      const w = g.measureText(txt).width + 8, bx = c.px + c.ox + R - w - 1, by = c.py + c.oy + R - 15;
      g.fillStyle = 'rgba(20,14,8,.9)'; g.fillRect(bx, by, w, 14);
      g.strokeStyle = SIDE_COLOR[c.side]; g.lineWidth = 1; g.strokeRect(bx + .5, by + .5, w - 1, 13);
      g.fillStyle = '#fff'; g.fillText(txt, bx + w / 2, by + 7.5);
      const frac = clamp(c.s.hp / c.T.hp, 0, 1);
      g.fillStyle = 'rgba(0,0,0,.6)'; g.fillRect(c.px + c.ox + 3, c.py + c.oy + R - 6, R * .45, 4);
      g.fillStyle = frac > .5 ? '#5fd35f' : frac > .25 ? '#e8c440' : '#e85040'; g.fillRect(c.px + c.ox + 4, c.py + c.oy + R - 5, (R * .45 - 2) * frac, 2);
    }
    g.globalAlpha = 1;
  }
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
function floatText(c, text, color = '#fff', size = 18, dur = 1200) {
  B.floats.push({ x: c.px + c.size * BT / 2, y: c.py + 4, text, color, size, dur, t0: performance.now() });
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
  c.moved += path.length;
  c.x = x; c.y = y;
  for (const i of path) {
    const sx = c.px, sy = c.py, tx = (i % BW) * BT, ty = ((i / BW) | 0) * BT;
    await tween(70, k => { c.px = sx + (tx - sx) * k; c.py = sy + (ty - sy) * k; });
  }
  c.px = x * BT; c.py = y * BT;
}

// ── Combat ──────────────────────────────────────────────────────────────────
async function lunge(s, t) {
  const dx = Math.sign((t.x + t.size / 2) - (s.x + s.size / 2)) * 10, dy = Math.sign((t.y + t.size / 2) - (s.y + s.size / 2)) * 10;
  await tween(110, k => { s.ox = dx * k; s.oy = dy * k; });
  return async () => { await tween(110, k => { s.ox = dx * (1 - k); s.oy = dy * (1 - k); }); s.ox = s.oy = 0; };
}
async function strike(s, t, mode, opts = {}) {
  if (!s.alive || !t.alive) return;
  const back = await lunge(s, t);
  const { dmg, lucky } = calcDamage(s, t, mode, opts);
  const before = stackHp(t.s), beforeN = t.s.n;
  setStackHp(t.s, before - dmg);
  const dealt = before - stackHp(t.s), kills = beforeN - t.s.n;
  if (s.side === 'p') B.xp += dealt;
  t.flash = .8;
  if (opts.label) floatText(s, opts.label, '#ffe27a', 14, 900);
  if (lucky) floatText(s, 'Lucky strike!', '#ffcf3a', 15, 900);
  floatText(t, kills ? `−${dealt} · ${kills} slain` : `−${dealt}`, lucky ? '#ffcf3a' : '#ff6a5a', 16);
  blog(`${s.T.name} (${s.s.n}) ${opts.retal ? 'retaliates against' : 'hits'} ${t.T.name} for ${dealt}${kills ? `, ${kills} perish` : ''}.`);
  if (s.T.abil.includes('lifesteal') && dealt > 0) {
    const b = stackHp(s.s); setStackHp(s.s, b + Math.ceil(dealt / 2), s.startN); const gain = stackHp(s.s) - b;
    if (gain > 0) floatText(s, `+${gain}`, '#7cf07c', 15);
  }
  await back();
  if (t.s.n <= 0) await killUnit(t);
  await sleep(120);
}
async function killUnit(c) {
  c.alive = false;
  blog(`☠️ The ${c.T.name} stack is destroyed.`);
  await tween(380, k => { c.alpha = 1 - k; });
}
// Full attack exchange: strike(s), retaliation, follow-up.
async function doCombat(a, d, mode) {
  B.busy = true;
  mode = mode || attackMode(a, d);
  const melee = mode !== 'ranged';
  if (a.T.abil.includes('manyHeads') && melee) {
    const all = foes(a).filter(o => distC(a, o) === 1);
    for (const t of all) await strike(a, t, 'melee', { label: all.length > 1 ? 'Many heads!' : null });
  } else {
    await strike(a, d, mode);
    if (a.T.abil.includes('cleave') && melee && a.alive) {
      const other = foes(a).find(o => o !== d && o.alive && distC(a, o) === 1 && (!d.alive || distC(d, o) <= 1));
      if (other) await strike(a, other, 'melee', { splash: true, label: 'Cleave!' });
    }
    if (melee && d.alive && a.alive && !d.retaliated) {
      const rm = attackMode(d, a);
      if (rm && rm !== 'ranged') { d.retaliated = true; await strike(d, a, rm, { retal: true, moved: 0 }); }
    }
    if (a.T.abil.includes('doubleStrike') && a.alive && d.alive) await strike(a, d, mode, { label: 'Again!' });
  }
  B.busy = false;
}
async function doHeal(h, t) {
  B.busy = true;
  const amt = 10 + h.s.n * 4, before = stackHp(t.s);
  setStackHp(t.s, before + amt, t.startN);
  const gain = stackHp(t.s) - before;
  await tween(150, k => { h.oy = -6 * Math.sin(k * Math.PI); });
  floatText(t, `+${gain}`, '#7cf07c', 20);
  blog(`${h.T.name} heal ${t.T.name} for ${gain}.`);
  await sleep(250);
  B.busy = false;
}

// God powers scale with the hero's Power; Resistance reduces them.
async function usePower(target) {
  const P = B.opt.player.power, pw = heroStat(B.opt.player.hero, 'power'), en = alive('e');
  B.busy = true; B.powerUses--;
  blog(`✨ ${P.name}!`);
  const hurt = async (c, base) => {
    const dmg = Math.max(1, Math.round(base * (1 - resOf(c)))), before = stackHp(c.s), bn = c.s.n;
    setStackHp(c.s, before - dmg); c.flash = 1; B.xp += before - stackHp(c.s);
    floatText(c, `−${before - stackHp(c.s)}${bn - c.s.n ? ` · ${bn - c.s.n} slain` : ''}`, '#ffd84a', 18);
    if (c.s.n <= 0) await killUnit(c);
  };
  if (P.kind === 'bolt') await hurt(target, 40 + 30 * pw);
  if (P.kind === 'hammer') {
    const main = 30 + 20 * pw; await hurt(target, main);
    for (const o of en) if (o !== target && o.alive && distC(o, target) === 1) await hurt(o, main / 2);
  }
  if (P.kind === 'flare') for (const o of en) await hurt(o, 15 + 10 * pw);
  if (P.kind === 'dawn') for (const o of alive('p')) { const b = stackHp(o.s); setStackHp(o.s, b + 30 + 20 * pw, o.startN); o.flash = 1; floatText(o, `+${stackHp(o.s) - b}`, '#7cf07c', 18); }
  await sleep(500);
  B.busy = false;
}

// ── Player input ────────────────────────────────────────────────────────────
function bTileFromEvent(e) {
  const cv = document.getElementById('bcanvas'), r = cv.getBoundingClientRect();
  return { x: Math.floor((e.clientX - r.left) / r.width * BW), y: Math.floor((e.clientY - r.top) / r.height * BH) };
}
// Enemies this stack can attack from any tile it can reach.
function attackableFrom(c, reach) {
  const out = new Set();
  if (c.T.weapon === 'staff') return out;
  for (const [i] of reach.dist) if (standable(c, i)) for (const e of foes(c)) if (attackMode(c, e, i % BW, (i / BW) | 0)) out.add(e);
  return out;
}
function select(c) {
  B.sel = c; B.mode = 'selected'; B.orig = { x: c.x, y: c.y, px: c.px, py: c.py, moved: c.moved };
  B.reach = reachOf(c, movOf(c) - c.moved); B.attackable = attackableFrom(c, B.reach); B.target = null;
  hideMenu(); refreshSide();
}
function deselect() {
  B.sel = null; B.mode = 'idle'; B.reach = null; B.targets = []; B.target = null; B.attackable = null;
  hideMenu(); refreshSide();
}
function bestAttackTile(c, foe) {
  let best = null, bestScore = -1e9;
  for (const [i] of B.reach.dist) {
    if (!standable(c, i)) continue;
    const x = i % BW, y = (i / BW) | 0, mode = attackMode(c, foe, x, y);
    if (!mode) continue;
    const t = terrOf(c, x, y);
    const score = (i === bIdx(c.x, c.y) ? 40 : 0) + (mode === 'ranged' ? 60 : mode === 'meleeHalf' ? -40 : 0) + t.avo + t.def * 10 - B.reach.dist.get(i) * (c.T.abil.includes('charge') ? -2 : 1);
    if (score > bestScore) { bestScore = score; best = { x, y }; }
  }
  return best;
}
// Pick an anchor so a 2×2 stack covers the clicked tile.
function anchorFor(c, x, y) {
  let best = null;
  for (let dy = 0; dy < c.size; dy++) for (let dx = 0; dx < c.size; dx++) {
    const ax = x - dx, ay = y - dy, i = bIdx(ax, ay);
    if (ax < 0 || ay < 0 || !B.reach.dist.has(i) || !standable(c, i)) continue;
    const d = B.reach.dist.get(i); if (!best || d < best.d) best = { x: ax, y: ay, d };
  }
  return best;
}

async function onBattleClick(e) {
  if (!B || B.busy || B.phase !== 'p') return;
  const { x, y } = bTileFromEvent(e);
  if (!inB(x, y)) return;
  const c = unitAt(x, y);
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
        B.targets = foes(s).filter(o => attackMode(s, o)); B.mode = 'target'; showForecast(c);
      } else {
        const a = anchorFor(s, x, y);
        if (a) { B.busy = true; await moveUnit(s, a.x, a.y); B.busy = false; openMenu(); }
        else deselect();
      }
      break;
    }
    case 'canto': {
      const s = B.sel, a = anchorFor(s, x, y);
      if (a) { B.busy = true; await moveUnit(s, a.x, a.y); B.busy = false; }
      finishUnit(s);
      break;
    }
    case 'target':
      if (c && B.targets.includes(c)) { if (B.target === c) await confirmAttack(); else showForecast(c); }
      break;
    case 'heal':
      if (c && B.targets.includes(c)) { hideMenu(); await doHeal(B.sel, c); finishUnit(B.sel); }
      break;
    case 'power':
      if (c && B.targets.includes(c)) { B.mode = 'idle'; B.targets = []; await usePower(c); afterAction(); }
      break;
  }
}
function threatTiles(c) {
  const out = new Set();
  const r = reachOf(c, movOf(c));
  for (const [i] of r.dist) if (standable(c, i)) {
    const ax = i % BW, ay = (i / BW) | 0;
    for (let y = 0; y < BH; y++) for (let x = 0; x < BW; x++) {
      const d = rectDist(ax, ay, c.size, x, y, 1);
      if (d >= 1 && d <= Math.max(1, c.T.range[1])) out.add(bIdx(x, y));
    }
  }
  return out;
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
    const s = B.sel; s.x = B.orig.x; s.y = B.orig.y; s.px = B.orig.px; s.py = B.orig.py; s.moved = B.orig.moved;
    select(s);
  } else if (B.mode === 'canto') finishUnit(B.sel);
  else if (B.mode === 'power') { B.mode = 'idle'; B.targets = []; refreshSide(); }
  else deselect();
}
function openMenu() {
  const s = B.sel;
  B.mode = 'menu'; B.reach = null; B.targets = []; B.target = null;
  const items = [];
  const atk = s.T.weapon === 'staff' && !foes(s).some(o => attackMode(s, o) === 'melee') ? [] : foes(s).filter(o => attackMode(s, o));
  const heal = s.T.abil.includes('heal') ? B.units.filter(o => o.alive && o !== s && o.side === s.side && distC(s, o) === 1 && stackHp(o.s) < o.startHp) : [];
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
  const left = (c.x + c.size) * BT * sx + (r.left - wr.left) + 6, top = c.y * BT * sx + (r.top - wr.top);
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
  if (!s.alive) { B.sel = null; afterAction(); return; }
  const left = movOf(s) - s.moved;
  if (s.T.abil.includes('hitAndRun') && left > 0 && !checkEnd()) {
    B.mode = 'canto'; B.reach = reachOf(s, left); refreshSide(); toast('Hit and run: move again, or right-click to stay.');
    return;
  }
  finishUnit(s);
}
function finishUnit(c) {
  c.acted = true; B.sel = null; B.mode = 'idle'; B.reach = null; B.targets = []; B.attackable = null;
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
  await startOfPhase('e');
  if (checkEnd()) return;
  await enemyPhase();
  if (checkEnd()) return;
  B.turn++;
  for (const c of B.units) c.retaliated = false;
  B.phase = 'p'; B.mode = 'idle';
  await banner(`Round ${B.turn}`, SIDE_COLOR.p);
  await startOfPhase('p');
  if (checkEnd()) return;
  refreshSide();
}
// Start-of-turn effects: regrowth, fort healing, bleeding ichor, cavalry runners.
async function startOfPhase(side) {
  for (const c of alive(side)) {
    c.acted = false; c.moved = 0; c.buff = { att: 0, mov: 0 };
    if (c.T.abil.includes('regrow') && c.s.hp < c.T.hp) { const g = c.T.hp - c.s.hp; c.s.hp = c.T.hp; floatText(c, `+${g}`, '#7cf07c', 15); }
    const heal = terrOf(c).heal;
    if (heal) { const b = stackHp(c.s); setStackHp(c.s, b + Math.ceil(c.T.hp * heal / 100), c.startN); if (stackHp(c.s) > b) floatText(c, `+${stackHp(c.s) - b}`, '#7cf07c', 15); }
    if (c.T.abil.includes('ichor') && stackHp(c.s) < c.startHp / 2) { c.defMalus += 2; floatText(c, 'Ichor bleeds −2 Def', '#ff9a2e', 13); }
    if (c.T.abil.includes('withHorse') && adjacentAllies(c).some(o => o.T.move === 'horse')) { c.buff = { att: 2, mov: 2 }; floatText(c, 'Runs with the horse', '#bfe3ff', 13); }
  }
  await sleep(200);
}

// ── Enemy AI ────────────────────────────────────────────────────────────────
async function enemyPhase() {
  const order = alive('e').sort((a, b) => movOf(b) - movOf(a));
  for (const c of order) {
    if (!c.alive || !alive('p').length) continue;
    await enemyAct(c);
    c.acted = true;
    if (checkEnd()) return;
  }
}
function distanceField(mv) {
  const d = new Array(BW * BH).fill(1e9), h = new Heap();
  for (const s of alive('p')) for (const [x, y] of cellsOf(s)) { d[bIdx(x, y)] = 0; h.push(bIdx(x, y), 0); }
  while (h.size) {
    const i = h.pop(), x = i % BW, y = (i / BW) | 0;
    for (const [dx, dy] of N4) {
      const nx = x + dx, ny = y + dy; if (!inB(nx, ny)) continue;
      const j = bIdx(nx, ny), c = BTER[B.map[i]].cost[mv];
      if (c >= 99) continue;
      if (d[i] + c < d[j]) { d[j] = d[i] + c; h.push(j, d[j]); }
    }
  }
  return d;
}
const valueOf = (c, n) => creatureValue(c.T) * n;
async function enemyAct(c) {
  const r = reachOf(c, movOf(c) - c.moved);
  const tiles = [...r.dist.keys()].filter(i => standable(c, i));
  if (c.T.abil.includes('heal')) {
    let best = null;
    for (const i of tiles) for (const t of alive('e')) {
      if (t === c || rectDist(i % BW, (i / BW) | 0, c.size, t.x, t.y, t.size) !== 1) continue;
      const need = t.startHp - stackHp(t.s);
      if (need > 0 && (!best || need > best.need)) best = { i, t, need };
    }
    if (best) { await moveUnit(c, best.i % BW, (best.i / BW) | 0); await doHeal(c, best.t); return; }
  }
  let best = null;
  for (const i of tiles) {
    const x = i % BW, y = (i / BW) | 0, terr = terrOf(c, x, y);
    for (const p of alive('p')) {
      const mode = attackMode(c, p, x, y);
      if (!mode) continue;
      const moved = c.moved + r.dist.get(i);
      let gain;
      if (c.T.abil.includes('manyHeads') && mode !== 'ranged') {
        gain = alive('p').filter(o => rectDist(x, y, c.size, o.x, o.y, o.size) === 1).reduce((t, o) => t + valueOf(o, Math.min(o.s.n, killsFor(o, calcDamage(c, o, 'melee', { roll: 'avg', moved, x, y }).dmg))) + 5, 0);
      } else {
        const dmg = calcDamage(c, p, mode, { roll: 'avg', moved, x, y }).dmg, kills = Math.min(p.s.n, killsFor(p, dmg));
        gain = valueOf(p, kills) + dmg * .2;
        if (mode !== 'ranged' && !p.retaliated && kills < p.s.n) {
          const left = p.s.n - kills, rm = rectDist(x, y, c.size, p.x, p.y, p.size) === 1 ? (p.T.range[0] >= 2 ? 'meleeHalf' : 'melee') : null;
          if (rm) { const saved = p.s.n; p.s.n = left; const rd = calcDamage(p, c, rm, { roll: 'avg', moved: 0 }).dmg; p.s.n = saved; gain -= valueOf(c, Math.min(c.s.n, killsFor(c, rd))) * .6; }
        }
        if (mode === 'meleeHalf') gain *= .7;
      }
      const score = gain + terr.avo * .05 - r.dist.get(i) * .01;
      if (!best || score > best.score) best = { i, p, score };
    }
  }
  if (best && best.score > 0) {
    await moveUnit(c, best.i % BW, (best.i / BW) | 0);
    await doCombat(c, best.p);
    if (c.alive && c.T.abil.includes('hitAndRun')) {
      const left = movOf(c) - c.moved;
      if (left > 0) {
        const r2 = reachOf(c, left); let far = null;
        for (const [i] of r2.dist) if (standable(c, i)) { const d = Math.min(...alive('p').map(o => rectDist(i % BW, (i / BW) | 0, c.size, o.x, o.y, o.size))); if (!far || d > far.d) far = { i, d }; }
        if (far) await moveUnit(c, far.i % BW, (far.i / BW) | 0);
      }
    }
    return;
  }
  // No good attack: advance, unless the player is still far away early on.
  if (c.T.range[1] >= 3) return;   // archers hold and shoot next turn
  const f = distanceField(c.T.move);
  const here = Math.min(...cellsOf(c).map(([x, y]) => f[bIdx(x, y)]));
  const holdLimit = movOf(c) * 2 + c.T.range[1] + (B.opt.siege === 'enemy' ? 0 : 2);
  if (here > holdLimit && B.turn < (B.opt.siege === 'enemy' ? 99 : 3)) return;
  let goal = null, gd = here;
  for (const i of tiles) { const d = Math.min(...cellsAt(i % BW, (i / BW) | 0, c.size).map(([x, y]) => f[bIdx(x, y)])); if (d < gd) { gd = d; goal = i; } }
  if (goal != null) await moveUnit(c, goal % BW, (goal / BW) | 0);
}

// ── End of battle ───────────────────────────────────────────────────────────
function checkEnd() {
  if (!B || B.ended) return true;
  if (!alive('e').length) return endBattle(true, false), true;
  if (!alive('p').length) return endBattle(false, false), true;
  return false;
}
function endBattle(win, retreat) {
  if (B.ended) return;
  B.ended = true;
  hideMenu();
  if (retreat) for (const c of B.units) if (c.side === 'p') { c.s.n = 0; c.s.hp = 0; }
  const lost = {}, slain = {};
  for (const c of B.units) {
    const n = c.startN - Math.max(0, c.s.n);
    if (n <= 0) continue;
    const bag = c.side === 'p' ? lost : slain; bag[c.s.type] = (bag[c.s.type] || 0) + n;
  }
  const list = bag => Object.entries(bag).map(([t, n]) => `${n} ${UNITS[t].icon} ${UNITS[t].name}`).join(', ') || 'none';
  const title = win ? 'Victory!' : retreat ? 'Retreat' : 'Defeat';
  const body = el('div', null,
    el('p', null, win ? 'The field is yours.' : retreat ? 'Your hero escapes, but the army is scattered.' : 'Your forces have been overwhelmed.'),
    el('p', null, el('b', null, 'Enemies slain: '), list(slain)),
    el('p', null, el('b', null, 'Your losses: '), list(lost)),
    B.opt.player.hero ? el('p', null, el('b', null, 'Experience: '), `+${B.xp}`) : null,
  );
  const xp = B.xp;
  setTimeout(() => {
    modal(title, body, [['Continue', () => {
      cancelAnimationFrame(B.raf);
      const res = B.resolve; B = null;
      res({ win, retreat, xp, lost });
    }]], { cls: win ? 'win' : 'lose', noClose: true });
  }, 500);
}
function retreatBattle() {
  if (!B || B.busy || B.phase !== 'p') return;
  confirmModal('Retreat?', 'Your hero will flee the battle. Every stack in the army will be lost.', () => endBattle(false, true));
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
  top.append(el('div', { className: 'btitle' }, B.opt.title), el('div', { id: 'b-phase', className: 'bphase' }));
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
  if (B.mode === 'menu' || B.mode === 'target' || B.mode === 'heal' || B.mode === 'canto') return;
  deselect();
  if (P.kind === 'bolt' || P.kind === 'hammer') { B.mode = 'power'; B.targets = alive('e'); refreshSide(); toast(`${P.name}: choose a target`); }
  else confirmModal(P.name, P.desc, async () => { await usePower(null); afterAction(); });
}
function refreshSide() {
  if (!B) return;
  const ph = document.getElementById('b-phase');
  const tot = side => alive(side).reduce((t, c) => t + c.s.n, 0);
  if (ph) ph.textContent = `Round ${B.turn} · ${B.phase === 'p' ? 'Your turn' : 'Enemy turn'} · ${tot('p')} vs ${tot('e')} creatures`;
  const pw = document.getElementById('b-power'), P = B.opt.player.power;
  if (pw) {
    pw.disabled = !P || B.powerUses <= 0 || B.phase !== 'p';
    pw.textContent = P ? `✨ ${P.name} (${B.powerUses})` : '✨ No hero';
    pw.title = P ? P.desc : '';
  }
  document.getElementById('b-end').disabled = B.phase !== 'p';
  document.getElementById('b-danger').classList.toggle('on', B.showDanger);
  const fc = document.getElementById('b-forecast');
  fc.innerHTML = '';
  const hint = t => fc.append(el('div', { className: 'hint' }, t));
  if (B.mode === 'target' && B.target) fc.append(forecastCard(B.sel, B.target));
  else if (B.mode === 'target') hint('Choose a target (red). Right-click / Esc to cancel.');
  else if (B.mode === 'heal') hint('Choose an ally to heal (green).');
  else if (B.mode === 'power') hint(`${P.name}: choose an enemy stack.`);
  else if (B.mode === 'canto') hint('Hit and run: click a blue tile to move again, or right-click to stay put.');
  else if (B.mode === 'selected') hint('Blue: move · Red: stacks you can attack. Click an enemy to attack it, or a tile to move.');
  else if (B.phase === 'p' && B.mode === 'idle') hint('Select one of your stacks. Every attack hits; damage depends on numbers, Attack vs Defence and the weapon triangle. Each stack retaliates once per round.');
  refreshInfo();
}
function forecastCard(a, d) {
  const mode = attackMode(a, d);
  const lo = calcDamage(a, d, mode, { roll: 'min' }).dmg, hi = calcDamage(a, d, mode, { roll: 'max' }).dmg;
  const kLo = Math.min(d.s.n, killsFor(d, lo)), kHi = Math.min(d.s.n, killsFor(d, hi));
  let retal = null;
  const many = a.T.abil.includes('manyHeads') && mode !== 'ranged';
  if (mode !== 'ranged' && !many && !d.retaliated) {
    const rm = attackMode(d, a);
    if (rm && rm !== 'ranged') {
      const avg = calcDamage(a, d, mode, { roll: 'avg' }).dmg, left = Math.max(0, d.s.n - killsFor(d, avg));
      if (left > 0) { const saved = d.s.n; d.s.n = left; const rd = calcDamage(d, a, rm, { roll: 'avg', moved: 0 }).dmg; d.s.n = saved; retal = { dmg: rd, kills: Math.min(a.s.n, killsFor(a, rd)) }; }
      else retal = { dmg: 0, kills: 0 };
    }
  }
  const tri = triangle(a.T.weapon, d.T.weapon);
  return el('div', { className: 'card forecast' },
    el('div', { className: 'fc-title' }, mode === 'ranged' ? 'Ranged attack' : mode === 'meleeHalf' ? 'Melee (half damage)' : 'Melee attack'),
    el('div', { className: 'fc-grid' },
      el('div', { className: 'fc-side p' }, el('div', { className: 'fc-name' }, `${a.s.n} ${a.T.icon} ${a.T.name}`),
        el('div', null, `Damage ${lo}–${hi}`), el('div', null, `Slays ${kLo}–${kHi} of ${d.s.n}`),
        tri ? el('div', { className: tri > 0 ? 'up' : 'down' }, tri > 0 ? '▲ +2 Attack (triangle)' : '▼ −2 Attack (triangle)') : null,
        a.T.abil.includes('charge') && mode === 'melee' && a.moved ? el('div', { className: 'up' }, `Charge +${a.moved * 5}%`) : null),
      el('div', { className: 'fc-side e' }, el('div', { className: 'fc-name' }, `${d.s.n} ${d.T.icon} ${d.T.name}`),
        many ? el('div', null, 'Cannot retaliate (many heads)') : mode === 'ranged' ? el('div', null, 'No retaliation at range') : d.retaliated ? el('div', null, 'Already retaliated this round') :
          retal ? [el('div', null, `Retaliates ~${retal.dmg}`), el('div', null, `Slays ~${retal.kills} of ${a.s.n}`)] : el('div', null, 'Cannot retaliate'))),
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
  if (show) box.append(stackCard(show.s, show.side, show));
  if (h && inB(h.x, h.y)) {
    const t = bTerr(h.x, h.y);
    box.append(el('div', { className: 'terr' }, `${t.name} · Def +${t.def} · −${t.avo / 2}% damage taken${t.heal ? ` · heals ${t.heal}%` : ''}`));
  }
}
// Stack card, shared with the adventure map. c is the battle combatant if any.
function stackCard(s, side, c) {
  const T = UNITS[s.type];
  const att = c ? attOf(c) : T.att, def = c ? defOf(c) : T.def, mov = c ? movOf(c) : T.mov;
  const bon = (v, b) => v !== b ? `${v}<sup>${v > b ? '+' : ''}${v - b}</sup>` : `${v}`;
  return el('div', { className: 'ucard ' + (side || '') },
    el('div', { className: 'uc-head' },
      el('span', { className: 'uc-icon' }, T.icon),
      el('div', null, el('div', { className: 'uc-name' }, `${s.n} × ${T.name}`),
        el('div', { className: 'uc-sub' }, `${'★'.repeat(T.lvl)}${'☆'.repeat(3 - T.lvl)} · Tier ${T.tier} · ${CLASSES[T.cls]} · ${MOVE_TYPES[T.move]}${T.size > 1 ? ' · Large' : ''}`))),
    el('div', { className: 'uc-stats', html: [
      ['Attack', bon(att, T.att)], ['Defence', bon(def, T.def)], ['Damage', `${T.dmg[0]}–${T.dmg[1]}`], ['Health', `${s.hp}/${T.hp}`],
      ['Move', bon(mov, T.mov)], ['Resist', `${T.res}%`], ['Range', T.range[1] > 1 ? `${T.range[0]}–${T.range[1]}` : 'melee'], ['Weapon', WEAPONS[T.weapon].name],
    ].map(([k, v]) => `<span>${k} <b>${v}</b></span>`).join('') }),
    T.abil.length ? el('div', { className: 'uc-abil' }, T.abil.map(a => ABILITIES[a][0]).join(' · ')) : null,
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
