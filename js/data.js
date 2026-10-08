'use strict';
// ─────────────────────────────────────────────────────────────────────────────
// Static game data: stats, weapons, terrain, factions, unit rosters, buildings.
// Everything here is plain data so new factions/units can be added by editing
// this file alone.
// ─────────────────────────────────────────────────────────────────────────────

const STATS = ['hp', 'str', 'mag', 'skl', 'spd', 'lck', 'def', 'res'];
const STAT_NAMES = { hp: 'HP', str: 'Str', mag: 'Mag', skl: 'Skl', spd: 'Spd', lck: 'Lck', def: 'Def', res: 'Res', mov: 'Mov' };
const MAX_LEVEL = 20;
const ARMY_CAP = 8;      // units a hero can lead, not counting the hero
const GARRISON_CAP = 8;

const RES = ['gold', 'wood', 'stone', 'ichor'];
const RES_INFO = {
  gold:  { name: 'Gold',  icon: '🪙' },
  wood:  { name: 'Wood',  icon: '🪵' },
  stone: { name: 'Stone', icon: '🪨' },
  ichor: { name: 'Ichor', icon: '💧' },
};

// Weapon triangle (Fire Emblem): sword > axe > lance > sword.
// Bows are effective (×3 might) against fliers. Tomes hit Res instead of Def.
const WEAPONS = {
  sword: { name: 'Sword',        mt: 4, hit: 90, crit: 5,  range: [1, 1] },
  lance: { name: 'Lance',        mt: 6, hit: 80, crit: 0,  range: [1, 1] },
  axe:   { name: 'Axe',          mt: 8, hit: 70, crit: 5,  range: [1, 1] },
  bow:   { name: 'Bow',          mt: 6, hit: 85, crit: 0,  range: [2, 2], effective: 'fly' },
  tome:  { name: 'Tome',         mt: 5, hit: 85, crit: 0,  range: [1, 2], magic: true },
  claw:  { name: 'Fang & Claw',  mt: 5, hit: 85, crit: 5,  range: [1, 1] },
  staff: { name: 'Staff',        mt: 0, hit: 0,  crit: 0,  range: [1, 1], heal: true },
};
const TRIANGLE = { sword: 'axe', axe: 'lance', lance: 'sword' }; // key beats value

const MOVE_TYPES = { foot: 'Infantry', armor: 'Armored', horse: 'Cavalry', fly: 'Flier' };

const ABILITIES = {
  heal:      'Heal — restores an adjacent ally (Mag + 10 HP).',
  regen:     'Regeneration — recovers 20% HP at the start of each turn.',
  lifesteal: 'Lifesteal — heals for half the damage dealt.',
  pierce:    'Pierce — ignores half of the target\'s Def/Res.',
  brave:     'Brave — strikes twice each time it attacks.',
  crit:      'Deadly — +20 critical rate.',
};

// Recruit cost & weekly growth by tier (Heroes 3 style dwellings).
const TIER_COST = {
  1: { gold: 150 }, 2: { gold: 250 }, 3: { gold: 400 }, 4: { gold: 600 },
  5: { gold: 900 }, 6: { gold: 1400, ichor: 1 }, 7: { gold: 2400, ichor: 2 },
};
const TIER_GROWTH = { 1: 3, 2: 3, 3: 2, 4: 2, 5: 1, 6: 1, 7: 1 };

const UNITS = {};
function defUnit(id, faction, tier, name, icon, weapon, move, b, abil = [], desc = '', w = {}) {
  const [hp, str, mag, skl, spd, lck, def, res, mov] = b;
  const base = { hp, str, mag, skl, spd, lck, def, res, mov };
  const hero = !!w.hero;
  const growth = {};
  for (const s of STATS) {
    growth[s] = s === 'hp' ? 55 + (hero ? 25 : tier * 4) : Math.max(5, Math.min(75, 10 + base[s] * 3 + (hero ? 15 : 0)));
  }
  const W = WEAPONS[weapon];
  const t = hero ? 4 : tier;
  UNITS[id] = {
    id, faction, tier, name, icon, weapon, move, base, growth, abil, desc, hero,
    mt: w.mt ?? (W.mt + Math.round(t * 1.2)),
    hit: w.hit ?? W.hit,
    crit: (w.crit ?? W.crit) + (abil.includes('crit') ? 20 : 0),
    range: w.range ?? W.range,
    group: w.group,
  };
}

// ── Hellenes ────────────────────────────────────────────────────────────────
//                                                       hp str mag skl spd lck def res mov
defUnit('hoplite',  'greek', 1, 'Hoplite',          '🛡️', 'lance', 'armor', [22, 7, 0, 5, 3, 3, 9, 1, 4], [], 'Bronze-clad spearmen of the phalanx.');
defUnit('toxotes',  'greek', 2, 'Toxotes',          '🏹', 'bow',   'foot',  [18, 6, 0, 8, 6, 4, 3, 2, 5], [], 'Cretan archers — deadly against winged foes.');
defUnit('oracle',   'greek', 3, 'Oracle of Delphi', '🔮', 'staff', 'foot',  [17, 0, 7, 5, 6, 8, 2, 8, 5], ['heal'], 'Pythian seers who mend wounds with Apollo\'s light.');
defUnit('centaur',  'greek', 4, 'Centaur',          '🐎', 'lance', 'horse', [26, 9, 0, 7, 7, 4, 6, 3, 7], [], 'Wild horse-folk hurling javelins.', { range: [1, 2] });
defUnit('pegasus',  'greek', 5, 'Pegasus Rider',    '🦄', 'lance', 'fly',   [24, 8, 2, 9, 11, 7, 5, 8, 7], [], 'Riders of the winged steeds of Olympus.');
defUnit('minotaur', 'greek', 6, 'Minotaur',         '🐂', 'axe',   'foot',  [38, 14, 0, 6, 6, 2, 10, 2, 5], ['brave'], 'Bull-headed terror of the Labyrinth.');
defUnit('cyclops',  'greek', 7, 'Cyclops',          '👁️', 'axe',   'foot',  [50, 18, 0, 7, 4, 2, 13, 4, 4], ['pierce'], 'Hephaestus\' one-eyed smiths, flinging boulders.', { range: [1, 2] });

// ── Egyptians ───────────────────────────────────────────────────────────────
defUnit('medjay',   'egypt', 1, 'Medjay Spearman',  '🔱', 'lance', 'foot',  [20, 7, 0, 6, 5, 4, 6, 2, 5], [], 'Desert guardians of the Pharaoh\'s cities.');
defUnit('scorpion', 'egypt', 2, 'Serket Scorpion',  '🦂', 'claw',  'foot',  [20, 8, 0, 6, 6, 2, 8, 1, 5], ['pierce'], 'Giant scorpions sacred to the goddess Serket.');
defUnit('chariot',  'egypt', 3, 'Chariot Archer',   '🏇', 'bow',   'horse', [22, 8, 0, 8, 7, 4, 5, 3, 7], [], 'Swift war-chariots raining arrows.');
defUnit('priest',   'egypt', 4, 'Priest of Thoth',  '☥',  'staff', 'foot',  [20, 0, 9, 6, 6, 7, 3, 10, 5], ['heal'], 'Ibis-masked scholars who know the words of healing.');
defUnit('anubite',  'egypt', 5, 'Anubite Warden',   '🐕', 'sword', 'foot',  [30, 11, 2, 11, 10, 5, 8, 6, 5], ['lifesteal'], 'Jackal-headed guardians of the Duat.');
defUnit('bennu',    'egypt', 6, 'Bennu Firebird',   '🔥', 'tome',  'fly',   [32, 3, 13, 10, 11, 8, 6, 12, 7], ['regen'], 'The undying heron of Heliopolis, reborn in flame.');
defUnit('sphinx',   'egypt', 7, 'Sphinx',           '🦁', 'claw',  'horse', [50, 15, 10, 10, 8, 10, 11, 12, 6], ['crit'], 'Riddle-keeper of Giza, lion-bodied and wise.');

// ── Norse ───────────────────────────────────────────────────────────────────
defUnit('huskarl',  'norse', 1, 'Huskarl',          '🪓', 'axe',   'foot',  [24, 8, 0, 4, 4, 2, 6, 1, 5], [], 'Sworn axemen of a jarl\'s household.');
defUnit('shieldm',  'norse', 2, 'Shieldmaiden',     '⚔️', 'sword', 'foot',  [20, 7, 0, 8, 8, 5, 5, 3, 5], [], 'Warrior women of the shield-wall.');
defUnit('volva',    'norse', 3, 'Völva',            '🌙', 'staff', 'foot',  [18, 0, 8, 5, 6, 7, 2, 8, 5], ['heal'], 'Seeresses who chant the galdr of mending.');
defUnit('ulfhedinn','norse', 4, 'Úlfheðinn',        '🐺', 'sword', 'foot',  [28, 10, 0, 9, 11, 3, 5, 2, 6], ['crit'], 'Wolf-pelted berserkers of Odin.');
defUnit('valkyrie', 'norse', 5, 'Valkyrie',         '🦢', 'lance', 'fly',   [26, 10, 4, 9, 11, 8, 6, 9, 7], [], 'Choosers of the slain on swan-white wings.');
defUnit('troll',    'norse', 6, 'Mountain Troll',   '🧌', 'axe',   'foot',  [42, 15, 0, 4, 4, 1, 11, 1, 5], ['regen'], 'Stone-hided brutes whose wounds knit shut.');
defUnit('jotunn',   'norse', 7, 'Frost Jötunn',     '❄️', 'axe',   'foot',  [55, 19, 6, 6, 5, 2, 12, 6, 4], ['pierce'], 'Giants of Jötunheimr, sworn foes of the Aesir.');

// ── Yamato (Japanese) ───────────────────────────────────────────────────────
defUnit('ashigaru', 'japan', 1, 'Ashigaru',         '🎌', 'lance', 'foot',  [19, 6, 0, 6, 6, 4, 6, 2, 5], [], 'Light spearmen levied from the provinces.');
defUnit('yumi',     'japan', 2, 'Yumi Archer',      '🎯', 'bow',   'foot',  [18, 6, 0, 9, 7, 5, 3, 3, 5], [], 'Masters of the great asymmetric bow.');
defUnit('samurai',  'japan', 3, 'Samurai',          '🗡️', 'sword', 'foot',  [24, 8, 0, 10, 9, 5, 6, 3, 5], ['crit'], 'Disciplined swordsmen of the warrior houses.');
defUnit('miko',     'japan', 4, 'Miko',             '🎐', 'staff', 'foot',  [20, 0, 9, 6, 7, 9, 3, 11, 5], ['heal'], 'Shrine maidens who channel the kami.');
defUnit('kitsune',  'japan', 5, 'Kitsune',          '🦊', 'tome',  'foot',  [24, 2, 11, 9, 12, 8, 4, 10, 6], [], 'Nine-tailed fox spirits wielding foxfire.');
defUnit('tengu',    'japan', 6, 'Tengu',            '👺', 'sword', 'fly',   [32, 12, 4, 12, 13, 7, 7, 8, 7], [], 'Crow-winged mountain goblins, peerless swordsmen.');
defUnit('oni',      'japan', 7, 'Oni',              '👹', 'axe',   'foot',  [52, 18, 0, 7, 5, 3, 12, 3, 5], ['brave'], 'Iron-clubbed ogres of Onigashima.');

// ── Heroes (lords) ──────────────────────────────────────────────────────────
defUnit('hero_greek', 'greek', 0, 'Perseus',  '🦸', 'sword', 'foot',  [28, 9, 2, 9, 9, 8, 7, 4, 5], [], 'Slayer of Medusa, son of Zeus.', { hero: true, mt: 8 });
defUnit('hero_egypt', 'egypt', 0, 'Ramesses', '👑', 'lance', 'horse', [28, 8, 5, 8, 8, 7, 7, 6, 6], [], 'Pharaoh of the Two Lands, beloved of Ra.', { hero: true, mt: 9 });
defUnit('hero_norse', 'norse', 0, 'Ragnar',   '🧔', 'axe',   'foot',  [30, 10, 0, 7, 8, 6, 8, 3, 5], [], 'Jarl and raider, who claims descent from Odin.', { hero: true, mt: 11 });
defUnit('hero_japan', 'japan', 0, 'Raikō',    '🏯', 'sword', 'foot',  [27, 9, 2, 10, 10, 7, 6, 5, 5], [], 'Minamoto no Raikō, slayer of the oni Shuten-dōji.', { hero: true, mt: 8 });

// ── Neutral creatures of the wilds ──────────────────────────────────────────
defUnit('wolf',     'neutral', 1, 'Dire Wolf',      '🐺', 'claw',  'foot',  [18, 6, 0, 5, 6, 2, 3, 1, 6], [], 'Hungry pack hunters.', { group: 'Wolf Pack' });
defUnit('skeleton', 'neutral', 1, 'Skeleton',       '💀', 'sword', 'foot',  [18, 6, 0, 5, 5, 0, 5, 1, 5], [], 'The restless dead.', { group: 'Restless Dead' });
defUnit('harpy',    'neutral', 2, 'Harpy',          '🦇', 'claw',  'fly',   [17, 6, 0, 6, 9, 3, 3, 3, 6], [], 'Shrieking snatchers of the winds.', { group: 'Harpy Flock' });
defUnit('draugr',   'neutral', 3, 'Draugr',         '🧟', 'axe',   'foot',  [26, 9, 0, 4, 4, 0, 8, 2, 4], ['regen'], 'Barrow-wights that will not stay down.', { group: 'Draugr Barrow' });
defUnit('spider',   'neutral', 3, 'Giant Spider',   '🕷️', 'claw',  'foot',  [22, 8, 0, 7, 8, 2, 4, 2, 5], ['pierce'], 'Venomous weavers of the deep woods.', { group: 'Spider Nest' });
defUnit('basilisk', 'neutral', 4, 'Basilisk',       '🦎', 'tome',  'foot',  [28, 4, 9, 7, 6, 2, 8, 8, 4], [], 'Its gaze burns like poison.', { group: 'Basilisk Lair' });
defUnit('griffin',  'neutral', 5, 'Griffin',        '🦅', 'claw',  'fly',   [30, 11, 0, 9, 11, 4, 6, 4, 7], [], 'Eagle-lion guardians of gold.', { group: 'Griffin Aerie' });
defUnit('hydra',    'neutral', 6, 'Hydra',          '🐍', 'claw',  'foot',  [45, 13, 0, 7, 5, 2, 10, 4, 4], ['brave', 'regen'], 'Cut one head, two grow back.', { group: 'Hydra' });
defUnit('wyrm',     'neutral', 7, 'Ancient Wyrm',   '🐲', 'tome',  'fly',   [60, 16, 14, 10, 8, 5, 14, 10, 6], ['pierce'], 'A dragon older than the gods.', { group: 'Ancient Wyrm' });

const NEUTRAL_UNITS = Object.values(UNITS).filter(u => u.faction === 'neutral').map(u => u.id);

// ── Factions ────────────────────────────────────────────────────────────────
const FACTIONS = {
  greek: {
    name: 'Hellenes', adj: 'Greek', color: '#3a78d8', biome: 'grass', hero: 'hero_greek',
    town: 'Athens', townIcon: '🏛️', god: 'Zeus', temple: 'Parthenon',
    units: ['hoplite', 'toxotes', 'oracle', 'centaur', 'pegasus', 'minotaur', 'cyclops'],
    dwellings: ['Phalanx Barracks', 'Archery Range', 'Delphic Sanctum', 'Centaur Glade', 'Pegasus Stables', 'Labyrinth', 'Forge of Hephaestus'],
    power: { name: 'Thunderbolt', kind: 'bolt', desc: 'Zeus strikes one enemy anywhere on the field for 20 damage.' },
    blurb: 'Disciplined phalanxes, centaurs and pegasi under the gaze of Olympus.',
  },
  egypt: {
    name: 'Kemet', adj: 'Egyptian', color: '#d6a21b', biome: 'sand', hero: 'hero_egypt',
    town: 'Thebes', townIcon: '🔺', god: 'Ra', temple: 'Temple of Karnak',
    units: ['medjay', 'scorpion', 'chariot', 'priest', 'anubite', 'bennu', 'sphinx'],
    dwellings: ['Medjay Barracks', 'Scorpion Pit', 'Chariot Yard', 'House of Thoth', 'Hall of the Duat', 'Heliopolis Spire', 'Giza Plateau'],
    power: { name: 'Solar Flare', kind: 'flare', desc: 'Ra scorches every enemy on the field for 8 damage.' },
    blurb: 'Chariots, scorpions and the undying servants of the sun god.',
  },
  norse: {
    name: 'Norsemen', adj: 'Norse', color: '#2e9e8f', biome: 'snow', hero: 'hero_norse',
    town: 'Uppsala', townIcon: '🏰', god: 'Thor', temple: 'Temple at Uppsala',
    units: ['huskarl', 'shieldm', 'volva', 'ulfhedinn', 'valkyrie', 'troll', 'jotunn'],
    dwellings: ['Mead Hall', 'Shield Wall', 'Seiðr Hut', 'Wolf Den', 'Hall of Valhalla', 'Troll Cave', 'Gate of Jötunheimr'],
    power: { name: 'Mjölnir', kind: 'hammer', desc: 'Thor hurls his hammer: 14 damage to one enemy and 7 to enemies beside it.' },
    blurb: 'Axes, berserkers and valkyries, with trolls and giants at the gate.',
  },
  japan: {
    name: 'Yamato', adj: 'Japanese', color: '#c23b5a', biome: 'bamboo', hero: 'hero_japan',
    town: 'Kyōto', townIcon: '⛩️', god: 'Amaterasu', temple: 'Grand Shrine of Ise',
    units: ['ashigaru', 'yumi', 'samurai', 'miko', 'kitsune', 'tengu', 'oni'],
    dwellings: ['Ashigaru Camp', 'Kyūdōjō', 'Dōjō', 'Shrine Hall', 'Inari Shrine', 'Mount Kurama', 'Onigashima Gate'],
    power: { name: 'Dawn of Amaterasu', kind: 'dawn', desc: 'The sun goddess restores every ally to full health.' },
    blurb: 'Samurai and archers allied with fox spirits, tengu and oni.',
  },
};
const FACTION_KEYS = Object.keys(FACTIONS);
const NEUTRAL_COLOR = '#8a8578';
const NEUTRAL_TOWNS = ['Delos', 'Memphis', 'Hedeby', 'Nara', 'Troy', 'Abydos', 'Birka', 'Izumo'];

// ── Town buildings ──────────────────────────────────────────────────────────
// d1..d7 are dwellings (names come from the faction). d1 is pre-built.
const BUILDINGS = {
  hall2:   { name: 'Town Hall',   cost: { gold: 2500 }, req: [], desc: 'Raises town income to 1000 gold per day.' },
  hall3:   { name: 'City Hall',   cost: { gold: 5000, wood: 5, stone: 5, ichor: 2 }, req: ['hall2', 'market'], desc: 'Raises town income to 2000 gold per day.' },
  market:  { name: 'Marketplace', cost: { gold: 500, wood: 5 }, req: [], desc: 'Lets you trade resources.' },
  citadel: { name: 'Citadel',     cost: { gold: 2500, stone: 10 }, req: [], desc: '+50% weekly recruits in every dwelling.' },
  walls:   { name: 'Walls',       cost: { gold: 1500, stone: 15 }, req: ['citadel'], desc: 'Defenders fight from behind walls and forts.' },
  temple:  { name: 'Temple',      cost: { gold: 2000, stone: 5, ichor: 2 }, req: ['d3'], desc: '+1 ichor per day. Your god answers twice per battle.' },
  d1: { cost: {}, req: [] },
  d2: { cost: { gold: 1000, wood: 5 }, req: ['d1'] },
  d3: { cost: { gold: 1500, stone: 5 }, req: ['d2'] },
  d4: { cost: { gold: 2000, wood: 5, stone: 5 }, req: ['d3'] },
  d5: { cost: { gold: 3000, stone: 10 }, req: ['d4'] },
  d6: { cost: { gold: 5000, wood: 10, ichor: 5 }, req: ['d5', 'citadel'] },
  d7: { cost: { gold: 8000, stone: 10, ichor: 10 }, req: ['d6', 'hall2'] },
};
const BUILD_ORDER = ['d2', 'd3', 'hall2', 'd4', 'market', 'citadel', 'd5', 'temple', 'walls', 'd6', 'hall3', 'd7'];
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

// ── Battle terrain (Fire Emblem style) ──────────────────────────────────────
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
// hero: stat bonus to the hero only; army: bonus to every unit incl. hero.
const ARTIFACTS = {
  aegis:     { name: 'Aegis of Athena',      icon: '🛡️', hero: { def: 4, res: 2 }, desc: 'Hero +4 Def, +2 Res' },
  fleece:    { name: 'Golden Fleece',        icon: '🐏', hero: { hp: 10 }, desc: 'Hero +10 HP' },
  talaria:   { name: 'Sandals of Hermes',    icon: '🪽', mp: 60, desc: '+60 movement points per day' },
  gungnir:   { name: 'Gungnir',              icon: '🔱', hero: { str: 3, skl: 4 }, desc: 'Hero +3 Str, +4 Skl' },
  draupnir:  { name: 'Draupnir',             icon: '💍', income: { gold: 500 }, desc: '+500 gold per day' },
  horus:     { name: 'Eye of Horus',         icon: '🧿', army: { skl: 3 }, desc: 'Army +3 Skl' },
  ankh:      { name: 'Ankh of Life',         icon: '☥',  army: { hp: 4 }, desc: 'Army +4 HP' },
  kusanagi:  { name: 'Kusanagi-no-Tsurugi',  icon: '🗡️', hero: { str: 4, spd: 2 }, desc: 'Hero +4 Str, +2 Spd' },
  yata:      { name: 'Yata no Kagami',       icon: '🪞', army: { res: 3 }, desc: 'Army +3 Res' },
  megingjord:{ name: 'Megingjörð',           icon: '🎗️', army: { str: 2 }, desc: 'Army +2 Str' },
  hadeshelm: { name: 'Helm of Hades',        icon: '⛑️', army: { spd: 1, lck: 4 }, desc: 'Army +1 Spd, +4 Lck' },
  khepri:    { name: 'Scarab of Khepri',     icon: '🪲', income: { ichor: 1 }, desc: '+1 ichor per day' },
};
const SHRINES = [
  { name: 'Shrine of Ares',       stat: 'str', val: 2 },
  { name: 'Shrine of Athena',     stat: 'skl', val: 2 },
  { name: 'Shrine of Hermes',     stat: 'spd', val: 2 },
  { name: 'Altar of Thoth',       stat: 'mag', val: 2 },
  { name: 'Hearth of Hephaestus', stat: 'def', val: 2 },
  { name: 'Well of Urðr',         stat: 'lck', val: 3 },
  { name: 'Spring of Asclepius',  stat: 'hp',  val: 5 },
  { name: 'Torii of Inari',       stat: 'res', val: 2 },
];
