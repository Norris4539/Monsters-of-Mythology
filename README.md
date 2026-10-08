# Pantheon: War of the Gods

A browser strategy game with a **Heroes of Might and Magic III–style adventure map** and **Fire Emblem Awakening–style tactical battles**. Rival pantheons from world mythology fight over a shared world.

No build step and no dependencies: it's plain HTML, CSS and JavaScript. Open `index.html` through any static server, for example `python3 -m http.server` and then open <http://localhost:8000/>. Enable GitHub Pages on `main` to play it at `https://norris4539.github.io/Monsters-of-Mythology/`.

## Factions

| Faction | Hero | God power | Roster (tier 1 → 7) |
|---|---|---|---|
| **Hellenes** (Greek) | Perseus | Zeus: *Thunderbolt*, 20 dmg to any enemy | Hoplite, Toxotes, Oracle of Delphi, Centaur, Pegasus Rider, Minotaur, Cyclops |
| **Kemet** (Egyptian) | Ramesses | Ra: *Solar Flare*, 8 dmg to every enemy | Medjay, Serket Scorpion, Chariot Archer, Priest of Thoth, Anubite Warden, Bennu Firebird, Sphinx |
| **Norsemen** (Scandinavian) | Ragnar | Thor: *Mjölnir*, 14 dmg plus 7 splash | Huskarl, Shieldmaiden, Völva, Úlfheðinn, Valkyrie, Mountain Troll, Frost Jötunn |
| **Yamato** (Japanese) | Raikō | Amaterasu: *Dawn*, full heal for all allies | Ashigaru, Yumi Archer, Samurai, Miko, Kitsune, Tengu, Oni |

Neutral creatures roam the wilds: dire wolves, skeletons, harpies, draugr, giant spiders, basilisks, griffins, hydras and ancient wyrms. Sometimes mercenary bands of faction units roam with them.

## Adventure map (HoMM3)

- The map is procedurally generated. Each faction starts in a corner with its own biome (grassland, desert, tundra, bamboo hills), and a marshy wasteland lies in the middle. Roads link the towns, and neutral towns can be captured.
- Heroes have 200 movement points per day. Roads cost less than rough terrain, and diagonal steps cost ×1.41. Click once to plot a path (green means reachable today, orange means later days, ⚔️ marks where a battle triggers). Click the same tile again to march.
- Map objects:
  - resource piles
  - treasure chests (gold or army XP)
  - mines (Gold Mine, Sawmill, Quarry, Ichor Spring) that you flag for daily income
  - shrines that give permanent hero stat boosts
  - guarded artifacts
- Monsters guard the 8 tiles around them, and stepping into that zone starts a fight, as in HoMM3. Hover a stack to see its zone and a threat rating.
- Towns build one structure per day. There are 7 dwellings, Town Hall and City Hall, Citadel (+50% growth), Walls (siege maps), Marketplace (trading) and a Temple (+ichor and a second god power per battle). New recruits arrive every week. You can recruit into the garrison from anywhere. To move units between the garrison and the army, visit the town.
- Resources are gold, wood, stone and ichor. Ichor is the rare one, needed for tier 6 and 7 units and buildings.
- Rival AI players explore, collect, build, recruit, fight monsters and besiege towns. Fights between two AIs are auto-resolved. Any fight that involves you is played as a tactical battle.
- You win by eliminating every rival: take their towns and defeat their hero. You lose if you have no towns and no hero, or if you go 7 days without a town. A defeated hero returns to a friendly town after 2 days with an empty army.

## Battles (Fire Emblem Awakening)

- 15×10 grid. Terrain is generated from the biome where the fight happens: forests, mountains, dunes, ruins, water and healing forts. Sieges of walled towns add a wall with gates.
- Player phase and enemy phase. Select a unit to see its move range (blue) and attack range (red), move it, then choose **Attack / Heal / Wait**. Clicking an enemy moves the unit to the best tile it can attack from.
- **Combat forecast**: damage, hit and crit, with ×2 for doubling. Then:
  - Damage = Str (or Mag) + weapon might − Def (or Res) − terrain defence
  - Hit = weapon hit + 2×Skl + Lck/2 − (2×Spd + Lck + terrain avoid)
  - Crits deal triple damage. A unit with at least 4 more Spd than its foe attacks twice.
- **Weapon triangle**: Sword > Axe > Lance > Sword (±15 hit, ±1 damage). Bows deal triple might to fliers. Tomes target Res.
- **Supports**: an adjacent ally gives +10 hit and avoid and may join in with a **Dual Strike**.
- Abilities: Heal, Regeneration, Lifesteal, Pierce (ignores half of Def/Res), Brave (strikes twice) and Deadly (+20 crit).
- **Commander**: if your hero falls, you lose the battle. If the enemy commander falls, their army routs.
- Once per battle, or twice with a Temple, your hero can call on their patron god.
- **Permadeath**: fallen units are gone. Survivors keep their XP and level-ups (FE-style growth rates) and heal fully after the battle. The **☠ Danger** button shows the combined enemy threat range.

## Code layout

| File | Contents |
|---|---|
| `js/data.js` | All game data: stats, weapons, terrain, factions, unit rosters, buildings, artifacts, shrines. Add a faction or unit here. |
| `js/core.js` | Helpers, unit instances, levelling, combat maths (`strikeStats`), power ratings. |
| `js/battle.js` | The tactical battle: map generation, input state machine, combat animation, enemy AI, god powers. `startBattle(opt)` returns a Promise. |
| `js/campaign.js` | Adventure-map state `G`: map generation, pathfinding with guard zones, interactions, towns, the day/week cycle, AI players. |
| `js/mapview.js` | Adventure-map canvas rendering, fog of war, minimap and input. |
| `js/ui.js` | Modals, side panel, town screen, main menu, save/load (`localStorage`, with an autosave each day). |

### Adding a faction

1. Add 7 units with `defUnit(id, faction, tier, name, icon, weapon, move, [hp,str,mag,skl,spd,lck,def,res,mov], abilities, description)`, plus a hero with `{ hero: true }`.
2. Add an entry to `FACTIONS` with colour, biome, town name and icon, dwelling names, temple, god power (`bolt`, `flare`, `hammer` or `dawn`, or add a new kind in `usePower`) and a blurb.
3. If it needs a new biome, add it to `TERRAIN` (adventure map) and `BTHEMES` (battles).

## Ideas for next steps

- Multiple heroes per player, a tavern, and hero skills or spellbooks (HoMM3).
- Pair Up / Dual Guard, support conversations and promotion classes (Awakening).
- More pantheons: Aztec, Celtic, Chinese, Hindu, Mesopotamian.
- Sprite art and sound in place of emoji, and a scripted campaign with story maps.
