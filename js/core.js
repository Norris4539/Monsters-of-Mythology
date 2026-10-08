'use strict';
// ─────────────────────────────────────────────────────────────────────────────
// Helpers, stacks and the Heroes 3 damage rules shared by both maps.
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

// ── Stacks ──────────────────────────────────────────────────────────────────
// A stack is { uid, type, n, hp }: n creatures, the top one at hp health.
let UID = 1;
function makeStack(type, n) { return { uid: UID++, type, n: Math.max(1, Math.round(n)), hp: UNITS[type].hp }; }
const stackHp = s => s.n > 0 ? (s.n - 1) * UNITS[s.type].hp + s.hp : 0;
function setStackHp(s, total, maxN = Infinity) {
  const H = UNITS[s.type].hp;
  total = Math.max(0, Math.min(total, maxN * H));
  s.n = Math.ceil(total / H); s.hp = total - (s.n - 1) * H;
  if (s.n <= 0) { s.n = 0; s.hp = 0; }
}
// Adds n creatures of a type to a list of stacks, merging with a matching stack.
function addToArmy(list, type, n, slots) {
  const same = list.find(s => s.type === type);
  if (same) { same.n += n; return same; }
  if (list.length >= slots) return null;
  const s = makeStack(type, n); list.push(s); return s;
}

// Hero stats with artifacts and shrine blessings.
function heroStat(h, k) {
  if (!h) return 0;
  let v = h[k] || 0;
  for (const id of h.artifacts || []) { const A = ARTIFACTS[id]; if (A.hero && A.hero[k]) v += A.hero[k]; }
  if (h.shrineBonus && h.shrineBonus[k]) v += h.shrineBonus[k];
  return v;
}
function armyArtifact(h, k) {
  let v = 0; if (!h) return v;
  for (const id of h.artifacts || []) { const A = ARTIFACTS[id]; if (A.army && A.army[k]) v += A.army[k]; }
  return v;
}

// ── Values used by the AI, auto-resolve and threat labels ───────────────────
// Fighting strength follows Lanchester's square law: sqrt(total health ×
// total damage), each scaled by Defence and Attack.
function creatureValue(T) {
  return Math.sqrt(effHp(T) * effDmg(T));
}
const effHp = T => T.hp * Math.pow(1.04, T.def) * (1 + T.res / 200) * (T.abil.includes('regrow') ? 1.15 : 1);
const effDmg = T => (T.dmg[0] + T.dmg[1]) / 2 * Math.pow(1.045, T.att) * (T.range[1] > 1 ? 1.25 : 1) * (T.abil.includes('manyHeads') || T.abil.includes('doubleStrike') ? 1.4 : 1);
const stackCount = s => s.n > 0 ? s.n - 1 + s.hp / UNITS[s.type].hp : 0;
const stackPower = s => creatureValue(UNITS[s.type]) * stackCount(s);
function armyPower(stacks, hero) {
  let hp = 0, dmg = 0;
  for (const s of stacks) { const n = stackCount(s), T = UNITS[s.type]; hp += n * effHp(T); dmg += n * effDmg(T); }
  return Math.sqrt(hp * dmg) * Math.pow(1.04, heroStat(hero, 'att') + heroStat(hero, 'def'));
}

function threatLabel(mine, theirs) {
  const r = theirs / Math.max(1, mine);
  if (r < 0.35) return ['Effortless', '#7ec27e'];
  if (r < 0.7) return ['Easy', '#a6d06a'];
  if (r < 1.0) return ['Fair fight', '#e2c25a'];
  if (r < 1.4) return ['Challenging', '#e8964a'];
  if (r < 2.0) return ['Deadly', '#e0603e'];
  return ['Impossible', '#d03a3a'];
}
function countLabel(n) {
  return n < 5 ? 'A few' : n < 10 ? 'Several' : n < 20 ? 'A pack of' : n < 50 ? 'Lots of' : n < 100 ? 'A horde of' : 'A throng of';
}

// ── Heroes 3 damage ─────────────────────────────────────────────────────────
// Base damage: one roll per creature (10 rolls scaled up for big stacks).
function rollBase(T, n, mode) {
  const [a, b] = T.dmg;
  if (mode === 'min') return a * n;
  if (mode === 'max') return b * n;
  if (mode === 'avg') return (a + b) / 2 * n;
  if (n <= 10) { let s = 0; for (let i = 0; i < n; i++) s += rint(a, b); return s; }
  let s = 0; for (let i = 0; i < 10; i++) s += rint(a, b); return s * n / 10;
}
// Attack vs Defence: +5% per point above (to ×4), −2.5% per point below (to ×0.3).
function attDefMod(att, def) {
  return att >= def ? 1 + Math.min(att - def, 60) * .05 : Math.max(.3, 1 - Math.min(def - att, 28) * .025);
}
function triangle(aw, dw) {
  const a = triGroup(aw), d = triGroup(dw);
  if (TRIANGLE[a] === d) return 1;
  if (TRIANGLE[d] === a) return -1;
  return 0;
}
