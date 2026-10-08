'use strict';
// ─────────────────────────────────────────────────────────────────────────────
// Adventure map rendering (canvas) and input: pan, hover, click-to-path,
// click-again-to-move, minimap.
// ─────────────────────────────────────────────────────────────────────────────

const TS = 40;
const V = { cx: 0, cy: 0, w: 0, h: 0, dpr: 1, layer: null, hover: null, drawQueued: false, drag: null };

function buildStaticLayer() {
  const c = document.createElement('canvas');
  c.width = G.W * TS; c.height = G.H * TS;
  const g = c.getContext('2d');
  g.textAlign = 'center'; g.textBaseline = 'middle';
  for (let y = 0; y < G.H; y++) for (let x = 0; x < G.W; x++) {
    const i = idx(x, y), T = TERRAIN[G.terr[i]], X = x * TS, Y = y * TS;
    g.fillStyle = T.color; g.fillRect(X, Y, TS, TS);
    g.fillStyle = T.dot;
    for (let k = 0; k < 5; k++) g.fillRect(X + ((x * 7 + y * 13 + k * 17) % 34) + 2, Y + ((x * 11 + y * 5 + k * 23) % 34) + 2, 3, 2);
    if (G.terr[i] === 'water') {
      g.strokeStyle = 'rgba(255,255,255,.18)'; g.lineWidth = 1.5;
      g.beginPath(); g.moveTo(X + 8, Y + 22); g.quadraticCurveTo(X + 14, Y + 16, X + 20, Y + 22); g.quadraticCurveTo(X + 26, Y + 28, X + 32, Y + 22); g.stroke();
    }
  }
  // Roads drawn as connected strokes.
  g.strokeStyle = '#c2a477'; g.lineWidth = 12; g.lineCap = 'round';
  for (let y = 0; y < G.H; y++) for (let x = 0; x < G.W; x++) {
    if (!G.road[idx(x, y)]) continue;
    const cx = x * TS + TS / 2, cy = y * TS + TS / 2;
    let any = false;
    for (const [dx, dy] of [[1, 0], [0, 1]]) if (inMap(x + dx, y + dy) && G.road[idx(x + dx, y + dy)]) {
      any = true; g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + dx * TS, cy + dy * TS); g.stroke();
    }
    if (!any) { g.beginPath(); g.arc(cx, cy, 6, 0, Math.PI * 2); g.fillStyle = '#c2a477'; g.fill(); }
  }
  for (let y = 0; y < G.H; y++) for (let x = 0; x < G.W; x++) {
    const i = idx(x, y), o = G.obst[i];
    if (!o) continue;
    const T = TERRAIN[G.terr[i]], list = o === 'tree' ? T.trees : T.rocks;
    g.font = `${o === 'tree' ? 30 : 32}px serif`;
    g.fillText(list[(x * 31 + y * 17) % list.length], x * TS + TS / 2 + ((x + y) % 3 - 1) * 2, y * TS + TS / 2 + 1);
  }
  V.layer = c;
}

function resizeMap() {
  const wrap = document.getElementById('mapwrap'), cv = document.getElementById('map');
  V.dpr = window.devicePixelRatio || 1;
  V.w = wrap.clientWidth; V.h = wrap.clientHeight;
  cv.width = V.w * V.dpr; cv.height = V.h * V.dpr;
  cv.style.width = V.w + 'px'; cv.style.height = V.h + 'px';
  clampCam(); requestDraw();
}
function clampCam() {
  V.cx = clamp(V.cx, -40, Math.max(-40, G.W * TS - V.w + 40));
  V.cy = clamp(V.cy, -40, Math.max(-40, G.H * TS - V.h + 40));
}
function centerOn(x, y) { V.cx = x * TS + TS / 2 - V.w / 2; V.cy = y * TS + TS / 2 - V.h / 2; clampCam(); requestDraw(); }
function followHero(h, force) {
  const sx = h.x * TS - V.cx, sy = h.y * TS - V.cy, m = 3 * TS;
  if (force || sx < m || sy < m || sx > V.w - m || sy > V.h - m) centerOn(h.x, h.y);
}
function requestDraw() {
  if (V.drawQueued || !G) return;
  V.drawQueued = true;
  requestAnimationFrame(() => { V.drawQueued = false; drawMap(); drawMinimap(); });
}

function drawObj(g, o, X, Y) {
  const cx = X + TS / 2, cy = Y + TS / 2;
  g.textAlign = 'center'; g.textBaseline = 'middle';
  if (o.kind === 'town') {
    g.fillStyle = 'rgba(0,0,0,.35)'; g.fillRect(X - 6, Y - 6, TS + 12, TS + 12);
    g.fillStyle = colorOf(o.owner); g.fillRect(X - 4, Y - 4, TS + 8, TS + 8);
    g.fillStyle = '#f4ead2'; g.fillRect(X - 1, Y - 1, TS + 2, TS + 2);
    g.font = '32px serif'; g.fillText(FACTIONS[o.faction].townIcon, cx, cy + 1);
    g.font = 'bold 11px system-ui, sans-serif'; g.fillStyle = '#fff'; g.strokeStyle = 'rgba(0,0,0,.8)'; g.lineWidth = 3;
    g.strokeText(o.name, cx, Y + TS + 12); g.fillText(o.name, cx, Y + TS + 12);
    return;
  }
  if (o.kind === 'monster') {
    g.beginPath(); g.arc(cx, cy, 16, 0, Math.PI * 2); g.fillStyle = 'rgba(120,20,20,.55)'; g.fill();
    g.font = '26px serif'; g.fillText(UNITS[o.units[0].type].icon, cx, cy + 1);
    g.font = 'bold 11px system-ui, sans-serif'; g.fillStyle = '#fff';
    g.beginPath(); g.arc(X + TS - 6, Y + TS - 6, 8, 0, Math.PI * 2); g.fillStyle = '#7a1b1b'; g.fill();
    g.fillStyle = '#fff'; g.fillText(o.units.length, X + TS - 6, Y + TS - 5);
    return;
  }
  let icon = '?';
  if (o.kind === 'mine') icon = MINE_INFO[o.res].icon;
  if (o.kind === 'pile') icon = RES_INFO[o.res].icon;
  if (o.kind === 'chest') icon = '💰';
  if (o.kind === 'shrine') icon = '🛐';
  if (o.kind === 'artifact') {
    g.beginPath(); g.arc(cx, cy, 15, 0, Math.PI * 2); g.fillStyle = 'rgba(255,220,90,.45)'; g.fill();
    icon = ARTIFACTS[o.art].icon;
  }
  if (o.kind === 'mine') {
    g.fillStyle = 'rgba(0,0,0,.25)'; g.fillRect(X + 3, Y + 3, TS - 6, TS - 6);
    g.fillStyle = colorOf(o.owner); g.fillRect(X + 3, Y + 3, 10, 7);
  }
  g.font = `${o.kind === 'pile' ? 22 : 26}px serif`;
  g.fillText(icon, cx, cy + 1);
}
function drawHero(g, h, X, Y) {
  const inTown = G.objAt.get(idx(h.x, h.y));
  const cx = X + TS / 2 + (inTown ? 14 : 0), cy = Y + TS / 2 + (inTown ? 12 : 0);
  g.beginPath(); g.arc(cx, cy, 16, 0, Math.PI * 2);
  g.fillStyle = colorOf(h.owner); g.fill();
  g.lineWidth = 3; g.strokeStyle = h.owner === 0 ? '#ffe27a' : '#1a1a1a'; g.stroke();
  g.font = '20px serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillText(UNITS[h.unit.type].icon, cx, cy + 1);
  if (inTown) return;
  // banner pole
  g.fillStyle = '#3a2a1a'; g.fillRect(X + TS - 9, Y - 8, 2, 20);
  g.fillStyle = colorOf(h.owner); g.fillRect(X + TS - 7, Y - 8, 10, 7);
}

function drawMap() {
  const cv = document.getElementById('map');
  if (!cv || !V.layer) return;
  const g = cv.getContext('2d');
  g.setTransform(V.dpr, 0, 0, V.dpr, 0, 0);
  g.fillStyle = '#0d0b09'; g.fillRect(0, 0, V.w, V.h);
  g.drawImage(V.layer, -V.cx, -V.cy);
  const x0 = Math.max(0, Math.floor(V.cx / TS)), y0 = Math.max(0, Math.floor(V.cy / TS));
  const x1 = Math.min(G.W - 1, Math.ceil((V.cx + V.w) / TS)), y1 = Math.min(G.H - 1, Math.ceil((V.cy + V.h) / TS));
  const me = human(), myHero = heroOf(me);
  // Guard zones of the hovered monster.
  if (V.hover) {
    const o = G.objAt.get(idx(V.hover.x, V.hover.y));
    if (o && o.kind === 'monster' && G.fog[idx(o.x, o.y)]) {
      g.fillStyle = 'rgba(220,40,40,.22)';
      for (const [i, m] of G.guard) if (m === o) g.fillRect((i % G.W) * TS - V.cx, ((i / G.W) | 0) * TS - V.cy, TS, TS);
    }
  }
  for (const o of G.objs) {
    if (o.x < x0 - 1 || o.x > x1 + 1 || o.y < y0 - 1 || o.y > y1 + 1 || !G.fog[idx(o.x, o.y)]) continue;
    drawObj(g, o, o.x * TS - V.cx, o.y * TS - V.cy);
  }
  // Planned path: green = reachable today, orange = later days.
  if (G.path && myHero && myHero.alive) {
    let mp = myHero.mp, prev = idx(myHero.x, myHero.y);
    for (let k = 0; k < G.path.length; k++) {
      const i = G.path[k];
      mp -= stepCost(prev, i); prev = i;
      const X = (i % G.W) * TS - V.cx + TS / 2, Y = ((i / G.W) | 0) * TS - V.cy + TS / 2;
      const o = G.objAt.get(i), h = heroAtIdx(i);
      const fight = G.guard.has(i) || (o && o.kind === 'monster') || (h && h.owner !== 0) || (o && o.kind === 'town' && o.owner !== 0);
      const last = fight || k === G.path.length - 1;
      g.textAlign = 'center'; g.textBaseline = 'middle';
      if (fight) { g.font = '22px serif'; g.fillText('⚔️', X, Y); }
      else {
        g.beginPath(); g.arc(X, Y, last ? 8 : 5, 0, Math.PI * 2);
        g.fillStyle = mp >= 0 ? '#4cd964' : '#ff9f43'; g.fill();
        g.lineWidth = 2; g.strokeStyle = 'rgba(0,0,0,.6)'; g.stroke();
      }
      if (last) {
        const days = mp >= 0 ? 0 : Math.ceil(-mp / BASE_MP);
        if (days) { g.font = 'bold 12px system-ui'; g.lineWidth = 3; g.strokeStyle = '#000'; g.strokeText(`+${days}d`, X, Y - 16); g.fillStyle = '#fff'; g.fillText(`+${days}d`, X, Y - 16); }
        break;
      }
    }
  }
  for (const h of G.heroes) if (h.alive && G.fog[idx(h.x, h.y)]) drawHero(g, h, h.x * TS - V.cx, h.y * TS - V.cy);
  // Fog of war
  for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
    if (G.fog[idx(x, y)]) continue;
    g.fillStyle = '#0d0b09';
    g.fillRect(x * TS - V.cx - 0.5, y * TS - V.cy - 0.5, TS + 1, TS + 1);
  }
  if (V.hover && inMap(V.hover.x, V.hover.y)) {
    g.strokeStyle = 'rgba(255,226,122,.9)'; g.lineWidth = 2;
    g.strokeRect(V.hover.x * TS - V.cx + 1, V.hover.y * TS - V.cy + 1, TS - 2, TS - 2);
  }
}

function drawMinimap() {
  const cv = document.getElementById('minimap');
  if (!cv) return;
  const s = 4, g = cv.getContext('2d');
  cv.width = G.W * s; cv.height = G.H * s;
  for (let y = 0; y < G.H; y++) for (let x = 0; x < G.W; x++) {
    const i = idx(x, y);
    g.fillStyle = !G.fog[i] ? '#0d0b09' : G.obst[i] ? '#3d4a2f' : G.road[i] ? '#c2a477' : TERRAIN[G.terr[i]].color;
    g.fillRect(x * s, y * s, s, s);
  }
  for (const o of G.objs) if ((o.kind === 'town' || o.kind === 'mine') && G.fog[idx(o.x, o.y)]) {
    g.fillStyle = colorOf(o.owner); const r = o.kind === 'town' ? 3 : 1.5;
    g.fillRect(o.x * s + 2 - r, o.y * s + 2 - r, r * 2, r * 2);
  }
  for (const h of G.heroes) if (h.alive && G.fog[idx(h.x, h.y)]) {
    g.fillStyle = h.owner === 0 ? '#ffe27a' : colorOf(h.owner);
    g.beginPath(); g.arc(h.x * s + 2, h.y * s + 2, 3, 0, Math.PI * 2); g.fill();
  }
  g.strokeStyle = '#fff'; g.lineWidth = 1;
  g.strokeRect(V.cx / TS * s, V.cy / TS * s, V.w / TS * s, V.h / TS * s);
}

// ── Hover descriptions ──────────────────────────────────────────────────────
function describeTile(x, y) {
  if (!inMap(x, y)) return null;
  const i = idx(x, y);
  if (!G.fog[i]) return { title: 'Unexplored', body: 'Send your hero to explore.' };
  const o = G.objAt.get(i), h = heroAtIdx(i), me = heroOf(human());
  const myPow = me && me.alive ? armyPower(me.army) + unitPower(me.unit) : 1;
  const terr = `${TERRAIN[G.terr[i]].name}${G.road[i] ? ' (road)' : ''}${G.obst[i] ? ' — impassable' : ''}`;
  if (h) {
    const [lbl, col] = threatLabel(myPow, armyPower(h.army) + unitPower(h.unit));
    return { title: `${UNITS[h.unit.type].icon} ${heroName(h)} (${FACTIONS[playerOf(h.owner).faction].name})`, body: h.owner === 0 ? 'Your hero.' : `Lv ${h.unit.lvl} hero with ${h.army.length} units.`, threat: h.owner === 0 ? null : [lbl, col] };
  }
  if (o) {
    switch (o.kind) {
      case 'town': {
        const owner = o.owner == null ? 'Neutral' : FACTIONS[playerOf(o.owner).faction].name;
        const f = townForce(o), pw = armyPower(f.units) + (f.lead ? unitPower(f.lead) : 0);
        return { title: `${FACTIONS[o.faction].townIcon} ${o.name}`, body: `${FACTIONS[o.faction].adj} town · ${owner}${o.built.includes('walls') ? ' · walled' : ''}${o.owner !== 0 ? ` · garrison ${f.units.length}` : ''}`, threat: o.owner !== 0 && pw ? threatLabel(myPow, pw) : null };
      }
      case 'monster': {
        const T = UNITS[o.units[0].type];
        return { title: `${T.icon} ${o.name}`, body: `${countLabel(o.units.length)} ${o.units.length === 1 ? T.name : 'creatures'} (Lv ${o.units[0].lvl}). Entering the red zone starts a battle.`, threat: threatLabel(myPow, armyPower(o.units)) };
      }
      case 'mine': return { title: `${MINE_INFO[o.res].icon} ${MINE_INFO[o.res].name}`, body: `+${MINE_INFO[o.res].amt} ${RES_INFO[o.res].name}/day · ${o.owner == null ? 'unclaimed' : o.owner === 0 ? 'yours' : FACTIONS[playerOf(o.owner).faction].name}` };
      case 'pile': return { title: `${RES_INFO[o.res].icon} ${RES_INFO[o.res].name}`, body: 'A pile of resources ripe for the taking.' };
      case 'chest': return { title: '💰 Treasure Chest', body: 'Gold, or experience for your army.' };
      case 'shrine': { const S = SHRINES[o.si]; return { title: `🛐 ${S.name}`, body: `Blesses a visiting hero with +${S.val} ${STAT_NAMES[S.stat]} (once).${me && me.shrines.includes(o.id) ? ' Already visited.' : ''}` }; }
      case 'artifact': { const A = ARTIFACTS[o.art]; return { title: `${A.icon} ${A.name}`, body: A.desc + (G.guard.has(i) ? ' · guarded!' : '') }; }
    }
  }
  const g = G.guard.get(i);
  return { title: terr, body: g ? `Guarded by ${g.name}.` : `Movement cost ${G.road[i] ? ROAD_COST : TERRAIN[G.terr[i]].cost}.` };
}

// ── Input ───────────────────────────────────────────────────────────────────
function tileAt(e) {
  const r = document.getElementById('map').getBoundingClientRect();
  return { x: Math.floor((e.clientX - r.left + V.cx) / TS), y: Math.floor((e.clientY - r.top + V.cy) / TS) };
}
async function onMapClick(x, y) {
  if (!G || G.busy || G.over || B) return;
  const h = heroOf(human());
  if (!h.alive) { toast('Your hero is recovering — end the turn.'); return; }
  if (!inMap(x, y)) return;
  const i = idx(x, y);
  if (i === idx(h.x, h.y)) {
    const t = G.objAt.get(i);
    if (t && t.kind === 'town') openTown(t);
    else { G.path = null; requestDraw(); }
    return;
  }
  if (G.path && G.path[G.path.length - 1] === i) {
    const path = G.path; G.path = null;
    G.busy = true;
    try { await walkHero(h, path, true); } finally { G.busy = false; }
    refreshPanel(); requestDraw(); autosave();
    return;
  }
  if (!G.fog[i]) { G.path = null; requestDraw(); return; }
  const dj = heroDijkstra(h, i);
  const p = pathFrom(dj, i);
  G.path = p && p.length ? p : null;
  if (!G.path) toast('No path there.');
  requestDraw();
}

document.addEventListener('DOMContentLoaded', () => {
  const cv = document.getElementById('map');
  cv.addEventListener('pointerdown', e => {
    V.drag = { x: e.clientX, y: e.clientY, cx: V.cx, cy: V.cy, moved: false, id: e.pointerId };
  });
  cv.addEventListener('pointermove', e => {
    if (!G) return;
    if (V.drag && e.buttons) {
      const dx = e.clientX - V.drag.x, dy = e.clientY - V.drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 6) V.drag.moved = true;
      if (V.drag.moved) { V.cx = V.drag.cx - dx; V.cy = V.drag.cy - dy; clampCam(); requestDraw(); }
    }
    const t = tileAt(e);
    if (!V.hover || V.hover.x !== t.x || V.hover.y !== t.y) { V.hover = t; requestDraw(); refreshHover(); }
  });
  cv.addEventListener('pointerup', e => {
    const d = V.drag; V.drag = null;
    if (d && !d.moved) { const t = tileAt(e); onMapClick(t.x, t.y); }
  });
  cv.addEventListener('pointerleave', () => { V.hover = null; requestDraw(); refreshHover(); });
  cv.addEventListener('contextmenu', e => { e.preventDefault(); if (G) { G.path = null; requestDraw(); } });
  document.getElementById('minimap').addEventListener('click', e => {
    const r = e.target.getBoundingClientRect();
    centerOn(Math.floor((e.clientX - r.left) / r.width * G.W), Math.floor((e.clientY - r.top) / r.height * G.H));
  });
  window.addEventListener('resize', () => { if (G && !document.getElementById('campaign').classList.contains('hidden')) resizeMap(); });
  document.addEventListener('keydown', e => {
    if (!G || B || document.querySelector('.modal-back')) return;
    const k = e.key, step = TS * 3;
    if (k === 'ArrowLeft') V.cx -= step; else if (k === 'ArrowRight') V.cx += step;
    else if (k === 'ArrowUp') V.cy -= step; else if (k === 'ArrowDown') V.cy += step;
    else if (k.toLowerCase() === 'e') { endTurn(); return; }
    else if (k.toLowerCase() === 'c') { const h = heroOf(human()); if (h.alive) centerOn(h.x, h.y); return; }
    else if (k.toLowerCase() === 't') { const t = townsOf(human())[0]; if (t) openTown(t); return; }
    else if (k === 'Escape') { G.path = null; requestDraw(); return; }
    else return;
    e.preventDefault(); clampCam(); requestDraw();
  });
});
