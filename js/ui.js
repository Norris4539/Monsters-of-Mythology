'use strict';
// ─────────────────────────────────────────────────────────────────────────────
// Screens, modals, the adventure side panel, the town screen, the main menu
// and save/load.
// ─────────────────────────────────────────────────────────────────────────────

function showScreen(name) {
  for (const s of document.querySelectorAll('.screen')) s.classList.toggle('hidden', s.id !== name);
  if (name === 'campaign' && G) { resizeMap(); refreshPanel(); }
}

// ── Modals & toasts ─────────────────────────────────────────────────────────
function modal(title, content, buttons = [['OK', null]], opts = {}) {
  const back = el('div', { className: 'modal-back' });
  const close = () => back.remove();
  const box = el('div', { className: 'modal ' + (opts.cls || '') },
    el('div', { className: 'modal-head' }, el('h2', null, title),
      opts.noClose ? null : el('button', { className: 'x', onClick: close, 'aria-label': 'Close' }, '✕')),
    el('div', { className: 'modal-body' }, content),
    buttons.length ? el('div', { className: 'modal-btns' }, buttons.map(([label, fn], i) =>
      el('button', { className: 'btn' + (i === 0 ? ' primary' : ''), onClick: () => { close(); if (fn) fn(); } }, label))) : null);
  back.append(box);
  if (!opts.noClose) back.addEventListener('pointerdown', e => { if (e.target === back) close(); });
  document.body.append(back);
  return { close, box };
}
function confirmModal(title, text, onYes) { modal(title, el('p', null, text), [['Confirm', onYes], ['Cancel', null]]); }
function choiceModal(title, text, options) {
  return new Promise(res => modal(title, el('p', null, text), options.map(([label, v]) => [label, () => res(v)]), { noClose: true }));
}
function toast(html) {
  const t = el('div', { className: 'toast', html });
  document.getElementById('toasts').append(t);
  setTimeout(() => t.classList.add('out'), 3200);
  setTimeout(() => t.remove(), 3700);
}

// ── Adventure side panel ────────────────────────────────────────────────────
function refreshPanel() {
  if (!G) return;
  const me = human(), h = heroOf(me);
  document.getElementById('res').innerHTML = RES.map(r => `<span title="${RES_INFO[r].name}">${RES_INFO[r].icon} <b>${me.res[r]}</b></span>`).join('');
  document.getElementById('date').textContent = dateText(G.day);
  document.getElementById('btn-end').disabled = !!G.busy || G.over;
  const hb = document.getElementById('hero-box');
  hb.innerHTML = '';
  const T = UNITS[h.unit.type], F = FACTIONS[me.faction];
  const maxMp = BASE_MP + h.artifacts.reduce((s, a) => s + (ARTIFACTS[a].mp || 0), 0);
  hb.append(
    el('div', { className: 'hero-head', onClick: () => heroModal(h) },
      el('span', { className: 'portrait', style: { background: F.color } }, T.icon),
      el('div', null,
        el('div', { className: 'hname' }, `${T.name} `, el('small', null, `Lv ${h.unit.lvl}`)),
        el('div', { className: 'hsub' }, h.alive ? `${F.name} · patron ${F.god}` : `Recovering… returns in ${h.respawn} day(s)`))),
    el('div', { className: 'bar', title: 'Movement points' }, el('i', { style: { width: `${h.alive ? h.mp / maxMp * 100 : 0}%` } }), el('span', null, `Move ${h.alive ? Math.round(h.mp / 10) : 0}/${maxMp / 10}`)),
    el('div', { className: 'bar xp', title: 'Experience' }, el('i', { style: { width: `${h.unit.xp}%` } }), el('span', null, `XP ${h.unit.xp}/100`)),
  );
  const ab = document.getElementById('army-box');
  ab.innerHTML = '';
  ab.append(el('div', { className: 'sl' }, `Army (${h.army.length}/${ARMY_CAP})`));
  const grid = el('div', { className: 'army' });
  for (let k = 0; k < ARMY_CAP; k++) {
    const u = h.army[k];
    grid.append(u ? unitChip(u, () => unitModal(u, { dismiss: () => { h.army = h.army.filter(x => x !== u); refreshPanel(); } })) : el('div', { className: 'chip empty' }));
  }
  ab.append(grid);
  const arts = document.getElementById('arts-box');
  arts.innerHTML = '';
  if (h.artifacts.length) arts.append(el('div', { className: 'sl' }, 'Artifacts'), el('div', { className: 'arts' }, h.artifacts.map(a => el('span', { title: `${ARTIFACTS[a].name}: ${ARTIFACTS[a].desc}` }, ARTIFACTS[a].icon))));
  const tb = document.getElementById('towns-box');
  tb.innerHTML = '';
  const towns = townsOf(me);
  tb.append(el('div', { className: 'sl' }, 'Towns'), towns.length ? el('div', { className: 'towns' }, towns.map(t =>
    el('button', { className: 'btn small', onClick: () => openTown(t) }, `${FACTIONS[t.faction].townIcon} ${t.name}`))) : el('div', { className: 'warn' }, `No towns! ${7 - me.noTownDays} days left.`));
  refreshLog();
}
function unitChip(u, onClick) {
  const T = UNITS[u.type];
  return el('button', { className: 'chip', onClick, title: `${T.name} Lv ${u.lvl}` },
    el('span', { className: 'ci' }, T.icon), el('span', { className: 'cl' }, `${u.lvl}`));
}
function refreshHover() {
  const box = document.getElementById('hover-box');
  if (!box) return;
  const d = V.hover && describeTile(V.hover.x, V.hover.y);
  box.innerHTML = '';
  if (!d) { box.append(el('div', { className: 'hint' }, 'Click a tile to plot a path, click it again to march. Drag to pan.')); return; }
  box.append(el('div', { className: 'ht' }, d.title), el('div', { className: 'hb' }, d.body));
  if (d.threat) box.append(el('div', { className: 'threat', style: { color: d.threat[1] } }, `Threat: ${d.threat[0]}`));
}
function refreshLog() {
  const l = document.getElementById('log');
  if (l && G) l.innerHTML = G.log.map(m => `<div>${m}</div>`).join('');
}

function unitModal(u, opts = {}) {
  const T = UNITS[u.type];
  const body = el('div', null, unitCard(u, 'p', T.hero),
    el('p', { className: 'desc' }, T.desc),
    T.abil.length ? el('ul', { className: 'abil' }, T.abil.map(a => el('li', null, ABILITIES[a]))) : null,
    el('p', { className: 'dim' }, `Growths: ${STATS.map(s => `${STAT_NAMES[s]} ${T.growth[s]}%`).join(' · ')}`));
  const btns = [['Close', null]];
  if (opts.dismiss) btns.push(['Dismiss unit', () => confirmModal('Dismiss?', `${T.name} will leave your army forever.`, opts.dismiss)]);
  modal(`${T.icon} ${T.name}`, body, btns);
}
function heroModal(h) {
  const F = FACTIONS[playerOf(h.owner).faction];
  h.unit.bonus = armyBonus(h, true);
  const card = unitCard(h.unit, 'p', true);
  delete h.unit.bonus;
  const body = el('div', null, card,
    el('p', { className: 'desc' }, UNITS[h.unit.type].desc),
    el('div', { className: 'sl' }, `God power — ${F.god}`),
    el('p', null, el('b', null, F.power.name + ': '), F.power.desc, ' Once per battle (twice if you own a Temple).'),
    el('div', { className: 'sl' }, 'Artifacts'),
    h.artifacts.length ? el('ul', null, h.artifacts.map(a => el('li', null, `${ARTIFACTS[a].icon} ${ARTIFACTS[a].name} — ${ARTIFACTS[a].desc}`))) : el('p', { className: 'dim' }, 'None yet. Seek them out across the map.'),
    Object.keys(h.shrineBonus).length ? el('p', null, el('b', null, 'Shrine blessings: '), Object.entries(h.shrineBonus).map(([k, v]) => `${STAT_NAMES[k]} +${v}`).join(', ')) : null);
  modal(`${UNITS[h.unit.type].icon} ${UNITS[h.unit.type].name}`, body, [['Close', null]]);
}

// ── Town screen ─────────────────────────────────────────────────────────────
function openTown(t) {
  if (t.owner !== 0) return;
  const m = modal(`${FACTIONS[t.faction].townIcon} ${t.name}`, el('div'), [], { cls: 'town' });
  const body = m.box.querySelector('.modal-body');
  const render = () => {
    const p = human(), h = heroOf(p), F = FACTIONS[t.faction];
    const heroHere = h.alive && h.x === t.x && h.y === t.y;
    body.innerHTML = '';
    body.append(el('div', { className: 'town-sub' },
      `${F.adj} town · income ${RES_INFO.gold.icon}${townIncome(t)}/day · `,
      ...RES.map(r => el('span', { className: 'rs' }, `${RES_INFO[r].icon}${p.res[r]} `))));
    // Recruitment
    const rec = el('div', { className: 'recruit' });
    for (let tier = 1; tier <= 7; tier++) {
      const type = F.units[tier - 1], U = UNITS[type], key = 'd' + tier, built = t.built.includes(key);
      const dest = heroHere && h.army.length < ARMY_CAP ? h.army : t.garrison;
      const destCap = dest === t.garrison ? GARRISON_CAP : ARMY_CAP;
      const avail = t.pool[key] || 0;
      const can = built && avail > 0 && canAfford(p.res, TIER_COST[tier]) && dest.length < destCap;
      rec.append(el('div', { className: 'rrow' + (built ? '' : ' locked') },
        el('button', { className: 'ricon', onClick: () => unitModal(makeUnit(type)), title: 'Unit details' }, U.icon),
        el('div', { className: 'rname' }, el('b', null, U.name), el('small', null, `Tier ${tier} · ${WEAPONS[U.weapon].name} · ${MOVE_TYPES[U.move]}`)),
        el('div', { className: 'ravail' }, built ? `${avail} available` : `Build ${F.dwellings[tier - 1]}`),
        el('div', { className: 'rcost' }, costText(TIER_COST[tier])),
        el('button', { className: 'btn small primary', disabled: !can, onClick: () => { recruit(t, tier, dest); render(); refreshPanel(); } }, 'Hire')));
    }
    body.append(el('div', { className: 'sl' }, heroHere ? 'Recruit (joins your hero)' : 'Recruit (joins the garrison)'), rec);
    // Armies
    const swap = (u, from, to, cap) => { if (to.length >= cap) return; from.splice(from.indexOf(u), 1); to.push(u); render(); refreshPanel(); };
    const armies = el('div', { className: 'armies' });
    if (heroHere) armies.append(el('div', null, el('div', { className: 'sl' }, `${UNITS[h.unit.type].name}'s army (${h.army.length}/${ARMY_CAP}) — click to station`),
      el('div', { className: 'army' }, h.army.map(u => unitChip(u, () => swap(u, h.army, t.garrison, GARRISON_CAP))))));
    armies.append(el('div', null, el('div', { className: 'sl' }, `Garrison (${t.garrison.length}/${GARRISON_CAP})${heroHere ? ' — click to join hero' : ''}`),
      el('div', { className: 'army' }, t.garrison.length ? t.garrison.map(u => unitChip(u, () => heroHere ? swap(u, t.garrison, h.army, ARMY_CAP) : unitModal(u))) : el('span', { className: 'dim' }, 'empty'))));
    body.append(armies);
    // Buildings
    const grid = el('div', { className: 'bgrid' });
    const all = ['d2', 'd3', 'd4', 'd5', 'd6', 'd7', 'hall2', 'hall3', 'market', 'citadel', 'walls', 'temple'];
    for (const b of all) {
      const done = t.built.includes(b), why = canBuild(t, b), B_ = BUILDINGS[b];
      const desc = b[0] === 'd' ? `Recruits ${UNITS[F.units[dwellingTier(b) - 1]].icon} ${UNITS[F.units[dwellingTier(b) - 1]].name} (${growthOf(t, dwellingTier(b))}/week)` : B_.desc;
      grid.append(el('div', { className: 'bcard' + (done ? ' done' : why ? ' no' : ' ok') },
        el('b', null, buildingName(t, b)), el('small', null, desc),
        done ? el('span', { className: 'tag' }, '✓ Built') : el('div', { className: 'bfoot' },
          el('span', null, costText(B_.cost)),
          el('button', { className: 'btn small', disabled: !!why, title: why || '', onClick: () => { build(t, b); render(); refreshPanel(); } }, 'Build')),
        !done && why && why !== 'Not enough resources' ? el('small', { className: 'why' }, why) : null));
    }
    body.append(el('div', { className: 'sl' }, t.builtToday ? 'Buildings (one per day — done for today)' : 'Buildings (one per day)'), grid);
    // Market
    if (t.built.includes('market')) {
      body.append(el('div', { className: 'sl' }, 'Marketplace'), el('div', { className: 'market' }, Object.entries(MARKET).map(([r, m]) =>
        el('div', { className: 'mrow' }, `${RES_INFO[r].icon} ${RES_INFO[r].name}`,
          el('button', { className: 'btn small', disabled: p.res[r] < 1, onClick: () => { p.res[r]--; p.res.gold += m.sell; render(); refreshPanel(); } }, `Sell 1 (+${m.sell})`),
          el('button', { className: 'btn small', disabled: p.res.gold < m.buy, onClick: () => { p.res[r]++; p.res.gold -= m.buy; render(); refreshPanel(); } }, `Buy 1 (−${m.buy})`)))));
    }
  };
  render();
}

// ── Main menu ───────────────────────────────────────────────────────────────
const MENU = { faction: 'greek', opponents: 2, difficulty: 1 };
function showMainMenu() {
  B = null;
  showScreen('menu');
  const root = document.getElementById('menu-body');
  root.innerHTML = '';
  const facs = el('div', { className: 'factions' }, FACTION_KEYS.map(k => {
    const F = FACTIONS[k];
    return el('button', { className: 'fcard' + (MENU.faction === k ? ' sel' : ''), style: { '--fc': F.color }, onClick: () => { MENU.faction = k; showMainMenu(); } },
      el('div', { className: 'fhead' }, el('span', { className: 'ficon' }, F.townIcon), el('div', null, el('b', null, F.name), el('small', null, `Patron: ${F.god}`))),
      el('p', null, F.blurb),
      el('div', { className: 'roster' }, F.units.map(id => el('span', { title: `T${UNITS[id].tier} ${UNITS[id].name}` }, UNITS[id].icon))),
      el('small', { className: 'power' }, `✨ ${F.power.name}: ${F.power.desc}`),
      el('small', null, `Hero: ${UNITS[F.hero].icon} ${UNITS[F.hero].name}`));
  }));
  const seg = (label, opts, key) => el('div', { className: 'seg' }, el('span', null, label), opts.map(([v, l]) =>
    el('button', { className: 'btn small' + (MENU[key] === v ? ' primary' : ''), onClick: () => { MENU[key] = v; showMainMenu(); } }, l)));
  let auto = null, manual = null;
  try { auto = localStorage.getItem('pantheon_autosave'); manual = localStorage.getItem('pantheon_save'); } catch (e) { /* storage blocked */ }
  root.append(
    el('div', { className: 'sl' }, 'Choose your pantheon'), facs,
    el('div', { className: 'opts' },
      seg('Rivals', [[1, '1'], [2, '2'], [3, '3']], 'opponents'),
      seg('Difficulty', [[0, 'Mortal'], [1, 'Hero'], [2, 'Demigod']], 'difficulty')),
    el('div', { className: 'menu-btns' },
      el('button', { className: 'btn primary big', onClick: () => { newGame(MENU); enterCampaign(); } }, '⚔️ Begin Campaign'),
      auto ? el('button', { className: 'btn big', onClick: () => loadGame('pantheon_autosave') }, '↻ Continue') : null,
      manual ? el('button', { className: 'btn big', onClick: () => loadGame('pantheon_save') }, '📜 Load Save') : null,
      el('button', { className: 'btn ghost big', onClick: helpModal }, '❔ How to play')),
  );
}
function helpModal() {
  modal('How to play', el('div', { className: 'help' },
    el('h3', null, 'The adventure map'),
    el('ul', null,
      el('li', null, 'Click a tile to plot a path (green = this turn, orange = later days). Click the same tile again to march.'),
      el('li', null, 'Collect resource piles and chests, capture mines for daily income, visit shrines for blessings and claim artifacts.'),
      el('li', null, 'Wandering monsters guard the tiles around them (shown in red on hover). Stepping into that zone starts a battle.'),
      el('li', null, 'Your town builds one structure per day. Dwellings produce new recruits every week. Visit town to merge the garrison into your army.'),
      el('li', null, 'Win by eliminating every rival pantheon: take their towns and defeat their heroes. Shortcuts: E end turn, C center hero, T town.')),
    el('h3', null, 'Battles'),
    el('ul', null,
      el('li', null, 'Each side moves all its units in turn. Select a unit, move it, then Attack, Heal or Wait.'),
      el('li', null, 'Weapon triangle: Sword beats Axe, Axe beats Lance, Lance beats Sword (+15 hit, +1 damage). Bows deal triple might to fliers. Tomes hit Res.'),
      el('li', null, 'Units 4+ Spd faster than their foe strike twice. Forests, mountains and forts grant avoid and defence.'),
      el('li', null, 'Adjacent allies give +10 Hit/Avoid and may join in with a Dual Strike.'),
      el('li', null, 'Your hero is the commander: if they fall, the battle is lost. Slay the enemy commander and their army routs.'),
      el('li', null, 'Once per battle, call on your god for a divine power. Fallen units are gone for good — survivors level up and heal fully afterwards.'))),
    [['Got it', null]]);
}
function enterCampaign() {
  showScreen('campaign');
  buildStaticLayer();
  resizeMap();
  const h = heroOf(human());
  centerOn(h.x, h.y);
  refreshPanel(); refreshHover();
}

// ── Save / load ─────────────────────────────────────────────────────────────
function serialize() {
  const { objAt, guard, busy, path, ...rest } = G;
  return JSON.stringify(rest);
}
function saveGame(key = 'pantheon_save') {
  if (!G || G.busy) return;
  try { localStorage.setItem(key, serialize()); if (key === 'pantheon_save') toast('💾 Game saved'); }
  catch (e) { if (key === 'pantheon_save') toast('Could not save (storage unavailable).'); }
}
function autosave() { if (G && !G.over) saveGame('pantheon_autosave'); }
function loadGame(key = 'pantheon_save') {
  let data = null;
  try { data = localStorage.getItem(key); } catch (e) { /* storage blocked */ }
  if (!data) { toast('No saved game found.'); return; }
  G = JSON.parse(data);
  G.busy = false; G.path = null;
  let max = 0;
  const scan = u => { if (u && u.uid > max) max = u.uid; };
  for (const h of G.heroes) { scan(h.unit); h.army.forEach(scan); }
  for (const o of G.objs) (o.units || o.garrison || []).forEach(scan);
  UID = max + 1;
  rebuildIndex();
  enterCampaign();
  toast(`Loaded — ${dateText(G.day)}`);
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btn-end').addEventListener('click', () => endTurn());
  document.getElementById('btn-save').addEventListener('click', () => saveGame());
  document.getElementById('btn-load').addEventListener('click', () => confirmModal('Load game?', 'Unsaved progress will be lost.', () => loadGame()));
  document.getElementById('btn-menu').addEventListener('click', () => confirmModal('Return to menu?', 'Your progress is autosaved each day.', () => { autosave(); showMainMenu(); }));
  document.getElementById('btn-help').addEventListener('click', helpModal);
  document.getElementById('btn-center').addEventListener('click', () => { const h = heroOf(human()); if (h.alive) centerOn(h.x, h.y); });
  showMainMenu();
});
