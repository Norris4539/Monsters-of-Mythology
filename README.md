# Pantheon: War of the Gods

A browser strategy game with a **Heroes of Might and Magic III–style adventure map** and **grid battles that mix Fire Emblem Awakening maps with Heroes III creature stacks**. Rival pantheons from world mythology fight over a shared world.

No build step and no dependencies: it's plain HTML, CSS and JavaScript. Open `index.html` through any static server, for example `python3 -m http.server` and then open <http://localhost:8000/>. Enable GitHub Pages on `main` to play it at `https://norris4539.github.io/Monsters-of-Mythology/`.

## Factions

| Faction | Hero | God power | Roster (tier 1 → 7) |
|---|---|---|---|
| **Hellenes** (Greek) | Perseus | Zeus: *Thunderbolt* strikes one stack | Peltast, Ephebe/Hoplite, Hamippoi, Minotaur, Prodromoi/Hippeis, Hydra, Bronze Automaton/Talos |
| **Kemet** (Egyptian) | Ramesses | Ra: *Solar Flare* scorches every enemy | Medjay, Serket Scorpion, Chariot Archer, Priest of Thoth, Anubite Warden, Bennu Firebird, Sphinx |
| **Norsemen** (Scandinavian) | Ragnar | Thor: *Mjölnir* hits one stack and splashes its neighbours | Huskarl, Shieldmaiden, Völva, Úlfheðinn, Valkyrie, Mountain Troll, Frost Jötunn |
| **Yamato** (Japanese) | Raikō | Amaterasu: *Dawn* heals and raises allies | Ashigaru, Yumi Archer, Samurai, Miko, Kitsune, Tengu, Oni |

Every creature line has three levels. The Greek lines are hand-tuned, with two classes:

| Tier | Level 1 → 2 → 3 | Class | Abilities |
|---|---|---|---|
| 1 | Peltast → Thracian Peltast → Agrianian | Light | Javelins (range 1–2), Hit and Run |
| 2 | Ephebe → Hoplite → Sacred Band | Heavy | Phalanx; Long spears (attacks at range 1 that cannot be retaliated against); the Sacred Band adds Bond |
| 3 | Hamippoi → Boeotian Hamippoi → Epilektoi Hamippoi | Light | Javelins at range 2 for half damage with no retaliation, full strength in melee; runs with the horse (+Attack and Move next to cavalry) |
| 4 | Minotaur → Labrys Guard → Asterion | Heavy | Cleave |
| 5 | Prodromoi → Hippeis → Hetairoi (melee) | Light | Prodromoi: javelins at range 2 for half damage, and Charge (+5% damage per tile moved). Melee branch: lance and Charge |
| 5 | Prodromoi → Hippakontistai → Tarantine (ranged) | Light | Ranged branch: javelins at range 1–3 at full damage, Hit and Run |
| 6 | Marsh Hydra → Lernaean Hydra → Hydra Matriarch | Heavy, 2×2 | Many heads (hits every adjacent enemy), Regrowth |
| 7 | Bronze Automaton → Talos → Colossus | Heavy, 2×2 | Siege, Bleeding ichor |

Neutral creatures roam the wilds: dire wolves, skeletons, harpies, draugr, giant spiders, basilisks, griffins and ancient wyrms. They also come in three levels, stronger further from the capitals. Sometimes mercenary bands of faction units roam with them.

## Adventure map (HoMM3)

- The map is procedurally generated. Each faction starts in a corner with its own biome (grassland, desert, tundra, bamboo hills), and a marshy wasteland lies in the middle. Roads link the towns, and neutral towns can be captured.
- Heroes have 200 movement points per day. Roads cost less than rough terrain, and diagonal steps cost ×1.41. Click once to plot a path (green means reachable today, orange means later days, ⚔️ marks where a battle triggers). Click the same tile again to march.
- Map objects:
  - resource piles
  - treasure chests (gold or hero experience)
  - mines (Gold Mine, Sawmill, Quarry, Ichor Spring) that you flag for daily income
  - shrines that give permanent hero stat boosts
  - guarded artifacts
- Monsters guard the 8 tiles around them, and stepping into that zone starts a fight, as in HoMM3. Hover a stack to see its zone and a threat rating.
- Towns build one structure per day: 7 dwellings, each with an upgrade (II) and an elite (III) building, plus Town Hall and City Hall, Citadel (+50% growth), Walls (siege maps), Marketplace (trading) and a Temple.
- New recruits arrive every week. Each dwelling has one pool of creatures, which you can buy at any level the town has unlocked. Recruits join the hero if they are in town, otherwise the garrison.
- With an upgrade built, a hero in town can convert a whole stack to the next level by paying the price difference per creature.
- The **Temple** heals every wounded stack when your hero visits. It also raises the fallen (the creatures your hero lost in won battles) for their full price, ichor included for beasts. It gives +1 ichor per day and lets your god answer twice per battle.
- Some lines branch at levels 2 and 3. The Hippeis split into melee shock cavalry and ranged javelin cavalry: both are recruited from the same dwelling pool, and a level 1 stack can be upgraded into either branch. A branched stack stays on its branch.
- A hero leads up to 7 stacks; recruiting a creature type you already have merges it into that stack.
- Resources are gold, wood, stone and ichor. Ichor is the rare one, needed for tier 6 and 7 creatures, elite buildings and buildings for beasts.
- Rival AI players explore, collect, build, recruit, fight monsters and besiege towns. Fights between two AIs are auto-resolved. Any fight that involves you is played as a tactical battle.
- You win by eliminating every rival: take their towns and defeat their hero. You lose if you have no towns and no hero, or if you go 7 days without a town. A defeated hero returns to a friendly town after 2 days with an empty army.
- Heroes gain experience from battles and chests. Each level gives +1 Attack or Defence, and every third level +1 Power.

## Battles

- 15×10 grid. Terrain is generated from the biome where the fight happens: forests, mountains, dunes, ruins, water and healing forts. Sieges of walled towns add a wall with gates.
- Armies are **stacks** in the Heroes III style. Each stack has a creature count, Attack, Defence, Damage range, Health, Move and Resistance. Only the top creature of a stack can be wounded, and wounds carry over after the battle.
- Player phase and enemy phase, as in Fire Emblem. Select a stack to see its move range (blue) and attack range (red), move it, then choose **Attack / Heal / Wait**. Clicking an enemy moves the stack to the best tile it can attack from.
- **Damage** (Heroes III):
  - Base damage is one damage roll per creature.
  - It is then scaled by Attack against Defence: +5% per point above the target's Defence (up to +300%), or −2.5% per point below (down to −70%).
  - Terrain cover cuts damage taken.
  - The forecast shows the damage range, the expected kills and the retaliation.
- **Weapon triangle**: Sword > Axe > Lance (and javelins) > Sword, worth ±2 Attack.
- Every stack **retaliates once per round** against a melee attack. Ranged attacks are not answered.
- **Large creatures** (Hydras, Talos, Wyrms) fill 2×2 tiles.
- Your hero stays off the field. Their Attack and Defence add to every stack. Their Power scales the god power, which can be used once per battle, or twice with a Temple.
- You win by destroying every enemy stack. Retreating saves the hero but loses the whole army. The **☠ Danger** button shows the combined enemy threat range.

## 3D models (Blender)

The Hoplite line is modelled, rigged and animated by a Blender script in a Heroes III style: heroic proportions, bold silhouettes, a big painted shield and saturated colours.

- `tools/blender/hoplite.py` builds the model with Blender's Python module (`pip install bpy pillow`) and exports `assets/models/hoplite.glb`.
- One body and skeleton carry all three levels. Each piece of kit is a separate node named after its level (`L1_` Ephebe, `L2_` Hoplite, `L3_` Sacred Band, `L23_` shared by levels 2 and 3), so a renderer shows one level by toggling nodes by name.
- Animations: Idle, Walk, Thrust, Block, Hit and Death. The spear and shield are bones that the hands reach by IK.
- Shading is baked into the vertex colours as ambient occlusion, for a painted look without extra textures.

The game still draws units as emoji; the models are used by the 3D preview while the art direction is settled.

## Code layout

| File | Contents |
|---|---|
| `js/data.js` | All game data: creature lines and levels (`defLine`, `autoLine`), abilities, heroes, factions, buildings, terrain, artifacts, shrines. Add a faction or creature here. |
| `js/core.js` | Helpers, stacks (`makeStack`, `stackHp`, `addToArmy`), hero stats, Heroes III damage maths, army power ratings. |
| `js/battle.js` | The tactical battle: map generation, input state machine, combat animation, enemy AI, god powers. `startBattle(opt)` returns a Promise. |
| `js/campaign.js` | Adventure-map state `G`: map generation, pathfinding with guard zones, interactions, towns, the day/week cycle, AI players. |
| `js/mapview.js` | Adventure-map canvas rendering, fog of war, minimap and input. |
| `js/ui.js` | Modals, side panel, town screen, main menu, save/load (`localStorage`, with an autosave each day). |

### Adding a faction

1. Add 7 creature lines with `autoLine(id, faction, tier, name, icon, weapon, move, cls, opts)` (stats come from the tier templates in `TIER`) or hand-tune them with `defLine`. Add a hero to `HEROES`.
2. Add an entry to `FACTIONS` with colour, biome, town name and icon, dwelling names, temple, god power (`bolt`, `flare`, `hammer` or `dawn`, or add a new kind in `usePower`) and a blurb.
3. If it needs a new biome, add it to `TERRAIN` (adventure map) and `BTHEMES` (battles).

## Ideas for next steps

- Multiple heroes per player, a tavern, and hero skills or spellbooks (HoMM3).
- Pair Up / Dual Guard and support conversations (Awakening).
- 3D models for the creature levels (see the preview artifact).
- More pantheons: Aztec, Celtic, Chinese, Hindu, Mesopotamian.
- Sprite art and sound in place of emoji, and a scripted campaign with story maps.
