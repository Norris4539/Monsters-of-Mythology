'use strict';
// ─────────────────────────────────────────────────────────────────────────────
// Helpers, unit instances, levelling and combat maths shared by both maps.
// ─────────────────────────────────────────────────────────────────────────────

const rnd = n => Math.floor(Math.random() * n);
const rint = (a, b) => a + rnd(b - a + 1);
const pick = a => a[rnd(a.length)];
const chance = p => Math.random() * 100 < p;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = rnd(i + 1); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const cheb = (ax, ay, bx, by) => Math.max(Math.abs(ax - bx), Math.abs(ay - by));
const manh = (ax, ay, bx, by) => Math.abs(ax - bx) + Math.abs(ay - by);

// DOM helper: el('div', {className:'x', onClick: fn, style:{…}}, ...children)
function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'className') e.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(e.style, v);
    else if (k === 'html') e.innerHTML = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2).toLowerCase(), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) e.append(k instanceof Node ? k : document.createTextNode(k));
  return e;
}

// Binary min-heap for Dijkstra / A*.
class Heap {
  constructor() { this.a = []; }
  get size() { return this.a.length; }
  push(v, p) {
    const a = this.a; a.push([p, v]);
    let i = a.length - 1;
    while (i > 0) { const j = (i - 1) >> 1; if (a[j][0] <= a[i][0]) break; [a[i], a[j]] = [a[j], a[i]]; i = j; }
  }
  pop() {
    const a = this.a, top = a[0], last = a.pop();
    if (a.length) {
      a[0] = last; let i = 0;
      for (;;) {
        const l = 2 * i + 1, r = l + 1; let m = i;
        if (l < a.length && a[l][0] < a[m][0]) m = l;
        if (r < a.length && a[r][0] < a[m][0]) m = r;
        if (m === i) break; [a[i], a[m]] = [a[m], a[i]]; i = m;
      }
    }
    return top[1];
  }
}

// ── Resources ───────────────────────────────────────────────────────────────
const canAfford = (res, cost) => Object.entries(cost).every(([k, v]) => (res[k] || 0) >= v);
const pay = (res, cost) => { for (const [k, v] of Object.entries(cost)) res[k] -= v; };
const costText = cost => Object.entries(cost).filter(([, v]) => v).map(([k, v]) => `${RES_INFO[k].icon}${v}`).join(' ') || 'free';

// ── Unit instances ──────────────────────────────────────────────────────────
let UID = 1;
function makeUnit(type, lvl = 1) {
  const T = UNITS[type];
  const u = { uid: UID++, type, lvl: 1, xp: 0, stats: { ...T.base }, hp: T.base.hp };
  while (u.lvl < lvl) levelUp(u);
  u.hp = u.stats.hp;
  return u;
}
function levelUp(u) {
  const T = UNITS[u.type], gains = {};
  for (const s of STATS) if (chance(T.growth[s])) { u.stats[s]++; gains[s] = 1; }
  if (!Object.keys(gains).length) { const s = pick(['hp', 'str', 'skl', 'spd', 'def']); u.stats[s]++; gains[s] = 1; }
  if (gains.hp) u.hp++;
  u.lvl++;
  return gains;
}
// Adds XP and returns an array of stat-gain objects (one per level gained).
function gainXp(u, amount) {
  const ups = [];
  if (u.lvl >= MAX_LEVEL) return ups;
  u.xp += Math.max(1, Math.round(amount));
  while (u.xp >= 100 && u.lvl < MAX_LEVEL) { u.xp -= 100; ups.push(levelUp(u)); }
  if (u.lvl >= MAX_LEVEL) u.xp = 0;
  return ups;
}

// Bonus stats from artifacts. `bonus` is attached to a unit just for battle.
const st = (u, s) => (u.stats[s] || 0) + ((u.bonus && u.bonus[s]) || 0);
const maxHp = u => st(u, 'hp');
function armyBonus(hero, forHero) {
  const b = {};
  if (!hero) return b;
  for (const id of hero.artifacts) {
    const A = ARTIFACTS[id];
    for (const src of [A.army, forHero && A.hero]) if (src) for (const [k, v] of Object.entries(src)) b[k] = (b[k] || 0) + v;
  }
  if (forHero && hero.shrineBonus) for (const [k, v] of Object.entries(hero.shrineBonus)) b[k] = (b[k] || 0) + v;
  return b;
}

// Rough strength rating used by the AI and for threat descriptions.
function unitPower(u) {
  const T = UNITS[u.type];
  const atk = (T.weapon === 'staff' ? st(u, 'mag') * 0.6 : Math.max(st(u, 'str'), st(u, 'mag')) + T.mt) * (T.abil.includes('brave') ? 1.6 : 1);
  return (u.hp + atk * 2.2 + st(u, 'def') + st(u, 'res') * 0.6 + st(u, 'spd') * 1.2 + st(u, 'skl') * 0.6) * (T.abil.includes('regen') ? 1.15 : 1);
}
const armyPower = units => units.reduce((s, u) => s + unitPower(u), 0);

function threatLabel(mine, theirs) {
  // Tuned against bot playtests: equal ratings are not an even fight, as the
  // defender's units gang up on yours.
  const r = theirs * 1.6 / Math.max(1, mine);
  if (r < 0.35) return ['Effortless', '#7ec27e'];
  if (r < 0.7) return ['Easy', '#a6d06a'];
  if (r < 1.0) return ['Fair fight', '#e2c25a'];
  if (r < 1.4) return ['Challenging', '#e8964a'];
  if (r < 2.0) return ['Deadly', '#e0603e'];
  return ['Impossible', '#d03a3a'];
}
function countLabel(n) {
  return n <= 1 ? 'A lone' : n <= 2 ? 'A pair of' : n <= 4 ? 'A few' : n <= 6 ? 'A pack of' : 'A horde of';
}

// ── Combat maths (Fire Emblem Awakening flavoured) ──────────────────────────
// a/d are battle combatants: { u, x, y, side, ... }
function triangle(aw, dw) {
  if (TRIANGLE[aw] === dw) return 1;
  if (TRIANGLE[dw] === aw) return -1;
  return 0;
}
function canAttackAt(T, dist) { return T.weapon !== 'staff' && dist >= T.range[0] && dist <= T.range[1]; }

// Compute one side's strike numbers against the other.
// ctx: { terr(x,y) -> BTER entry, support(c) -> bool }
function strikeStats(a, d, ax, ay, dx, dy, ctx) {
  const A = UNITS[a.u.type], D = UNITS[d.u.type], W = WEAPONS[A.weapon];
  const tri = triangle(A.weapon, D.weapon);
  const dT = ctx.terr(dx, dy), aSup = ctx.support(a, ax, ay), dSup = ctx.support(d, dx, dy);
  let mt = A.mt + tri;
  if (W.effective && D.move === W.effective) mt *= 3;
  const atk = (W.magic ? st(a.u, 'mag') : st(a.u, 'str')) + mt;
  let prot = (W.magic ? st(d.u, 'res') : st(d.u, 'def')) + dT.def;
  if (A.abil.includes('pierce')) prot = Math.floor(prot / 2);
  const dmg = Math.max(0, atk - prot);
  const hitRate = A.hit + st(a.u, 'skl') * 2 + Math.floor(st(a.u, 'lck') / 2) + tri * 15 + (aSup ? 10 : 0);
  const avoid = st(d.u, 'spd') * 2 + st(d.u, 'lck') + dT.avo + (dSup ? 10 : 0);
  const hit = clamp(hitRate - avoid, 0, 100);
  const crit = clamp(A.crit + Math.floor(st(a.u, 'skl') / 2) - st(d.u, 'lck'), 0, 100);
  const doubles = st(a.u, 'spd') - st(d.u, 'spd') >= 4;
  const brave = A.abil.includes('brave');
  return { dmg, hit, crit, doubles, brave, tri, eff: !!(W.effective && D.move === W.effective) };
}
