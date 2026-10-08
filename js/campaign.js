'use strict';
// ─────────────────────────────────────────────────────────────────────────────
// The adventure map (Heroes of Might & Magic III style): generation, hero
// movement, map objects, towns, the day/week cycle and the computer players.
// ─────────────────────────────────────────────────────────────────────────────

let G = null;

const MINE_INFO = {
  gold:  { name: 'Gold Mine',    icon: '⛏️', amt: 500 },
  wood:  { name: 'Sawmill',      icon: '🪚', amt: 2 },
  stone: { name: 'Quarry',       icon: '🏗️', amt: 2 },
  ichor: { name: 'Ichor Spring', icon: '⛲', amt: 1 },
};
const N8 = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]];

const idx = (x, y) => y * G.W + x;
const inMap = (x, y) => x >= 0 && y >= 0 && x < G.W && y < G.H;
const passable = i => G.terr[i] !== 'water' && !G.obst[i];
const playerOf = id => G.players.find(p => p.id === id);
const heroOf = p => G.heroes.find(h => h.owner === p.id);
const human = () => G.players[0];
const townsOf = p => G.objs.filter(o => o.kind === 'town' && o.owner === p.id);
const heroAtIdx = i => G.heroes.find(h => h.alive && idx(h.x, h.y) === i);
const colorOf = owner => owner == null ? NEUTRAL_COLOR : FACTIONS[playerOf(owner).faction].color;
const dateText = d => `Month ${Math.floor((d - 1) / 28) + 1}, Week ${Math.floor(((d - 1) % 28) / 7) + 1}, Day ${(d - 1) % 7 + 1}`;

function rebuildIndex() {
  G.objAt = new Map(); G.guard = new Map();
  for (const o of G.objs) G.objAt.set(idx(o.x, o.y), o);
  for (const o of G.objs) if (o.kind === 'monster') for (const [dx, dy] of N8) {
    const x = o.x + dx, y = o.y + dy;
    if (inMap(x, y) && passable(idx(x, y)) && !G.guard.has(idx(x, y))) G.guard.set(idx(x, y), o);
  }
}
function removeObj(o) { G.objs = G.objs.filter(x => x !== o); rebuildIndex(); }

// ── New game & map generation ───────────────────────────────────────────────
function newGame({ faction, opponents, difficulty }) {
  UID = 1;
  const W = 46, H = 34;
  G = { W, H, day: 1, terr: [], obst: [], road: [], objs: [], heroes: [], players: [], fog: new Array(W * H).fill(0), difficulty, nextId: 1, log: [], over: false };
  const others = shuffle(FACTION_KEYS.filter(f => f !== faction)).slice(0, opponents);
  const fs = [faction, ...others];
  fs.forEach((f, i) => G.players.push({
    id: i, faction: f, human: i === 0, alive: true, noTownDays: 0,
    res: i === 0 ? { gold: 6000, wood: 15, stone: 15, ichor: 3 } : { gold: 6000 + difficulty * 2000, wood: 20, stone: 20, ichor: 3 + difficulty * 2 },
  }));
  genMap(fs);
  rebuildIndex();
  revealAround(heroOf(human()));
  for (const t of townsOf(human())) reveal(t.x, t.y, 5);
  log(`The gods have set you upon the world. Defeat ${others.map(f => FACTIONS[f].name).join(', ')}!`);
}

function valueNoise(W, H, cell) {
  const gw = Math.ceil(W / cell) + 2, gh = Math.ceil(H / cell) + 2;
  const g = Array.from({ length: gw * gh }, () => Math.random());
  const out = new Float32Array(W * H);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const fx = x / cell, fy = y / cell, x0 = Math.floor(fx), y0 = Math.floor(fy), tx = fx - x0, ty = fy - y0;
    const s = t => t * t * (3 - 2 * t);
    const a = g[y0 * gw + x0], b = g[y0 * gw + x0 + 1], c = g[(y0 + 1) * gw + x0], d = g[(y0 + 1) * gw + x0 + 1];
    out[y * W + x] = (a + (b - a) * s(tx)) + ((c + (d - c) * s(tx)) - (a + (b - a) * s(tx))) * s(ty);
  }
  return out;
}

function genMap(fs) {
  const { W, H } = G;
  const corners = shuffle([[5, 5], [W - 6, 5], [5, H - 6], [W - 6, H - 6]]);
  const center = [Math.floor(W / 2), Math.floor(H / 2)];
  const spare = shuffle(['dirt', 'swamp', ...FACTION_KEYS.filter(f => !fs.includes(f)).map(f => FACTIONS[f].biome)]);
  const sites = corners.map((c, i) => ({ x: c[0], y: c[1], faction: fs[i] || null, biome: fs[i] ? FACTIONS[fs[i]].biome : spare[i % spare.length] }));
  const jitter = valueNoise(W, H, 5), lumps = valueNoise(W, H, 3);
  // Biomes: nearest site, with a wasteland/marsh heart in the middle.
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = y * W + x, j = jitter[i] * 8;
    let best = null, bd = 1e9;
    for (const s of sites) { const d = Math.hypot(s.x - x, s.y - y) + j; if (d < bd) { bd = d; best = s; } }
    const dc = Math.hypot(center[0] - x, center[1] - y) + j * 0.6;
    G.terr[i] = dc < 7 ? (lumps[i] > 0.55 ? 'swamp' : 'dirt') : best.biome;
    G.obst[i] = null; G.road[i] = false;
  }
  // Lakes
  for (let k = rint(4, 6); k > 0; k--) {
    const cx = rint(4, W - 5), cy = rint(4, H - 5), r = rint(1, 3);
    if (sites.some(s => Math.hypot(s.x - cx, s.y - cy) < 7)) continue;
    for (let y = cy - r; y <= cy + r; y++) for (let x = cx - r; x <= cx + r; x++)
      if (inMap(x, y) && Math.hypot(x - cx, y - cy) <= r + Math.random() * 0.6) G.terr[idx(x, y)] = 'water';
  }
  // Forests & mountains
  const dens = valueNoise(W, H, 4);
  for (let i = 0; i < W * H; i++) {
    if (G.terr[i] === 'water') continue;
    const x = i % W, y = (i / W) | 0;
    if (x === 0 || y === 0 || x === W - 1 || y === H - 1) { G.obst[i] = 'rock'; continue; }
    if (dens[i] > 0.62 || Math.random() < 0.07) G.obst[i] = Math.random() < 0.7 ? 'tree' : 'rock';
  }
  const townSites = [...sites, { x: center[0], y: center[1], faction: null, biome: 'dirt' }];
  for (const s of townSites) for (let y = s.y - 2; y <= s.y + 2; y++) for (let x = s.x - 2; x <= s.x + 2; x++) {
    G.obst[idx(x, y)] = null; if (G.terr[idx(x, y)] === 'water') G.terr[idx(x, y)] = s.biome;
  }
  // Roads: each town to the centre, plus a ring between neighbouring corners.
  const links = sites.map(s => [s, townSites[4]]);
  links.push([sites[0], sites[1]], [sites[2], sites[3]]);
  for (const [a, b] of links) carveRoad(a, b);
  // Cull pockets the heroes could never reach.
  const reach = new Uint8Array(W * H), q = [idx(sites[0].x, sites[0].y)];
  reach[q[0]] = 1;
  while (q.length) {
    const i = q.pop(), x = i % W, y = (i / W) | 0;
    for (const [dx, dy] of N8) {
      const nx = x + dx, ny = y + dy, j = idx(nx, ny);
      if (inMap(nx, ny) && !reach[j] && passable(j)) { reach[j] = 1; q.push(j); }
    }
  }
  for (let i = 0; i < W * H; i++) if (!reach[i] && passable(i)) G.obst[i] = 'tree';

  // Towns & heroes
  sites.forEach((s, i) => {
    const t = makeTown(s.x, s.y, s.faction || pick(FACTION_KEYS), s.faction ? i : null);
    if (!s.faction) { t.garrison = monsterGroup(0.55, 2).units; t.built.push('d2', 'd3'); }
    G.objs.push(t);
    if (s.faction) {
      const p = G.players[i];
      const F = FACTIONS[p.faction];
      const h = { id: i, owner: p.id, unit: makeUnit(F.hero, 1), army: [], x: s.x, y: s.y, mp: BASE_MP, artifacts: [], shrines: [], shrineBonus: {}, alive: true, respawn: 0 };
      h.army.push(makeUnit(F.units[0], 2), makeUnit(F.units[0]), makeUnit(F.units[1], 2), makeUnit(F.units[1]), makeUnit(F.units[2]));
      G.heroes.push(h);
    }
  });
  const mid = makeTown(center[0], center[1], pick(FACTION_KEYS), null);
  mid.garrison = monsterGroup(0.85, 3).units; mid.built.push('d2', 'd3', 'd4', 'hall2');
  G.objs.push(mid);
  rebuildIndex();

  const danger = (x, y) => clamp(Math.min(...sites.filter(s => s.faction).map(s => Math.hypot(s.x - x, s.y - y))) / 24, 0, 1);
  const place = (obj, near, rmin, rmax, opts = {}) => {
    for (let tries = 0; tries < 400; tries++) {
      const x = near ? near.x + rint(-rmax, rmax) : rint(1, W - 2), y = near ? near.y + rint(-rmax, rmax) : rint(1, H - 2);
      if (!inMap(x, y)) continue;
      const i = idx(x, y);
      if (!passable(i) || !reach[i] || G.objAt.has(i) || G.guard.has(i)) continue;
      if (G.road[i] && !opts.road) continue;
      if (near && Math.hypot(near.x - x, near.y - y) < rmin) continue;
      if (townSites.some(s => Math.hypot(s.x - x, s.y - y) < (opts.townGap ?? 3))) continue;
      if (N8.some(([dx, dy]) => G.objAt.has(idx(x + dx, y + dy)))) continue;
      if (opts.minDanger != null && danger(x, y) < opts.minDanger) continue;
      Object.assign(obj, { id: G.nextId++, x, y });
      G.objs.push(obj); rebuildIndex();
      return obj;
    }
    return null;
  };
  const guard = (obj, d, n) => {
    if (!obj) return;
    for (const [dx, dy] of shuffle(N8.slice())) {
      const x = obj.x + dx, y = obj.y + dy, i = idx(x, y);
      if (inMap(x, y) && passable(i) && !G.objAt.has(i) && !heroAtIdx(i)) {
        const m = monsterGroup(d, n); Object.assign(m, { id: G.nextId++, x, y });
        G.objs.push(m); rebuildIndex(); return;
      }
    }
  };
  for (const s of sites) {
    place({ kind: 'mine', res: 'wood', owner: null }, s, 3, 6);
    place({ kind: 'mine', res: 'stone', owner: null }, s, 3, 6);
    place({ kind: 'mine', res: 'gold', owner: null }, s, 5, 9);
    for (let k = 0; k < 3; k++) place({ kind: 'pile', res: pick(['gold', 'wood', 'stone']), amt: 0 }, s, 2, 6);
  }
  for (let k = 0; k < 3; k++) guard(place({ kind: 'mine', res: 'ichor', owner: null }, null, 0, 0, { minDanger: 0.45 }), 0.7, 2);
  for (let k = 0; k < 2; k++) guard(place({ kind: 'mine', res: 'gold', owner: null }, null, 0, 0, { minDanger: 0.35 }), 0.5, 1);
  for (const id of shuffle(Object.keys(ARTIFACTS)).slice(0, 7)) guard(place({ kind: 'artifact', art: id }, null, 0, 0, { minDanger: 0.3 }), 0.6 + Math.random() * 0.4, 2);
  for (let k = 0; k < 7; k++) place({ kind: 'shrine', si: rnd(SHRINES.length) }, null, 0, 0, { minDanger: 0.15 });
  for (let k = 0; k < 12; k++) place({ kind: 'chest' }, null, 0, 0, {});
  for (let k = 0; k < 26; k++) place({ kind: 'pile', res: pick(['gold', 'gold', 'wood', 'stone', 'ichor']), amt: 0 }, null, 0, 0, {});
  for (let k = 0; k < 26; k++) {
    const m = { ...monsterGroup(0, 1) };
    const o = place(m, null, 0, 0, { road: true, townGap: 5, minDanger: 0.18 });
    if (o) { const g = monsterGroup(danger(o.x, o.y), 1); o.units = g.units; o.name = g.name; }
  }
  for (const o of G.objs) {
    if (o.kind === 'pile') o.amt = o.res === 'gold' ? rint(5, 10) * 100 : o.res === 'ichor' ? rint(1, 3) : rint(4, 8);
    if (o.kind === 'chest') { o.gold = rint(10, 20) * 100; o.xp = rint(4, 8) * 10; }
  }
}
function carveRoad(a, b) {
  const { W, H } = G;
  const dist = new Float64Array(W * H).fill(1e9), prev = new Int32Array(W * H).fill(-1), h = new Heap();
  const s = idx(a.x, a.y), e = idx(b.x, b.y);
  dist[s] = 0; h.push(s, 0);
  while (h.size) {
    const i = h.pop(); if (i === e) break;
    const x = i % W, y = (i / W) | 0;
    for (const [dx, dy] of N8.slice(0, 4)) {
      const nx = x + dx, ny = y + dy; if (nx < 1 || ny < 1 || nx >= W - 1 || ny >= H - 1) continue;
      const j = idx(nx, ny);
      const c = G.road[j] ? 0.5 : G.terr[j] === 'water' ? 25 : G.obst[j] ? 6 : 1 + Math.random() * 0.5;
      if (dist[i] + c < dist[j]) { dist[j] = dist[i] + c; prev[j] = i; h.push(j, dist[j] + Math.hypot(nx - b.x, ny - b.y)); }
    }
  }
  for (let i = e; i !== -1 && i !== s; i = prev[i]) {
    G.road[i] = true; G.obst[i] = null;
    if (G.terr[i] === 'water') G.terr[i] = 'dirt';
  }
  G.road[s] = true;
}

function makeTown(x, y, faction, owner) {
  const t = { id: G.nextId++, kind: 'town', x, y, faction, owner, name: owner != null ? FACTIONS[faction].town : NEUTRAL_TOWNS.splice(rnd(NEUTRAL_TOWNS.length), 1)[0] || 'Free City', built: ['d1'], pool: {}, garrison: [], builtToday: false };
  t.pool.d1 = TIER_GROWTH[1] * 2;
  return t;
}
// A neutral creature stack for a given danger (0 = near a capital, 1 = far).
function monsterGroup(danger, size = 1) {
  const tiers = danger < 0.3 ? [1, 2] : danger < 0.5 ? [2, 3, 4] : danger < 0.75 ? [3, 4, 5] : [5, 6, 7];
  const mercs = danger >= 0.3 && Math.random() < 0.2;
  const pool = mercs ? FACTION_KEYS.flatMap(f => FACTIONS[f].units).filter(id => tiers.includes(UNITS[id].tier) && UNITS[id].weapon !== 'staff')
    : NEUTRAL_UNITS.filter(id => tiers.includes(UNITS[id].tier));
  const lead = pick(pool), T = UNITS[lead];
  const lvl = 1 + Math.round(danger * danger * 6) + (G ? Math.max(0, G.difficulty - 1) : 0);
  const n = clamp(Math.round((5.5 - T.tier * 0.6) * (0.5 + Math.random() * 0.5) * (0.8 + size * 0.25)), 1, 8);
  const units = [];
  for (let k = 0; k < n; k++) units.push(makeUnit(k > 0 && Math.random() < 0.3 ? pick(pool) : lead, lvl));
  return { kind: 'monster', units, name: mercs ? `${T.name} Mercenaries` : (T.group || T.name) };
}

// ── Fog of war ──────────────────────────────────────────────────────────────
function reveal(x, y, r) {
  for (let yy = y - r; yy <= y + r; yy++) for (let xx = x - r; xx <= x + r; xx++)
    if (inMap(xx, yy) && Math.hypot(xx - x, yy - y) <= r + 0.5) G.fog[idx(xx, yy)] = 1;
}
const revealAround = h => h && reveal(h.x, h.y, 6);

// ── Pathfinding (8-directional, H3 guard zones) ─────────────────────────────
function stepCost(i, j) {
  const base = G.road[j] && G.road[i] ? ROAD_COST : TERRAIN[G.terr[j]].cost;
  const diag = (i % G.W !== j % G.W) && (((i / G.W) | 0) !== ((j / G.W) | 0));
  return diag ? Math.round(base * 1.41) : base;
}
// Dijkstra from a hero. Tiles holding objects/heroes and guard zones are
// end points: you can step onto them but not through them.
function heroDijkstra(h, goal = -1) {
  const n = G.W * G.H, dist = new Float64Array(n).fill(Infinity), prev = new Int32Array(n).fill(-1), heap = new Heap();
  const s = idx(h.x, h.y);
  dist[s] = 0; heap.push(s, 0);
  while (heap.size) {
    const i = heap.pop();
    if (i === goal) break;
    const x = i % G.W, y = (i / G.W) | 0;
    let onlyInto = null;
    if (i !== s) {
      const z = G.guard.get(i);
      if (G.objAt.has(i) || heroAtIdx(i)) continue;
      if (z) onlyInto = idx(z.x, z.y);
    }
    for (const [dx, dy] of N8) {
      const nx = x + dx, ny = y + dy;
      if (!inMap(nx, ny)) continue;
      const j = idx(nx, ny);
      if (onlyInto != null && j !== onlyInto) continue;
      if (!passable(j)) continue;
      if (dx && dy && (!passable(idx(x + dx, y)) || !passable(idx(x, y + dy)))) continue;
      const nd = dist[i] + stepCost(i, j);
      if (nd < dist[j]) { dist[j] = nd; prev[j] = i; heap.push(j, nd); }
    }
  }
  return { dist, prev, start: s };
}
function pathFrom(dj, goal) {
  if (!isFinite(dj.dist[goal])) return null;
  const p = [];
  for (let i = goal; i !== dj.start; i = dj.prev[i]) p.unshift(i);
  return p;
}

// ── Movement & interaction ──────────────────────────────────────────────────
// Walk a hero along a path. Returns when the hero stops (out of MP, reached
// something, or fought).
async function walkHero(h, path, animate) {
  let prev = idx(h.x, h.y);
  for (let k = 0; k < path.length; k++) {
    const i = path[k], c = stepCost(prev, i);
    if (c > h.mp) break;
    const occupant = heroAtIdx(i);
    if (occupant && occupant !== h) {          // bump into a hero
      h.mp = Math.max(0, h.mp - c);
      const t = G.objAt.get(i);
      if (t && t.kind === 'town' && t.owner === occupant.owner) await siegeTown(h, t);
      else await battleHeroes(h, occupant);
      return;
    }
    h.mp -= c; h.x = i % G.W; h.y = (i / G.W) | 0; prev = i;
    if (h.owner === 0) { revealAround(h); }
    if (animate) { followHero(h); requestDraw(); await sleep(55); }
    const g = G.guard.get(i), here = G.objAt.get(i);
    if (here && here.kind === 'monster') { await fightMonster(h, here); return; }
    if (g) { const won = await fightMonster(h, g); if (!won || !h.alive || !here) return; }
    if (here) { await interact(h, here); return; }
  }
}

async function interact(h, o) {
  const p = playerOf(h.owner), me = h.owner === 0;
  switch (o.kind) {
    case 'pile':
      p.res[o.res] += o.amt;
      if (me) toast(`Found ${RES_INFO[o.res].icon} ${o.amt} ${RES_INFO[o.res].name}`);
      removeObj(o);
      break;
    case 'chest':
      if (me) {
        const choice = await choiceModal('Treasure Chest', `You find a chest full of treasure. Keep the gold, or share the spoils with your troops for experience?`,
          [[`${RES_INFO.gold.icon} ${o.gold} gold`, 'gold'], [`⭐ +${o.xp} XP to every unit`, 'xp']]);
        if (choice === 'xp') giveArmyXp(h, o.xp); else p.res.gold += o.gold;
      } else p.res.gold += o.gold;
      removeObj(o);
      break;
    case 'artifact': {
      const A = ARTIFACTS[o.art];
      h.artifacts.push(o.art);
      if (me) modal(`${A.icon} ${A.name}`, el('p', null, `Your hero claims ${A.name}! `, el('b', null, A.desc)), [['Glorious', null]]);
      else if (G.fog[idx(o.x, o.y)]) log(`${FACTIONS[p.faction].name} claimed ${A.name}.`);
      removeObj(o);
      break;
    }
    case 'shrine': {
      const S = SHRINES[o.si];
      if (h.shrines.includes(o.id)) { if (me) toast(`${S.name}: you have already been blessed here.`); break; }
      h.shrines.push(o.id);
      h.shrineBonus[S.stat] = (h.shrineBonus[S.stat] || 0) + S.val;
      if (me) modal(S.name, el('p', null, `The gods bless your hero: `, el('b', null, `+${S.val} ${STAT_NAMES[S.stat]}`), ' (permanent).'), [['Praise be', null]]);
      break;
    }
    case 'mine':
      if (o.owner !== h.owner) {
        const prevOwner = o.owner;
        o.owner = h.owner;
        if (me) { toast(`${MINE_INFO[o.res].icon} ${MINE_INFO[o.res].name} captured: +${MINE_INFO[o.res].amt} ${RES_INFO[o.res].name}/day`); reveal(o.x, o.y, 3); }
        else if (prevOwner === 0) log(`⚠️ ${FACTIONS[p.faction].name} seized your ${MINE_INFO[o.res].name}!`);
      }
      break;
    case 'town':
      if (o.owner === h.owner) {
        absorbGarrison(h, o, !me);
        if (me) openTown(o);
      } else await siegeTown(h, o);
      break;
  }
  requestDraw(); refreshPanel();
}
function giveArmyXp(h, xp) {
  const lines = [];
  for (const u of [h.unit, ...h.army]) for (const g of gainXp(u, xp))
    lines.push(`${UNITS[u.type].icon} ${UNITS[u.type].name} → Lv ${u.lvl} (${Object.keys(g).map(s => STAT_NAMES[s] + '+1').join(' ')})`);
  if (h.owner === 0) toast(lines.length ? lines.join('<br>') : `+${xp} XP to the army`);
}
function absorbGarrison(h, t, auto) {
  if (!auto) return;
  t.garrison.sort((a, b) => unitPower(b) - unitPower(a));
  while (t.garrison.length && h.army.length < ARMY_CAP) h.army.push(t.garrison.shift());
}

// ── Battles on the adventure map ────────────────────────────────────────────
// A "force" is { units, lead, hero, owner, theme }.
function heroForce(h) { return { units: h.army, lead: h.unit, hero: h, owner: h.owner }; }
function townForce(t) {
  const h = heroAtIdx(idx(t.x, t.y));
  const defender = h && h.owner === t.owner ? h : null;
  return { units: defender ? [...defender.army, ...t.garrison].slice(0, 12) : t.garrison, lead: defender ? defender.unit : null, hero: defender, owner: t.owner, town: t };
}
const themeAt = (x, y) => G.terr[idx(x, y)] === 'water' ? 'grass' : G.terr[idx(x, y)];

// Resolve a fight between attacker force a and defender force d.
// Returns true if the attacker won.
async function resolveFight(a, d, { title, theme, siege }) {
  const aHuman = a.owner === 0, dHuman = d.owner === 0;
  const aUnits = a.units.filter(u => u.hp > 0), dUnits = d.units.filter(u => u.hp > 0);
  let attackerWon;
  if (!dUnits.length && !d.lead) attackerWon = true;
  else if (!aUnits.length && !a.lead) attackerWon = false;
  else if (aHuman || dHuman) {
    const P = aHuman ? a : d, E = aHuman ? d : a;
    const pTowns = townsOf(human());
    const power = P.hero ? FACTIONS[playerOf(P.owner).faction].power : null;
    const uses = power ? (pTowns.some(t => t.built.includes('temple')) ? 2 : 1) : 0;
    const res = await startBattle({
      title, theme,
      siege: siege ? (dHuman ? 'player' : 'enemy') : null,
      player: { units: P.units.filter(u => u.hp > 0), lead: P.lead, hero: P.hero, power, powerUses: uses },
      enemy: { units: E.units.filter(u => u.hp > 0), lead: E.lead, hero: E.hero },
    });
    showScreen('campaign');
    attackerWon = aHuman ? res.win : !res.win;
  } else {
    attackerWon = autoResolve(a, d);
  }
  // Clean up the dead and patch up the living.
  for (const f of [a, d]) {
    const winner = (f === a) === attackerWon;
    if (!winner) { for (const u of f.units) u.hp = 0; }
    if (f.hero) f.hero.army = f.hero.army.filter(u => u.hp > 0);
    if (f.town) f.town.garrison = f.town.garrison.filter(u => u.hp > 0);
    if (f.obj) f.obj.units = f.obj.units.filter(u => u.hp > 0);
    for (const u of f.units) if (u.hp > 0) u.hp = u.stats.hp;
    if (f.lead) f.lead.hp = f.lead.stats.hp;
  }
  if (!attackerWon && a.hero) defeatHero(a.hero);
  if (attackerWon && d.hero) defeatHero(d.hero);
  requestDraw(); refreshPanel();
  return attackerWon;
}
function autoResolve(a, d) {
  const A = [...a.units.filter(u => u.hp > 0), ...(a.lead ? [a.lead] : [])];
  const D = [...d.units.filter(u => u.hp > 0), ...(d.lead ? [d.lead] : [])];
  const pa = armyPower(A) * (1 + (a.hero ? a.hero.artifacts.length * 0.05 : 0));
  const pd = armyPower(D) * (1 + (d.hero ? d.hero.artifacts.length * 0.05 : 0)) * (d.town && d.town.built.includes('walls') ? 1.25 : 1);
  const aWins = Math.random() < pa * pa / (pa * pa + pd * pd);
  const [W, Wp, Lp] = aWins ? [a, pa, pd] : [d, pd, pa];
  const loss = clamp(Lp / Wp * 0.6, 0, 0.9) * Wp;
  let removed = 0;
  for (const u of shuffle(W.units.filter(u => u.hp > 0))) {
    if (removed >= loss) break;
    if (Math.random() < 0.6) { removed += unitPower(u); u.hp = 0; }
  }
  for (const u of [...W.units, ...(W.lead ? [W.lead] : [])]) if (u.hp > 0) gainXp(u, 25);
  return aWins;
}
async function fightMonster(h, m) {
  const won = await resolveFight(heroForce(h), { units: m.units, lead: null, hero: null, owner: null, obj: m },
    { title: `${heroName(h)} vs ${m.name}`, theme: themeAt(m.x, m.y) });
  if (won) {
    removeObj(m);
    if (h.owner === 0) log(`Your army defeated the ${m.name}.`);
  } else {
    m.units = m.units.filter(u => u.hp > 0);
    if (!m.units.length) removeObj(m);
  }
  return won;
}
async function battleHeroes(a, d) {
  const title = `${heroName(a)} attacks ${heroName(d)}`;
  if (d.owner === 0) toast(`⚠️ ${heroName(a)} is attacking you!`);
  const won = await resolveFight(heroForce(a), heroForce(d), { title, theme: themeAt(d.x, d.y) });
  if (a.owner === 0 || d.owner === 0) log(won ? `${heroName(a)} defeated ${heroName(d)}.` : `${heroName(d)} repelled ${heroName(a)}.`);
}
async function siegeTown(h, t) {
  const prevOwner = t.owner;
  const f = townForce(t);
  if (f.hero && f.hero.owner === h.owner) return;
  const title = `Siege of ${t.name}`;
  if (prevOwner === 0) toast(`⚠️ ${heroName(h)} is besieging ${t.name}!`);
  const won = await resolveFight(heroForce(h), f, { title, theme: themeAt(t.x, t.y), siege: t.built.includes('walls') });
  if (!won) return;
  t.owner = h.owner;
  t.garrison = [];
  h.x = t.x; h.y = t.y;
  rebuildIndex();
  const p = playerOf(h.owner);
  if (h.owner === 0) {
    reveal(t.x, t.y, 5);
    modal(`${t.name} is yours!`, el('p', null, `The banners of ${FACTIONS[p.faction].name} fly over ${t.name}. You may now build and recruit ${FACTIONS[t.faction].adj} units here.`), [['Enter town', () => openTown(t)], ['Later', null]]);
  } else {
    log(prevOwner === 0 ? `⚠️ ${FACTIONS[p.faction].name} captured your town of ${t.name}!` : `${FACTIONS[p.faction].name} captured ${t.name}.`);
  }
}
function defeatHero(h) {
  h.alive = false; h.army = []; h.respawn = 2; h.mp = 0;
  if (h.owner === 0) {
    log(`💀 ${heroName(h)} was defeated and fled the field.`);
    toast(`${heroName(h)} has been defeated! They will return to one of your towns in 2 days.`);
  } else log(`${heroName(h)} has been defeated.`);
}
const heroName = h => UNITS[h.unit.type].name;

// ── Towns: building & recruiting (shared by player and AI) ──────────────────
const dwellingTier = b => +b.slice(1);
function buildingName(t, b) {
  if (b[0] === 'd') return FACTIONS[t.faction].dwellings[dwellingTier(b) - 1];
  if (b === 'temple') return FACTIONS[t.faction].temple;
  return BUILDINGS[b].name;
}
function canBuild(t, b) {
  const p = playerOf(t.owner);
  if (t.built.includes(b)) return 'Built';
  if (t.builtToday) return 'Already built today';
  const miss = BUILDINGS[b].req.filter(r => !t.built.includes(r));
  if (miss.length) return 'Requires ' + miss.map(r => buildingName(t, r)).join(', ');
  if (!canAfford(p.res, BUILDINGS[b].cost)) return 'Not enough resources';
  return null;
}
function build(t, b) {
  const p = playerOf(t.owner);
  if (canBuild(t, b)) return false;
  pay(p.res, BUILDINGS[b].cost);
  t.built.push(b); t.builtToday = true;
  if (b[0] === 'd') t.pool[b] = (t.pool[b] || 0) + growthOf(t, dwellingTier(b));
  return true;
}
const growthOf = (t, tier) => Math.ceil(TIER_GROWTH[tier] * (t.built.includes('citadel') ? 1.5 : 1));
function recruit(t, tier, dest) {
  const p = playerOf(t.owner), type = FACTIONS[t.faction].units[tier - 1], key = 'd' + tier;
  const cost = TIER_COST[tier];
  if (!t.built.includes(key) || !(t.pool[key] > 0) || !canAfford(p.res, cost) || dest.length >= (dest === t.garrison ? GARRISON_CAP : ARMY_CAP)) return null;
  pay(p.res, cost); t.pool[key]--;
  const u = makeUnit(type, 1);
  dest.push(u);
  return u;
}
function townIncome(t) { return t.built.includes('hall3') ? 2000 : t.built.includes('hall2') ? 1000 : 500; }

// ── Day cycle ───────────────────────────────────────────────────────────────
async function endTurn() {
  if (!G || G.busy || G.over) return;
  G.busy = true; G.path = null;
  refreshPanel();
  try {
    for (const p of G.players.slice(1)) if (p.alive) await aiTurn(p);
    newDay();
  } finally { G.busy = false; }
  refreshPanel(); requestDraw();
}
function newDay() {
  G.day++;
  const week = (G.day - 1) % 7 === 0;
  for (const p of G.players) {
    if (!p.alive) continue;
    const towns = townsOf(p);
    let gold = 0;
    for (const t of towns) { gold += townIncome(t); if (t.built.includes('temple')) p.res.ichor += 1; }
    for (const o of G.objs) if (o.kind === 'mine' && o.owner === p.id) {
      if (o.res === 'gold') gold += MINE_INFO.gold.amt; else p.res[o.res] += MINE_INFO[o.res].amt;
    }
    const h = heroOf(p);
    if (h) for (const a of h.artifacts) { const inc = ARTIFACTS[a].income; if (inc) for (const [k, v] of Object.entries(inc)) k === 'gold' ? gold += v : p.res[k] += v; }
    if (!p.human) gold = Math.round(gold * (1 + G.difficulty * 0.25));
    p.res.gold += gold;
  }
  for (const o of G.objs) if (o.kind === 'town') {
    o.builtToday = false;
    if (week) for (const b of o.built) if (b[0] === 'd') o.pool[b] = (o.pool[b] || 0) + growthOf(o, dwellingTier(b));
  }
  if (week) for (const o of G.objs) if (o.kind === 'monster' && o.units.length < 10 && Math.random() < 0.5) o.units.push(makeUnit(o.units[0].type, o.units[0].lvl));
  for (const h of G.heroes) {
    h.mp = BASE_MP + h.artifacts.reduce((s, a) => s + (ARTIFACTS[a].mp || 0), 0);
    if (!h.alive) {
      h.respawn--;
      const towns = townsOf(playerOf(h.owner));
      const home = towns.find(t => !heroAtIdx(idx(t.x, t.y)));
      if (h.respawn <= 0 && home) {
        h.alive = true; h.x = home.x; h.y = home.y; h.unit.hp = h.unit.stats.hp;
        absorbGarrison(h, home, h.owner !== 0);
        if (h.owner === 0) { log(`${heroName(h)} returns to ${home.name}.`); revealAround(h); followHero(h, true); }
      }
    }
  }
  // Elimination & victory.
  for (const p of G.players) {
    if (!p.alive) continue;
    const towns = townsOf(p), h = heroOf(p);
    p.noTownDays = towns.length ? 0 : p.noTownDays + 1;
    if ((!towns.length && (!h || !h.alive)) || p.noTownDays >= 7) {
      p.alive = false;
      if (h) { h.alive = false; h.respawn = 1e9; }
      if (!p.human) log(`🏴 ${FACTIONS[p.faction].name} have been wiped from the world!`);
    }
  }
  const me = human();
  if (!me.alive) return gameOver(false);
  if (G.players.slice(1).every(p => !p.alive)) return gameOver(true);
  if (me.noTownDays > 0) toast(`⚠️ You have no towns! ${7 - me.noTownDays} days left to capture one.`);
  if (week) modal(`Week ${Math.floor(((G.day - 1) % 28) / 7) + 1} begins`, el('p', null, 'Creatures in every dwelling have multiplied. Wandering monsters grow bolder.'), [['Onward', null]]);
  else toast(dateText(G.day));
  autosave();
}
function gameOver(win) {
  G.over = true;
  try { localStorage.removeItem('pantheon_autosave'); } catch (e) { /* storage may be blocked */ }
  modal(win ? '🏆 Victory!' : '💀 Defeat', el('p', null, win
    ? `The rival pantheons have fallen. ${FACTIONS[human().faction].god} reigns supreme after ${G.day} days.`
    : 'Your gods have abandoned you. Your realm is lost.'), [['Main menu', () => showMainMenu()]], { noClose: true, cls: win ? 'win' : 'lose' });
}

// ── Computer players ────────────────────────────────────────────────────────
async function aiTurn(p) {
  for (const t of townsOf(p)) aiTown(p, t);
  const h = heroOf(p);
  if (h && h.alive) await aiHero(h);
}
function aiTown(p, t) {
  const hasMarket = townsOf(p).some(x => x.built.includes('market'));
  for (const b of BUILD_ORDER) {
    if (t.built.includes(b) || t.builtToday) continue;
    if (BUILDINGS[b].req.some(r => !t.built.includes(r))) continue;
    // Buy missing wood/stone/ichor at the market rather than sit on gold.
    const cost = BUILDINGS[b].cost;
    if (hasMarket) {
      let extra = 0;
      for (const r of ['wood', 'stone', 'ichor']) extra += Math.max(0, (cost[r] || 0) - p.res[r]) * MARKET[r].buy;
      if (extra && p.res.gold >= (cost.gold || 0) + extra + 1000) {
        for (const r of ['wood', 'stone', 'ichor']) { const need = Math.max(0, (cost[r] || 0) - p.res[r]); p.res[r] += need; p.res.gold -= need * MARKET[r].buy; }
      }
    }
    if (!canBuild(t, b)) { build(t, b); break; }
  }
  const h = heroOf(p), heroHere = h && h.alive && h.x === t.x && h.y === t.y;
  for (let tier = 7; tier >= 1; tier--) {
    for (let guard = 0; guard < 10; guard++) {
      const dest = heroHere && h.army.length < ARMY_CAP ? h.army : t.garrison;
      if (!recruit(t, tier, dest)) break;
    }
  }
  if (heroHere) absorbGarrison(h, t, true);
}
function aiTargetValue(h, o, myPow) {
  const p = playerOf(h.owner);
  switch (o.kind) {
    case 'pile': return o.res === 'ichor' ? 5 : 3;
    case 'chest': return 5;
    case 'artifact': return 9;
    case 'shrine': return h.shrines.includes(o.id) ? 0 : 4;
    case 'mine': return o.owner === p.id ? 0 : o.res === 'ichor' ? 7 : o.res === 'gold' ? 7 : 4;
    case 'monster': return myPow > armyPower(o.units) * 1.6 ? 3 + UNITS[o.units[0].type].tier : 0;
    case 'town': {
      if (o.owner === p.id) {
        const gp = armyPower(o.garrison);
        return h.army.length < ARMY_CAP && gp > 0 ? 3 + gp / 40 : 0;
      }
      const f = townForce(o), dp = armyPower(f.units) + (f.lead ? unitPower(f.lead) : 0);
      return myPow > dp * 1.4 ? (o.owner == null ? 14 : 22) : 0;
    }
  }
  return 0;
}
async function aiHero(h) {
  for (let iter = 0; iter < 5 && h.alive && h.mp > 0; iter++) {
    const myPow = armyPower(h.army) + unitPower(h.unit);
    const dj = heroDijkstra(h);
    let best = null;
    const consider = (i, v) => {
      if (v <= 0 || !isFinite(dj.dist[i]) || i === dj.start) return;
      const z = G.guard.get(i), o = G.objAt.get(i);
      if (z && z !== o && myPow < armyPower(z.units) * 1.6) return; // guarded and too strong
      const score = v / (dj.dist[i] / 100 + 1.5);
      if (!best || score > best.score) best = { i, score };
    };
    for (const o of G.objs) consider(idx(o.x, o.y), aiTargetValue(h, o, myPow));
    for (const e of G.heroes) {
      if (e === h || !e.alive || e.owner === h.owner) continue;
      const ep = armyPower(e.army) + unitPower(e.unit);
      if (myPow > ep * 1.35) consider(idx(e.x, e.y), 16);
    }
    if (!best) break;
    const path = pathFrom(dj, best.i);
    if (!path || !path.length) break;
    const before = h.mp;
    const visible = G.fog[best.i] && G.fog[idx(h.x, h.y)];
    await walkHero(h, path, false);
    if (visible) requestDraw();
    if (h.mp === before) break;
  }
}

// ── Log ─────────────────────────────────────────────────────────────────────
function log(msg) {
  G.log.unshift(`<span class="day">D${G.day}</span> ${msg}`);
  G.log.length = Math.min(G.log.length, 60);
  refreshLog();
}
