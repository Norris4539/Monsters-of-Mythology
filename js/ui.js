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
  const HD = HEROES[h.type], F = FACTIONS[me.faction];
  const maxMp = BASE_MP + h.artifacts.reduce((s, a) => s + (ARTIFACTS[a].mp || 0), 0);
  const x0 = h.lvl > 1 ? xpForLevel(h.lvl - 1) : 0, x1 = xpForLevel(h.lvl);
  hb.append(
    el('div', { className: 'hero-head', onClick: () => heroModal(h) },
      el('span', { className: 'portrait', style: { background: F.color } }, HD.icon),
      el('div', null,
        el('div', { className: 'hname' }, `${HD.name} `, el('small', null, `Lv ${h.lvl}`)),
        el('div', { className: 'hsub' }, h.alive ? `⚔️${heroStat(h, 'att')} 🛡️${heroStat(h, 'def')} ✨${heroStat(h, 'power')} · ${F.god}` : `Recovering… returns in ${h.respawn} day(s)`))),
    el('div', { className: 'bar', title: 'Movement points' }, el('i', { style: { width: `${h.alive ? h.mp / maxMp * 100 : 0}%` } }), el('span', null, `Move ${h.alive ? Math.round(h.mp / 10) : 0}/${maxMp / 10}`)),
    el('div', { className: 'bar xp', title: 'Experience' }, el('i', { style: { width: `${clamp((h.xp - x0) / (x1 - x0) * 100, 0, 100)}%` } }), el('span', null, `XP ${h.xp}/${x1}`)),
  );
  const ab = document.getElementById('army-box');
  ab.innerHTML = '';
  ab.append(el('div', { className: 'sl' }, `Army (${h.army.length}/${ARMY_SLOTS} stacks)`));
  const grid = el('div', { className: 'army' });
  for (let k = 0; k < ARMY_SLOTS; k++) {
    const u = h.army[k];
    grid.append(u ? unitChip(u, () => stackModal(u, { dismiss: () => { h.army = h.army.filter(x => x !== u); refreshPanel(); } })) : el('div', { className: 'chip empty' }));
  }
  ab.append(grid);
  const fallen = Object.entries(h.fallen || {});
  if (fallen.length) ab.append(el('div', { className: 'fallen', title: 'Can be raised at a temple' }, '⚰️ Fallen: ', fallen.map(([t, n]) => `${n} ${UNITS[t].icon}`).join(' ')));
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
function unitChip(s, onClick) {
  const T = UNITS[s.type], hurt = s.hp < T.hp;
  return el('button', { className: 'chip' + (hurt ? ' hurt' : ''), onClick, title: `${s.n} × ${T.name}${hurt ? ` (top creature ${s.hp}/${T.hp} HP)` : ''}` },
    el('span', { className: 'ci' }, T.icon), el('span', { className: 'cl' }, `${s.n}`),
    T.lvl > 1 ? el('span', { className: 'cs' }, '★'.repeat(T.lvl - 1)) : null);
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

function stackModal(s, opts = {}) {
  const T = UNITS[s.type], L = LINES[T.line];
  const body = el('div', null, stackCard(s, 'p'),
    el('p', { className: 'desc' }, T.desc || L.desc),
    T.abil.length ? el('ul', { className: 'abil' }, T.abil.map(a => el('li', null, el('b', null, ABILITIES[a][0] + ': '), ABILITIES[a][1]))) : null,
    el('p', { className: 'dim' }, `Line: ${L.levels.map((id, i) => `${i + 1 === T.lvl ? '▶ ' : ''}${UNITS[id].name}`).join(' → ')} · ${costText(T.cost)} each`));
  const btns = [['Close', null]];
  if (opts.dismiss) btns.push(['Dismiss stack', () => confirmModal('Dismiss?', `${s.n} ${T.name} will leave your army forever.`, opts.dismiss)]);
  modal(`${T.icon} ${T.name}`, body, btns);
}
const unitModalOf = type => stackModal(makeStack(type, 1));
function heroModal(h) {
  const F = FACTIONS[playerOf(h.owner).faction], HD = HEROES[h.type];
  const stat = k => { const b = h[k], v = heroStat(h, k); return v !== b ? `${v} (${b}+${v - b})` : `${v}`; };
  const body = el('div', null,
    el('div', { className: 'ucard p' },
      el('div', { className: 'uc-head' }, el('span', { className: 'uc-icon' }, HD.icon),
        el('div', null, el('div', { className: 'uc-name' }, HD.name), el('div', { className: 'uc-sub' }, `Level ${h.lvl} · ${h.xp}/${xpForLevel(h.lvl)} XP`))),
      el('div', { className: 'uc-stats', html: [['Attack', stat('att')], ['Defence', stat('def')], ['Power', stat('power')]].map(([k, v]) => `<span>${k} <b>${v}</b></span>`).join('') })),
    el('p', { className: 'desc' }, HD.desc, ' The hero commands from behind the lines: Attack and Defence are added to every stack, Power strengthens the god power.'),
    el('div', { className: 'sl' }, `God power — ${F.god}`),
    el('p', null, el('b', null, F.power.name + ': '), F.power.desc, ' Once per battle (twice if you own a Temple).'),
    el('div', { className: 'sl' }, 'Artifacts'),
    h.artifacts.length ? el('ul', null, h.artifacts.map(a => el('li', null, `${ARTIFACTS[a].icon} ${ARTIFACTS[a].name} — ${ARTIFACTS[a].desc}`))) : el('p', { className: 'dim' }, 'None yet. Seek them out across the map.'),
    Object.keys(h.shrineBonus).length ? el('p', null, el('b', null, 'Shrine blessings: '), Object.entries(h.shrineBonus).map(([k, v]) => `${HERO_STAT[k]} +${v}`).join(', ')) : null);
  modal(`${HD.icon} ${HD.name}`, body, [['Close', null]]);
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
    // Recruitment: one row per tier, a button per unlocked level.
    const dest = heroHere ? h.army : t.garrison;
    const rec = el('div', { className: 'recruit' });
    for (let tier = 1; tier <= 7; tier++) {
      const L = lineOf(t, tier), key = 'd' + tier, lvl = townLevel(t, tier), avail = t.pool[key] || 0;
      const top = UNITS[L.levels[Math.max(0, lvl - 1)]];
      const row = el('div', { className: 'rrow' + (lvl ? '' : ' locked') },
        el('button', { className: 'ricon', onClick: () => unitModalOf(top.id), title: 'Unit details' }, top.icon),
        el('div', { className: 'rname' }, el('b', null, top.name), el('small', null, `Tier ${tier} · ${CLASSES[top.cls]} · ${WEAPONS[top.weapon].name}${top.size > 1 ? ' · Large' : ''}`)),
        el('div', { className: 'ravail' }, lvl ? `${avail} available · +${growthOf(t, tier)}/week` : `Build ${F.dwellings[tier - 1]}`));
      const buys = el('div', { className: 'rbuy' });
      if (lvl) for (let l = 1; l <= lvl; l++) {
        const U = UNITS[L.levels[l - 1]], most = Math.min(avail, maxAffordable(p.res, U.cost));
        const fits = dest.some(s => s.type === U.id) || dest.length < (dest === t.garrison ? GARRISON_SLOTS : ARMY_SLOTS);
        const hire = n => { recruit(t, tier, l, n, dest); render(); refreshPanel(); };
        buys.append(el('div', { className: 'rlvl' },
          el('span', { title: U.name }, `${'★'.repeat(l)} ${costText(U.cost)}`),
          el('button', { className: 'btn small', disabled: !fits || most < 1, onClick: () => hire(1) }, '+1'),
          el('button', { className: 'btn small primary', disabled: !fits || most < 1, onClick: () => hire(most) }, `All ${most > 0 ? most : ''}`)));
      }
      row.append(buys);
      rec.append(row);
    }
    body.append(el('div', { className: 'sl' }, heroHere ? 'Recruit (joins your hero)' : 'Recruit (joins the garrison)'), rec);
    // Armies: click a stack to move it, ⬆ to upgrade it.
    const move = (s, from, to, cap) => {
      const same = to.find(x => x.type === s.type);
      if (!same && to.length >= cap) return;
      from.splice(from.indexOf(s), 1);
      if (same) same.n += s.n; else to.push(s);
      render(); refreshPanel();
    };
    const stackRow = (list, s, onClick) => {
      const to = canUpgrade(t, s), wrap = el('div', { className: 'srow' }, unitChip(s, onClick));
      if (to) {
        const cost = upgradeCost(s, to), N = UNITS[LINES[UNITS[s.type].line].levels[to - 1]];
        wrap.append(el('button', { className: 'btn small up', disabled: !canAfford(p.res, cost), title: `Upgrade to ${N.name} for ${costText(cost)}`,
          onClick: () => { upgradeStack(t, s, list); render(); refreshPanel(); } }, `⬆ ${costText(cost)}`));
      }
      return wrap;
    };
    const armies = el('div', { className: 'armies' });
    if (heroHere) armies.append(el('div', null, el('div', { className: 'sl' }, `${heroName(h)}'s army (${h.army.length}/${ARMY_SLOTS}) — click to station`),
      el('div', { className: 'army' }, h.army.map(s => stackRow(h.army, s, () => move(s, h.army, t.garrison, GARRISON_SLOTS))))));
    armies.append(el('div', null, el('div', { className: 'sl' }, `Garrison (${t.garrison.length}/${GARRISON_SLOTS})${heroHere ? ' — click to join hero' : ''}`),
      el('div', { className: 'army' }, t.garrison.length ? t.garrison.map(s => stackRow(t.garrison, s, () => heroHere ? move(s, t.garrison, h.army, ARMY_SLOTS) : stackModal(s))) : el('span', { className: 'dim' }, 'empty'))));
    body.append(armies);
    // Temple: raise the fallen.
    if (heroHere && t.built.includes('temple')) {
      const fallen = Object.entries(h.fallen);
      body.append(el('div', { className: 'sl' }, `${buildingName(t, 'temple')} — raise the fallen`),
        fallen.length ? el('div', { className: 'temple' }, fallen.map(([type, n]) => {
          const U = UNITS[type], most = Math.min(n, maxAffordable(p.res, U.cost));
          return el('div', { className: 'mrow' }, `${n} ${U.icon} ${U.name}`,
            el('span', { className: 'dim' }, `${costText(U.cost)} each`),
            el('button', { className: 'btn small primary', disabled: most < 1, onClick: () => { resurrect(h, t, type, most); render(); refreshPanel(); } }, `Raise ${most}`));
        })) : el('p', { className: 'dim' }, 'None of your soldiers lie fallen. Wounded stacks are healed whenever your hero visits.'));
    }
    // Buildings
    const grid = el('div', { className: 'bgrid' });
    const all = ['hall2', 'hall3', 'market', 'citadel', 'walls', 'temple', ...[1, 2, 3, 4, 5, 6, 7].flatMap(k => ['d' + k, 'u' + k, 'e' + k])].filter(b => b !== 'd1');
    for (const b of all) {
      const done = t.built.includes(b), why = canBuild(t, b), B_ = BUILDINGS[b];
      const U = 'due'.includes(b[0]) && !B_.name ? UNITS[lineOf(t, dwellingTier(b)).levels['due'.indexOf(b[0])]] : null;
      const desc = U ? (b[0] === 'd' ? `Recruits ${U.icon} ${U.name} (${growthOf(t, dwellingTier(b))}/week)` : `Recruit and upgrade to ${U.icon} ${U.name}: Attack ${U.att}, Defence ${U.def}, Move ${U.mov}`) : B_.desc;
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
      el('div', { className: 'roster' }, F.units.map(id => el('span', { title: `T${LINES[id].tier} ${LINES[id].levels.map(u => UNITS[u].name).join(' → ')}` }, LINES[id].icon))),
      el('small', { className: 'power' }, `✨ ${F.power.name}: ${F.power.desc}`),
      el('small', null, `Hero: ${HEROES[F.hero].icon} ${HEROES[F.hero].name}`));
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
    el('h3', null, 'Towns'),
    el('ul', null,
      el('li', null, 'Every creature line has three levels. Build the dwelling to recruit level 1, then its upgrade (II) and elite (III) buildings to recruit stronger levels.'),
      el('li', null, 'With an upgrade built, a hero in town can convert a whole stack by paying the price difference per creature (⬆ button).'),
      el('li', null, 'The Temple heals every wounded stack when your hero visits, and raises the fallen for their full price.')),
    el('h3', null, 'Battles'),
    el('ul', null,
      el('li', null, 'Armies are stacks of creatures. Select a stack, move it, then Attack, Heal or Wait. Each stack acts once per round.'),
      el('li', null, 'Damage = creatures × damage roll, +5% per point of Attack above the target\'s Defence (−2.5% per point below). Health carries over: the top creature may be wounded.'),
      el('li', null, 'Weapon triangle: Sword beats Axe, Axe beats Lance (and javelins), Lance beats Sword: +2 Attack for the winner, −2 for the loser.'),
      el('li', null, 'A stack strikes back once per round. Javelin skirmishers can throw at range; Hit and Run units fall back after attacking; cavalry with Charge hit harder the further they ride.'),
      el('li', null, 'Large creatures such as the Hydra and Talos fill 2×2 tiles. Forests, mountains and forts give Defence and cut damage taken.'),
      el('li', null, 'Your hero stays off the field: their Attack and Defence add to every stack, and Power fuels your god\'s divine power. Losses persist after battle.'))),
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
  for (const h of G.heroes) h.army.forEach(scan);
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
