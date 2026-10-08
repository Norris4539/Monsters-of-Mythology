'use strict';
// ─────────────────────────────────────────────────────────────────────────────
// Static game data: unit lines, stats, terrain, factions, buildings.
//
// Armies are Heroes 3-style stacks: a stack is { type, n (count), hp (HP of the
// top creature) }. Every creature type belongs to a line with three levels
// (base → upgraded → elite); a town's dwelling upgrades unlock the higher ones.
// ─────────────────────────────────────────────────────────────────────────────

const ARMY_SLOTS = 7;     // stacks a hero can lead
const GARRISON_SLOTS = 7;

const RES = ['gold', 'wood', 'stone', 'ichor'];
const RES_INFO = {
  gold:  { name: 'Gold',  icon: '🪙' },
  wood:  { name: 'Wood',  icon: '🪵' },
  stone: { name: 'Stone', icon: '🪨' },
  ichor: { name: 'Ichor', icon: '💧' },
};

// Weapon triangle: sword > axe > lance (and javelin) > sword, worth ±2 Attack.
const WEAPONS = {
  sword:   { name: 'Sword' },
  lance:   { name: 'Spear' },
  javelin: { name: 'Javelins', tri: 'lance' },
  axe:     { name: 'Axe' },
  bow:     { name: 'Bow' },
  tome:    { name: 'Sorcery' },
  claw:    { name: 'Fang & Claw' },
  fist:    { name: 'Bronze fists' },
  staff:   { name: 'Staff' },
};
const TRIANGLE = { sword: 'axe', axe: 'lance', lance: 'sword' }; // key beats value
const triGroup = w => (WEAPONS[w] && WEAPONS[w].tri) || w;

const MOVE_TYPES = { foot: 'Infantry', armor: 'Armoured', horse: 'Cavalry', fly: 'Flier' };
const CLASSES = { heavy: 'Heavy', light: 'Light' };

const ABILITIES = {
  hitAndRun:   ['Hit and run', 'May move again with any movement left after attacking.'],
  phalanx:     ['Phalanx', '+2 Defence while next to another friendly Heavy stack.'],
  bond:        ['Sacred bond', '+1 Attack and Defence for each adjacent stack of the same kind.'],
  withHorse:   ['Run with the horse', '+2 Move and +2 Attack on turns it starts next to friendly cavalry.'],
  cleave:      ['Cleave', 'Also strikes another enemy beside the target for half damage.'],
  charge:      ['Charge', '+5% melee damage for every tile moved this turn.'],
  halfRange:   ['Javelin volley', 'Can attack at range 2 for half damage, without retaliation.'],
  manyHeads:   ['Many heads', 'Strikes every adjacent enemy at once; none can retaliate.'],
  regrow:      ['Regrowth', 'Its wounded top creature heals fully at the start of each turn.'],
  siege:       ['Siege engine', '+25% damage in siege battles.'],
  ichor:       ['Bleeding ichor', 'Below half strength, loses 2 Defence each turn.'],
  heal:        ['Heal', 'Instead of attacking, restores an adjacent ally and can raise its fallen.'],
  lifesteal:   ['Lifesteal', 'Heals for half the damage dealt and can raise its own fallen.'],
  pierce:      ['Pierce', 'Ignores half of the target\'s Defence.'],
  doubleStrike:['Double strike', 'Attacks twice.'],
  luck:        ['Fortune', '20% chance to deal double damage.'],
  large:       ['Large', 'Occupies 2×2 tiles.'],
};

// Tier templates for lines that are not hand-tuned, plus recruitment economy.
const TIER = {
  1: { att: 4,  def: 4,  dmg: [1, 3],   hp: 7,   mov: 5, res: 0,  grow: 14, cost: { gold: 70 } },
  2: { att: 6,  def: 6,  dmg: [2, 4],   hp: 13,  mov: 5, res: 5,  grow: 10, cost: { gold: 150 } },
  3: { att: 8,  def: 7,  dmg: [3, 6],   hp: 18,  mov: 6, res: 5,  grow: 8,  cost: { gold: 250 } },
  4: { att: 12, def: 11, dmg: [8, 14],  hp: 38,  mov: 6, res: 15, grow: 4,  cost: { gold: 550 } },
  5: { att: 15, def: 12, dmg: [12, 20], hp: 55,  mov: 7, res: 10, grow: 4,  cost: { gold: 800 } },
  6: { att: 18, def: 17, dmg: [25, 40], hp: 170, mov: 6, res: 25, grow: 2,  cost: { gold: 1800, ichor: 1 } },
  7: { att: 25, def: 26, dmg: [40, 60], hp: 380, mov: 6, res: 40, grow: 1,  cost: { gold: 3500, ichor: 3 } },
};
const LEVEL_COST = [1, 1.25, 1.6];   // price multiplier per level

const UNITS = {}, LINES = {};
const unitId = (line, lvl) => lvl === 1 ? line : `${line}_${lvl}`;
// lv: three level specs { name, att, def, dmg, hp, mov, res, abil? }
function defLine(id, faction, tier, cls, base, lv, desc) {
  const T = TIER[tier], L = { id, faction, tier, cls, desc, icon: base.icon, levels: [], grow: base.grow || T.grow };
  lv.forEach((s, i) => {
    const uid = unitId(id, i + 1);
    const cost = {}; for (const [k, v] of Object.entries(base.cost || T.cost)) cost[k] = Math.round(v * LEVEL_COST[i] / (k === 'gold' ? 5 : 1)) * (k === 'gold' ? 5 : 1);
    UNITS[uid] = {
      id: uid, line: id, lvl: i + 1, faction, tier, cls, desc,
      name: s.name, icon: base.icon, weapon: base.weapon, move: base.move,
      att: s.att, def: s.def, dmg: s.dmg, hp: s.hp, mov: s.mov, res: s.res,
      range: base.range || [1, 1], size: base.size || 1,
      abil: [...(base.abil || []), ...(s.abil || [])], cost,
    };
    L.levels.push(uid);
  });
  LINES[id] = L;
}
// Generic three-level line built from the tier template with small tweaks.
function autoLine(id, faction, tier, name, icon, weapon, move, cls, opts = {}) {
  const T = TIER[tier], h = cls === 'heavy';
  const att = T.att + (h ? -1 : 1) + (opts.att || 0), def = T.def + (h ? 2 : -1) + (opts.def || 0);
  const mov = T.mov + (h ? -1 : 0) + (move === 'horse' || move === 'fly' ? 2 : 0) + (opts.mov || 0);
  const names = opts.names || [name, `Veteran ${name}`, `Elite ${name}`];
  const lv = [0, 1, 2].map(i => ({
    name: names[i],
    att: Math.round(att * [1, 1.25, 1.5][i]), def: Math.round(def * [1, 1.25, 1.5][i]),
    dmg: T.dmg.map(d => Math.round(d * [1, 1.12, 1.25][i] * (opts.dmgMul || 1))),
    hp: Math.round(T.hp * [1, 1.12, 1.25][i] * (opts.hpMul || 1)),
    mov: mov + (h ? (i === 2 ? 1 : 0) : i), res: T.res + [0, 5, 10][i] + (opts.res || 0),
  }));
  defLine(id, faction, tier, cls, { icon, weapon, move, range: opts.range, size: opts.size, abil: opts.abil }, lv, opts.desc || '');
}

// ── Hellenes (hand-tuned) ───────────────────────────────────────────────────
defLine('peltast', 'greek', 1, 'light', { icon: '🎯', weapon: 'javelin', move: 'foot', range: [1, 2], abil: ['hitAndRun'], grow: 14, cost: { gold: 70 } }, [
  { name: 'Peltast',          att: 4, def: 3, dmg: [1, 3], hp: 6, mov: 6, res: 0 },
  { name: 'Thracian Peltast', att: 5, def: 4, dmg: [1, 4], hp: 7, mov: 7, res: 5 },
  { name: 'Agrianian',        att: 6, def: 5, dmg: [2, 4], hp: 8, mov: 8, res: 10 },
], 'Javelin skirmishers with a crescent wicker shield (pelte). They throw, then slip away.');
defLine('hoplite', 'greek', 2, 'heavy', { icon: '🛡️', weapon: 'lance', move: 'foot', abil: ['phalanx'], grow: 10, cost: { gold: 150 } }, [
  { name: 'Ephebe',      att: 4, def: 6,  dmg: [2, 3], hp: 12, mov: 4, res: 5 },
  { name: 'Hoplite',     att: 5, def: 8,  dmg: [2, 4], hp: 14, mov: 4, res: 10 },
  { name: 'Sacred Band', att: 6, def: 10, dmg: [3, 5], hp: 16, mov: 5, res: 15, abil: ['bond'] },
], 'Citizen spearmen in bronze behind the great round aspis: the backbone of the phalanx.');
defLine('hamippoi', 'greek', 3, 'light', { icon: '🏃', weapon: 'sword', move: 'foot', abil: ['withHorse'], grow: 8, cost: { gold: 250 } }, [
  { name: 'Hamippoi',           att: 7,  def: 5, dmg: [3, 5], hp: 14, mov: 6, res: 5 },
  { name: 'Boeotian Hamippoi',  att: 9,  def: 6, dmg: [3, 6], hp: 16, mov: 7, res: 10 },
  { name: 'Epilektoi Hamippoi', att: 11, def: 8, dmg: [4, 7], hp: 18, mov: 8, res: 15 },
], 'Runners who fought among the cavalry, keeping pace by holding the horses\' manes.');
defLine('minotaur', 'greek', 4, 'heavy', { icon: '🐂', weapon: 'axe', move: 'foot', abil: ['cleave'], grow: 4, cost: { gold: 550 } }, [
  { name: 'Minotaur',     att: 13, def: 12, dmg: [10, 18], hp: 45, mov: 5, res: 15 },
  { name: 'Labrys Guard', att: 16, def: 15, dmg: [12, 20], hp: 50, mov: 5, res: 20 },
  { name: 'Asterion',     att: 20, def: 19, dmg: [14, 24], hp: 60, mov: 6, res: 30 },
], 'The bull of Minos, swinging the Cretan double axe (labrys).');
defLine('hippeis', 'greek', 5, 'light', { icon: '🐎', weapon: 'lance', move: 'horse', range: [1, 2], abil: ['charge', 'halfRange'], grow: 4, cost: { gold: 800 } }, [
  { name: 'Prodromoi', att: 15, def: 10, dmg: [12, 20], hp: 55, mov: 8,  res: 5 },
  { name: 'Hippeis',   att: 19, def: 13, dmg: [14, 22], hp: 62, mov: 9,  res: 10 },
  { name: 'Hetairoi',  att: 24, def: 16, dmg: [16, 26], hp: 70, mov: 10, res: 15 },
], 'Greek horsemen who throw javelins, then charge home with the spear.');
defLine('hydra', 'greek', 6, 'heavy', { icon: '🐍', weapon: 'claw', move: 'foot', size: 2, abil: ['large', 'manyHeads', 'regrow'], grow: 2, cost: { gold: 1800, ichor: 1 } }, [
  { name: 'Marsh Hydra',     att: 18, def: 18, dmg: [25, 45], hp: 180, mov: 5, res: 25 },
  { name: 'Lernaean Hydra',  att: 23, def: 23, dmg: [30, 50], hp: 210, mov: 5, res: 30 },
  { name: 'Hydra Matriarch', att: 28, def: 28, dmg: [35, 60], hp: 250, mov: 6, res: 40 },
], 'The many-headed serpent of Lerna. Cut one head off and two grow back.');
defLine('talos', 'greek', 7, 'heavy', { icon: '🗿', weapon: 'fist', move: 'armor', size: 2, abil: ['large', 'siege', 'ichor'], grow: 1, cost: { gold: 3500, ichor: 3 } }, [
  { name: 'Bronze Automaton', att: 26, def: 30, dmg: [45, 60], hp: 400, mov: 4, res: 50 },
  { name: 'Talos',            att: 32, def: 37, dmg: [50, 70], hp: 450, mov: 4, res: 55 },
  { name: 'Colossus',         att: 40, def: 46, dmg: [60, 80], hp: 520, mov: 5, res: 65 },
], 'The bronze giant forged by Hephaestus to guard Crete. A single vein of ichor runs to a nail at his ankle.');

// ── Kemet (Egyptians) ───────────────────────────────────────────────────────
autoLine('medjay', 'egypt', 1, 'Medjay', '🔱', 'lance', 'foot', 'light', { desc: 'Desert guardians of the Pharaoh\'s cities.' });
autoLine('scorpion', 'egypt', 2, 'Serket Scorpion', '🦂', 'claw', 'foot', 'heavy', { abil: ['pierce'], desc: 'Giant scorpions sacred to Serket.' });
autoLine('chariot', 'egypt', 3, 'Chariot Archer', '🏇', 'bow', 'horse', 'light', { range: [2, 4], desc: 'Swift war-chariots raining arrows.' });
autoLine('priest', 'egypt', 4, 'Priest of Thoth', '☥', 'staff', 'foot', 'light', { abil: ['heal'], dmgMul: .4, desc: 'Scholars who know the words of healing.' });
autoLine('anubite', 'egypt', 5, 'Anubite Warden', '🐕', 'sword', 'foot', 'heavy', { abil: ['lifesteal'], desc: 'Jackal-headed guardians of the Duat.' });
autoLine('bennu', 'egypt', 6, 'Bennu Firebird', '🔥', 'tome', 'fly', 'light', { range: [1, 3], abil: ['regrow'], desc: 'The undying heron of Heliopolis.' });
autoLine('sphinx', 'egypt', 7, 'Sphinx', '🦁', 'claw', 'foot', 'heavy', { size: 2, abil: ['large', 'luck'], desc: 'Riddle-keeper of Giza.' });
// ── Norsemen ────────────────────────────────────────────────────────────────
autoLine('huskarl', 'norse', 1, 'Huskarl', '🪓', 'axe', 'foot', 'heavy', { desc: 'Sworn axemen of a jarl\'s household.' });
autoLine('shieldm', 'norse', 2, 'Shieldmaiden', '⚔️', 'sword', 'foot', 'light', { desc: 'Warrior women of the shield-wall.' });
autoLine('volva', 'norse', 3, 'Völva', '🌙', 'staff', 'foot', 'light', { abil: ['heal'], dmgMul: .4, desc: 'Seeresses who chant the galdr of mending.' });
autoLine('ulfhedinn', 'norse', 4, 'Úlfheðinn', '🐺', 'sword', 'foot', 'light', { abil: ['luck'], desc: 'Wolf-pelted berserkers of Odin.' });
autoLine('valkyrie', 'norse', 5, 'Valkyrie', '🦢', 'lance', 'fly', 'light', { desc: 'Choosers of the slain on swan-white wings.' });
autoLine('troll', 'norse', 6, 'Mountain Troll', '🧌', 'axe', 'foot', 'heavy', { abil: ['regrow'], desc: 'Stone-hided brutes whose wounds knit shut.' });
autoLine('jotunn', 'norse', 7, 'Frost Jötunn', '❄️', 'axe', 'armor', 'heavy', { size: 2, abil: ['large', 'pierce'], desc: 'Giants of Jötunheimr.' });
// ── Yamato ──────────────────────────────────────────────────────────────────
autoLine('ashigaru', 'japan', 1, 'Ashigaru', '🎌', 'lance', 'foot', 'light', { desc: 'Light spearmen levied from the provinces.' });
autoLine('yumi', 'japan', 2, 'Yumi Archer', '🏹', 'bow', 'foot', 'light', { range: [2, 4], desc: 'Masters of the great bow.' });
autoLine('samurai', 'japan', 3, 'Samurai', '🗡️', 'sword', 'foot', 'heavy', { abil: ['luck'], desc: 'Disciplined swordsmen of the warrior houses.' });
autoLine('miko', 'japan', 4, 'Miko', '🎐', 'staff', 'foot', 'light', { abil: ['heal'], dmgMul: .4, desc: 'Shrine maidens who channel the kami.' });
autoLine('kitsune', 'japan', 5, 'Kitsune', '🦊', 'tome', 'foot', 'light', { range: [1, 3], desc: 'Nine-tailed fox spirits wielding foxfire.' });
autoLine('tengu', 'japan', 6, 'Tengu', '👺', 'sword', 'fly', 'light', { desc: 'Crow-winged mountain goblins.' });
autoLine('oni', 'japan', 7, 'Oni', '👹', 'axe', 'foot', 'heavy', { size: 2, abil: ['large', 'doubleStrike'], desc: 'Iron-clubbed ogres of Onigashima.' });
// ── Neutral creatures (levels used for tougher wandering stacks) ────────────
autoLine('wolf', 'neutral', 1, 'Dire Wolf', '🐺', 'claw', 'foot', 'light', { names: ['Dire Wolf', 'Grey Wolf', 'Alpha Wolf'] });
autoLine('skeleton', 'neutral', 1, 'Skeleton', '💀', 'sword', 'foot', 'heavy', { names: ['Skeleton', 'Skeleton Warrior', 'Skeleton Champion'] });
autoLine('harpy', 'neutral', 2, 'Harpy', '🦇', 'claw', 'fly', 'light', { abil: ['hitAndRun'], names: ['Harpy', 'Harpy Hag', 'Harpy Queen'] });
autoLine('draugr', 'neutral', 3, 'Draugr', '🧟', 'axe', 'foot', 'heavy', { abil: ['regrow'], names: ['Draugr', 'Barrow Draugr', 'Draugr Lord'] });
autoLine('spider', 'neutral', 3, 'Giant Spider', '🕷️', 'claw', 'foot', 'light', { abil: ['pierce'], names: ['Giant Spider', 'Venom Spider', 'Spider Queen'] });
autoLine('basilisk', 'neutral', 4, 'Basilisk', '🦎', 'tome', 'foot', 'heavy', { range: [1, 2], names: ['Basilisk', 'Greater Basilisk', 'Basilisk King'] });
autoLine('griffin', 'neutral', 5, 'Griffin', '🦅', 'claw', 'fly', 'light', { names: ['Griffin', 'Royal Griffin', 'Griffin Lord'] });
autoLine('wyrm', 'neutral', 7, 'Ancient Wyrm', '🐲', 'tome', 'fly', 'heavy', { size: 2, range: [1, 2], abil: ['large', 'pierce'], names: ['Young Wyrm', 'Ancient Wyrm', 'Elder Wyrm'] });
const NEUTRAL_LINES = Object.values(LINES).filter(l => l.faction === 'neutral').map(l => l.id);
const GROUP_NAMES = { wolf: 'Wolf Pack', skeleton: 'Restless Dead', harpy: 'Harpy Flock', draugr: 'Draugr Barrow', spider: 'Spider Nest', basilisk: 'Basilisk Lair', griffin: 'Griffin Aerie', wyrm: 'Ancient Wyrm' };

// ── Heroes (commanders; they lead from behind and boost the army) ───────────
const HEROES = {
  hero_greek: { name: 'Perseus',  icon: '🦸', att: 2, def: 1, power: 1, desc: 'Slayer of Medusa, son of Zeus.' },
  hero_egypt: { name: 'Ramesses', icon: '👑', att: 1, def: 1, power: 2, desc: 'Pharaoh of the Two Lands, beloved of Ra.' },
  hero_norse: { name: 'Ragnar',   icon: '🧔', att: 2, def: 2, power: 0, desc: 'Jarl and raider, who claims descent from Odin.' },
  hero_japan: { name: 'Raikō',    icon: '🏯', att: 1, def: 2, power: 1, desc: 'Minamoto no Raikō, slayer of the oni Shuten-dōji.' },
};
const xpForLevel = l => Math.round(600 * Math.pow(l, 1.6));

// ── Factions ────────────────────────────────────────────────────────────────
const FACTIONS = {
  greek: {
    name: 'Hellenes', adj: 'Greek', color: '#3a78d8', biome: 'grass', hero: 'hero_greek',
    town: 'Athens', townIcon: '🏛️', god: 'Zeus', temple: 'Parthenon',
    units: ['peltast', 'hoplite', 'hamippoi', 'minotaur', 'hippeis', 'hydra', 'talos'],
    dwellings: ['Peltast Camp', 'Phalanx Barracks', 'Hamippoi Track', 'Labyrinth', 'Hippodrome', 'Lernaean Marsh', 'Forge of Hephaestus'],
    power: { name: 'Thunderbolt', kind: 'bolt', desc: 'Zeus strikes one enemy stack anywhere on the field.' },
    blurb: 'A tough phalanx army with a fast wing of runners and horsemen, backed by the Hydra and bronze Talos.',
  },
  egypt: {
    name: 'Kemet', adj: 'Egyptian', color: '#d6a21b', biome: 'sand', hero: 'hero_egypt',
    town: 'Thebes', townIcon: '🔺', god: 'Ra', temple: 'Temple of Karnak',
    units: ['medjay', 'scorpion', 'chariot', 'priest', 'anubite', 'bennu', 'sphinx'],
    dwellings: ['Medjay Barracks', 'Scorpion Pit', 'Chariot Yard', 'House of Thoth', 'Hall of the Duat', 'Heliopolis Spire', 'Giza Plateau'],
    power: { name: 'Solar Flare', kind: 'flare', desc: 'Ra scorches every enemy stack on the field.' },
    blurb: 'Chariots, scorpions and the undying servants of the sun god.',
  },
  norse: {
    name: 'Norsemen', adj: 'Norse', color: '#2e9e8f', biome: 'snow', hero: 'hero_norse',
    town: 'Uppsala', townIcon: '🏰', god: 'Thor', temple: 'Temple at Uppsala',
    units: ['huskarl', 'shieldm', 'volva', 'ulfhedinn', 'valkyrie', 'troll', 'jotunn'],
    dwellings: ['Mead Hall', 'Shield Wall', 'Seiðr Hut', 'Wolf Den', 'Hall of Valhalla', 'Troll Cave', 'Gate of Jötunheimr'],
    power: { name: 'Mjölnir', kind: 'hammer', desc: 'Thor\'s hammer smashes one stack and splashes the stacks beside it.' },
    blurb: 'Axes, berserkers and valkyries, with trolls and giants at the gate.',
  },
  japan: {
    name: 'Yamato', adj: 'Japanese', color: '#c23b5a', biome: 'bamboo', hero: 'hero_japan',
    town: 'Kyōto', townIcon: '⛩️', god: 'Amaterasu', temple: 'Grand Shrine of Ise',
    units: ['ashigaru', 'yumi', 'samurai', 'miko', 'kitsune', 'tengu', 'oni'],
    dwellings: ['Ashigaru Camp', 'Kyūdōjō', 'Dōjō', 'Shrine Hall', 'Inari Shrine', 'Mount Kurama', 'Onigashima Gate'],
    power: { name: 'Dawn of Amaterasu', kind: 'dawn', desc: 'The sun goddess heals every allied stack and raises some of its fallen.' },
    blurb: 'Samurai and archers allied with fox spirits, tengu and oni.',
  },
};
const FACTION_KEYS = Object.keys(FACTIONS);
const NEUTRAL_COLOR = '#8a8578';
const NEUTRAL_TOWNS = ['Delos', 'Memphis', 'Hedeby', 'Nara', 'Troy', 'Abydos', 'Birka', 'Izumo'];

// ── Town buildings ──────────────────────────────────────────────────────────
// d1..d7 dwellings, u1..u7 upgrade them to level 2, e1..e7 to level 3 (elite).
const BUILDINGS = {
  hall2:   { name: 'Town Hall',   cost: { gold: 2500 }, req: [], desc: 'Raises town income to 1000 gold per day.' },
  hall3:   { name: 'City Hall',   cost: { gold: 5000, wood: 5, stone: 5, ichor: 2 }, req: ['hall2', 'market'], desc: 'Raises town income to 2000 gold per day.' },
  market:  { name: 'Marketplace', cost: { gold: 500, wood: 5 }, req: [], desc: 'Lets you trade resources.' },
  citadel: { name: 'Citadel',     cost: { gold: 2500, stone: 10 }, req: [], desc: '+50% weekly recruits in every dwelling.' },
  walls:   { name: 'Walls',       cost: { gold: 1500, stone: 15 }, req: ['citadel'], desc: 'Defenders fight from behind walls and forts.' },
  temple:  { name: 'Temple',      cost: { gold: 2000, stone: 5, ichor: 2 }, req: ['d2'], desc: 'Heals wounded stacks of visiting heroes and garrisons, and raises the fallen for gold. +1 ichor per day; your god answers twice per battle.' },
};
const DWELLING_COST = {
  1: {}, 2: { gold: 1000, wood: 5 }, 3: { gold: 1500, stone: 5 }, 4: { gold: 2000, wood: 5, stone: 5 },
  5: { gold: 3000, stone: 10 }, 6: { gold: 5000, wood: 10, ichor: 5 }, 7: { gold: 8000, stone: 10, ichor: 10 },
};
for (let t = 1; t <= 7; t++) {
  BUILDINGS['d' + t] = { cost: DWELLING_COST[t], req: t === 1 ? [] : ['d' + (t - 1), ...(t === 6 ? ['citadel'] : t === 7 ? ['hall2'] : [])] };
  const base = t === 1 ? { gold: 500, wood: 5 } : DWELLING_COST[t];
  const scale = (c, m, extra = {}) => { const o = {}; for (const [k, v] of Object.entries(c)) o[k] = Math.round(v * m / (k === 'gold' ? 50 : 1)) * (k === 'gold' ? 50 : 1); for (const [k, v] of Object.entries(extra)) o[k] = (o[k] || 0) + v; return o; };
  BUILDINGS['u' + t] = { cost: scale(base, .75), req: ['d' + t], level: 2 };
  BUILDINGS['e' + t] = { cost: scale(base, 1.25, t >= 4 ? { ichor: 2 } : {}), req: ['u' + t, ...(t >= 4 ? ['citadel'] : [])], level: 3 };
}
const BUILD_ORDER = ['d2', 'u1', 'd3', 'hall2', 'u2', 'temple', 'd4', 'market', 'citadel', 'u3', 'd5', 'u4', 'walls', 'e1', 'e2', 'd6', 'u5', 'hall3', 'e3', 'd7', 'u6', 'e4', 'e5', 'u7', 'e6', 'e7'];
const MARKET = { wood: { sell: 60, buy: 250 }, stone: { sell: 60, buy: 250 }, ichor: { sell: 200, buy: 700 } };

// ── Adventure map terrain ───────────────────────────────────────────────────
// Movement cost per tile (×10); a hero has 200 movement points per day.
const TERRAIN = {
  grass:  { name: 'Grassland', cost: 20, color: '#6f9a4c', dot: '#5e8a3e', trees: ['🌳', '🌲', '🌳'], rocks: ['⛰️'] },
  bamboo: { name: 'Bamboo Hills', cost: 20, color: '#7aa35a', dot: '#6a924a', trees: ['🎋', '🌸', '🌲'], rocks: ['🗻', '⛰️'] },
  sand:   { name: 'Desert',    cost: 30, color: '#d9c27e', dot: '#c9b06a', trees: ['🌵', '🌴'], rocks: ['⛰️', '🏜️'] },
  snow:   { name: 'Tundra',    cost: 30, color: '#e3ebef', dot: '#cfdbe2', trees: ['🌲', '🌲'], rocks: ['🏔️'] },
  dirt:   { name: 'Wasteland', cost: 25, color: '#9c8160', dot: '#8b7152', trees: ['🌳', '🍂'], rocks: ['⛰️', '🪨'] },
  swamp:  { name: 'Marsh',     cost: 35, color: '#5f6d4b', dot: '#525f40', trees: ['🌿', '🌳'], rocks: ['🪨'] },
  water:  { name: 'Water',     cost: 999, color: '#3b6ea8', dot: '#4a7db6' },
};
const ROAD_COST = 10;
const BASE_MP = 200;

// ── Battle terrain ───────────────────────────────────────────────────────────────────────────────────────────────
const BTER = {
  plain:  { name: 'Plain',    avo: 0,  def: 0, cost: { foot: 1, armor: 1, horse: 1, fly: 1 } },
  forest: { name: 'Forest',   avo: 20, def: 1, cost: { foot: 2, armor: 2, horse: 3, fly: 1 } },
  hill:   { name: 'Mountain', avo: 30, def: 2, cost: { foot: 3, armor: 99, horse: 99, fly: 1 } },
  dune:   { name: 'Dunes',    avo: 5,  def: 0, cost: { foot: 2, armor: 3, horse: 3, fly: 1 } },
  ruins:  { name: 'Ruins',    avo: 20, def: 1, cost: { foot: 2, armor: 2, horse: 2, fly: 1 } },
  water:  { name: 'Water',    avo: 0,  def: 0, cost: { foot: 99, armor: 99, horse: 99, fly: 1 } },
  wall:   { name: 'Wall',     avo: 0,  def: 0, cost: { foot: 99, armor: 99, horse: 99, fly: 99 } },
  fort:   { name: 'Fort',     avo: 20, def: 2, heal: 20, cost: { foot: 2, armor: 2, horse: 2, fly: 1 } },
  gate:   { name: 'Gate',     avo: 10, def: 3, heal: 10, cost: { foot: 1, armor: 1, horse: 1, fly: 1 } },
};
const BTHEMES = {
  grass:  { plain: '#7da55a', alt: '#769d53', feats: { forest: '🌳', hill: '⛰️', ruins: '🏚️', fort: '🏛️' }, mix: ['forest', 'forest', 'hill', 'water', 'ruins'] },
  bamboo: { plain: '#86ad63', alt: '#7fa65c', feats: { forest: '🎋', hill: '🗻', ruins: '🏮', fort: '⛩️' }, mix: ['forest', 'forest', 'hill', 'water', 'ruins'] },
  sand:   { plain: '#dcc68a', alt: '#d5be80', feats: { forest: '🌴', hill: '⛰️', dune: '', ruins: '🗿', fort: '🔺' }, mix: ['dune', 'dune', 'hill', 'ruins', 'water', 'forest'] },
  snow:   { plain: '#e4ecf0', alt: '#dbe4e9', feats: { forest: '🌲', hill: '🏔️', ruins: '🪨', fort: '🏰' }, mix: ['forest', 'forest', 'hill', 'water', 'ruins'] },
  dirt:   { plain: '#a68b69', alt: '#9e8462', feats: { forest: '🌳', hill: '⛰️', ruins: '🪨', fort: '🏰' }, mix: ['forest', 'hill', 'ruins', 'ruins', 'water'] },
  swamp:  { plain: '#6d7c55', alt: '#67754f', feats: { forest: '🌿', hill: '🪨', ruins: '🪵', fort: '🛖' }, mix: ['forest', 'water', 'water', 'forest', 'ruins'] },
};

// ── Artifacts & shrines ─────────────────────────────────────────────────────
// hero: raises the hero's Attack/Defence/Power; army: bonus to every stack.
const ARTIFACTS = {
  aegis:     { name: 'Aegis of Athena',      icon: '🛡️', hero: { def: 3 }, desc: 'Hero +3 Defence' },
  fleece:    { name: 'Golden Fleece',        icon: '🐏', army: { hpPct: 10 }, desc: 'Army +10% health' },
  talaria:   { name: 'Sandals of Hermes',    icon: '🪽', mp: 60, desc: '+60 movement points per day' },
  gungnir:   { name: 'Gungnir',              icon: '🔱', hero: { att: 3 }, desc: 'Hero +3 Attack' },
  draupnir:  { name: 'Draupnir',             icon: '💍', income: { gold: 500 }, desc: '+500 gold per day' },
  horus:     { name: 'Eye of Horus',         icon: '🧿', hero: { power: 2 }, desc: 'Hero +2 Power' },
  ankh:      { name: 'Ankh of Life',         icon: '☥',  army: { hpPct: 15 }, desc: 'Army +15% health' },
  kusanagi:  { name: 'Kusanagi-no-Tsurugi',  icon: '🗡️', hero: { att: 2, def: 1 }, desc: 'Hero +2 Attack, +1 Defence' },
  yata:      { name: 'Yata no Kagami',       icon: '🪞', army: { res: 10 }, desc: 'Army +10% Resistance' },
  megingjord:{ name: 'Megingjörð',           icon: '🎗️', hero: { att: 2, power: 1 }, desc: 'Hero +2 Attack, +1 Power' },
  hadeshelm: { name: 'Helm of Hades',        icon: '⛑️', army: { mov: 1 }, desc: 'Army +1 Move' },
  khepri:    { name: 'Scarab of Khepri',     icon: '🪲', income: { ichor: 1 }, desc: '+1 ichor per day' },
};
const SHRINES = [
  { name: 'Shrine of Ares',       stat: 'att',   val: 2 },
  { name: 'Shrine of Athena',     stat: 'def',   val: 2 },
  { name: 'Altar of Thoth',       stat: 'power', val: 1 },
  { name: 'Hearth of Hephaestus', stat: 'def',   val: 1 },
  { name: 'Well of Urðr',         stat: 'power', val: 1 },
  { name: 'Torii of Inari',       stat: 'att',   val: 1 },
];
const HERO_STAT = { att: 'Attack', def: 'Defence', power: 'Power' };
