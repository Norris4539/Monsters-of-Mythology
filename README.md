# Pantheon: War of the Gods

A browser strategy game with a **Heroes of Might and Magic III–style adventure map** and **grid battles that mix Fire Emblem Awakening maps with Heroes III creature stacks**. Rival pantheons from world mythology fight over a shared world.

No build step and no dependencies: it's plain HTML, CSS and JavaScript. Open `index.html` through any static server, for example `python3 -m http.server` and then open <http://localhost:8000/>. Enable GitHub Pages on `main` to play it at `https://norris4539.github.io/Monsters-of-Mythology/`.

## Factions

| Faction | Hero | God power | Roster (tier 1 → 7) |
|---|---|---|---|
| **Hellenes** (Greek) | Perseus | Zeus: *Thunderbolt* strikes one stack | Peltast, Ephebe/Hoplite, Hamippoi, Minotaur, Prodromoi/Hippeis, Hydra, Bronze Automaton/Talos |
| **Kemet** (Egyptian) | Ramesses | Ra: *Solar Flare* scorches every enemy | Medjay, Serket Scorpion, Chariot Archer, Priest of Thoth, Anubite Warden, Bennu Firebird, Akhekh Griffin |
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
- Some lines branch at levels 2 and 3. The Hippeis split into melee shock cavalry and ranged javelin cavalry, and Kemet's chariots into archers (Veteran and Elite Chariot Archer) and a spear crew who charge into melee (Chariot Spearman and Royal Chariot Guard). Both branches are recruited from the same dwelling pool, and a level 1 stack can be upgraded into either branch. A branched stack stays on its branch.
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

Every Greek line (Peltast, Hoplite, Hamippoi, Minotaur, Hippeis, Hydra and Talos), the horse and every Kemet line (Medjay, Serket Scorpion, Chariot, Priest of Thoth, Anubite Warden, Bennu Firebird and Akhekh Griffin) are modelled, rigged and animated by Blender scripts in a realistic style.

- `tools/blender/fetch_makehuman.py` downloads the MakeHuman base mesh and shape targets (CC0 1.0, public domain) into `third_party/makehuman`.
- `tools/blender/hoplite.py` runs with Blender's Python module (`pip install bpy pillow`) and exports `assets/models/hoplite.glb`:
  - the body is the MakeHuman base mesh shaped into a young, athletic Mediterranean man at 1.76 m;
  - the muscle cuirass, linothorax and greaves are grown from the body's surface, helmets are smooth hulls over the skull, and the chiton and cloaks are draped with the cloth simulator;
  - procedural materials (skin, hammered bronze with patina, painted shields, linen, leather, wool, ash) are baked into colour, roughness and normal textures;
  - one skeleton carries all three levels; kit nodes are named `L1_` (Ephebe), `L2_` (Hoplite), `L3_` (Sacred Band) or `L23_` (levels 2 and 3), so a renderer shows one level by name;
  - animations: Idle, Walk, Thrust, Block, Hit and Death. Arms and legs are solved in the script (shoulder to wrist target, elbow towards a natural hint) and keyed as plain rotations, so the browser plays exactly what Blender shows. The spear is held overhand through the right fist, and the shield is strapped to the left forearm by the porpax with the hand on the antilabe.
- `tools/blender/peltast.py` reuses the Hoplite pipeline and exports `assets/models/peltast.glb`:
  - a leaner man at 1.74 m with curly hair and a beard per level (stubble, a full Thracian beard, a trimmed one);
  - `L1_` Peltast: undyed exomis with the right shoulder bare, fringed hem, rope belt, barefoot, a wicker pelte faced with hide;
  - `L2_` Thracian Peltast: fox-skin alopekis with the fox's mask and tail, patterned zeira, fringed tunic, fur-topped fawnskin boots, a pelte painted with a face, a curved knife;
  - `L3_` Agrianian: Thracian helmet with peak, cheek pieces and plume, patterned tunic, olive cloak, laced boots, a round shield with a meander border, a machaira;
  - animations: Idle, Walk, Throw, Thrust, Block, Hit and Death. The javelin in the right hand is its own node, `ThrowJavelin`, so a renderer can hide it from the release (frame 12 of Throw) while a thrown copy flies; the spares are held behind the shield.
  - its face kit (beards, curly hair, eyes), arm-region selection and scabbard builder are shared with the Hamippoi.
- `tools/blender/hamippoi.py` builds on both and exports `assets/models/hamippoi.glb`:
  - a lean runner at 1.75 m with fuller curly hair; a short beard, a full beard, stubble;
  - `L1_` Hamippoi: ochre wool tunic with woven zigzag borders at the neck, sleeves and hem, leather belt with a bronze buckle, a knife at the right hip, a petasos hung on the back from a cord round the neck, two javelins;
  - `L2_` Boeotian Hamippoi: madder wool tunic, knotted rope belt, petasos, baldric and xiphos, a small wicker shield with a tooled leather triskele boss, three javelins;
  - `L3_` Epilektoi Hamippoi: bronze pilos with a chin strap, linen corselet with red-trimmed shoulder flaps and a leather belt over a red chiton, baldric and xiphos, a small bronze shield with a thunderbolt, four javelins;
  - shields are strapped to the left forearm; when blocking, the forearm turns about its own axis so the shield faces forward (the `face` option of an arm in `hoplite.pose`);
  - animations: Idle, Walk, Run, Throw, Thrust, Block, Hit and Death, with `ThrowJavelin` released at frame 12 as for the Peltast.
- `tools/blender/horse.py` builds the horse that every cavalry tier rides, as a module for the unit builds:
  - a small Greek horse of about 13½ hands (1.37 m at the withers), traced from the side view of the reference sheet: the outline is inflated into round sections (a Poisson solve inside it), scaled to the widths measured on the sheet's front and back views, with the legs laid joint to joint at the sheet's joints and a voxel remesh fusing it all;
  - a dark brown coat with black points, a cropped upright mane, a full tail, unshod hooves;
  - tack: a draped sheepskin with a fur fringe, a braided girth and breast strap, and a leather bridle with bronze bit rings;
  - its bones (`h_*`) join the unit's armature; legs are posed from hoof targets and cannon and pastern angles, and the four-beat walk and the gallop are generated from each leg's phase in the stride.
- `tools/blender/hippeis.py` seats the rider on the horse and exports `assets/models/hippeis.glb`:
  - one armature for horse and rider: the rider's root hangs from the horse's saddle bone, so he rides every gait, gripping with his thighs and without stirrups;
  - `L1_` Prodromos: bronze Boeotian helmet, madder chiton with a cord belt, blue chlamys pinned at the right shoulder, open-toed endromides, two cornel-wood javelins (one to throw, one kept for close fighting);
  - the spear branch: `L2_` Hippeus, an Attic helmet with cheek pieces, a linothorax over a short chiton, an olive chlamys, high riding boots and a cornel-wood spear with a bronze butt-spike; `L3_` Hetairos, a Boeotian helmet with a white horsehair plume, a linothorax faced with bronze scales, a purple chlamys with a woven yellow border, high boots, the xyston with a blade at each end and a kopis on a baldric;
  - the javelin branch: `L4_` Hippakontistes, a felt petasos, a brown chiton and chlamys, soft boots and three javelins, two held upright with the reins; `L5_` Tarantine, a laurel wreath, a pale chiton, a blue chlamys, soft boots, a small round bronze shield on the left forearm and three javelins;
  - the horse and its tack are untagged and the rider is `L12345_`, so level 0 shows the horse alone. It then wears `L0_Reins` lying over its withers instead of the reins that run to the rider's left fist, which hang from their own bone: keyed to the fist in every clip, it lets go when he falls. The throwing javelin is `L145_`, so only the javelin tiers throw one;
  - animations: Idle, Walk, Gallop, Throw, Thrust, Rear, Hit and Death. Throw and Thrust are made at the gallop, with `ThrowJavelin` released at frame 12; in Death the horse stumbles, kneels and rolls onto its left side while the rider is thrown clear to the right.
- `tools/blender/minotaur.py` builds the Minotaur line and exports `assets/models/minotaur.glb`:
  - the MakeHuman man made massive (widened through the shoulders and deepened through the chest, his muscles deepened as for Talos), his head replaced by a bull's head and neck traced from the side view of the sheet, inflated as for the horse and sized to the front view's widths, its base laid onto the shoulders; built at the infantry's scale and exported at 2.3 m to the poll, with Asterion a little larger;
  - `L1_` Minotaur: dark brown hide, a linen loincloth with a woven zigzag flap, a wide leather belt, a bronze labrys about 1 m long; `L2_` Labrys Guard: a bronze belt, crossed leather harness, bronze armbands, a figure-of-eight oxhide shield on the back and a longer engraved labrys; `L3_` Asterion: near-black hide flecked like the stars, gilded horns, a Dendra-style bronze corselet with shoulder guards and girdle, greaves, a crimson kilt, gold armlets and a gilded double labrys. `L12_` nodes are the brown body, head and horns the first two share;
  - eyes, ears, a curly forelock between the horns, shaggy hair on the hump and a tufted tail;
  - the fists are bent into the mesh as for Talos, the right one round the haft;
  - animations: Idle, Walk, Cleave (an overhead chop), Gore (head down, a lunge on the horns and a toss), Hit and Death.
- `tools/blender/hydra.py` builds the Hydra line and exports `assets/models/hydra.glb`:
  - a heavy, low body on four splayed legs like a giant monitor lizard, with five-toed clawed feet, a long tail and two rows of osteoderms down the back, laid as ellipsoids and fused by a voxel remesh; about 6 m long, and the gallery scales the second and third tiers up;
  - the necks rise in a fan from the shoulders, each a tube lofted along an S-curve on its own chain of five bones; each serpent's head is lofted from sections, with a lower jaw on its own bone, teeth and slit-pupilled eyes;
  - `L1_` Marsh Hydra: five necks, olive and mud-brown scales; `L2_` Lernaean Hydra: seven necks, green-black scales with a bronze sheen and a ridge of spines; `L3_` Hydra Matriarch: nine necks, the middle one longer and thicker with a larger head, scarred black-green hide and pale gold eyes. The scales are Voronoi cells with dark seams, paler on the belly and throat (a colour attribute baked into the texture) in transverse plates;
  - animations: Idle, Walk (a trot with the body swinging), Strike (every head draws back and strikes, a frame or two apart, its jaws gaping), Hit and Death (the body sinks and the necks topple out flat).
- `tools/blender/talos.py` builds the Talos line on the same pipeline and exports `assets/models/talos.glb`:
  - the MakeHuman man made heavier and more muscled, his muscle forms deepened by unsharp masking the mesh (each vertex moved away from a volume-preserving smooth of it); built at 1.76 m and exported at the automaton's 2.6 m, and the gallery scales Talos (3 m) and the Colossus (4 m) up from that;
  - each tier has its own body in its own bronze, on one skeleton: `L1_` Bronze Automaton, dark with green patina in the recesses; `L2_` Talos, polished with a darker patina, a cast beard and a boulder in his right hand; `L3_` Colossus, gleaming, with a radiate crown and a cloak of hammered bronze hung from the trunk;
  - the joints are cut in as seams in the baked normal map, the eyes are inlaid stone, and the vein of ichor runs on the skin from the neck to a bronze nail at the right ankle;
  - the fists are bent into the mesh rather than posed: each finger turns at its three joints and the thumb tucks over the first two fingers, while Talos' right hand is cupped round the boulder;
  - animations: Idle, Walk, Smash (a hammer blow of the right fist, or the boulder), Hit and Death (he sinks to his knees and topples).
- `tools/blender/medjay.py` builds Kemet's Medjay line on the infantry pipeline and exports `assets/models/medjay.glb`:
  - the MakeHuman man at 1.75 m, lean and athletic (the shoulders broadened a little and the muscles deepened as for Talos), olive-brown, his hair cropped to a few millimetres with a single ostrich feather at the crown; both fists are bent into the mesh as for Talos, closed round the spear and the shield's grip;
  - `L1_` Medjay: a bead necklace and a stone amulet on a cord, a white linen kilt draped with the cloth simulator (its outer turn rounded up at the front, a tab hanging from the tooled leather belt and a knot at the back), a bronze dagger at the left hip, a 1.9 m spear with a bronze leaf blade, and a small oval cowhide shield laced round its rim with rawhide;
  - `L2_` Veteran Medjay: a tan leather corselet grown from the body with a plain yoke and edging, sewn with rows of small bronze plates with rounded lower ends (each modelled, lying over the top of the row below), a khopesh in a sheath cut to its crescent, and a round-topped dappled cowhide shield on a wooden frame, strapped round the forearm;
  - `L3_` Elite Medjay: a coat of about two thousand bronze scales to mid-thigh with short sleeves, its skirt open at the front over a beaded apron; a broad collar of turquoise, lapis and gold beads, gold armlets and ribbed wristlets, a pleated kilt, a 2 m spear with a broad blade, gilded socket and bronze butt-spike, and a tall cowhide shield with a gilded rim and a sun-disc boss. `L12_` nodes are the plain kilt, belt, necklace and spear the first two share;
  - the kilts and the coat's skirt hang from the hips and take the thighs' weights only towards the hem, so they stretch between the legs; the spear rides on its own bone, `spear.R`, so a clip slides it through the fist and lets it fall;
  - animations: Idle, Walk, Run, Thrust (an underhand thrust from the hip, the spear slid forward through the fist), Block (the shield brought round in front), Hit and Death (he falls backwards and the spear drops beside him).
- `tools/blender/chariot.py` (with `chariot_car.py`) builds Kemet's Chariot line and exports `assets/models/chariot.glb`:
  - a New Kingdom war chariot c. 1300 BC: a car of bent wood on a D-shaped floor of woven leather straps, open at the back, its siding a curved rail over a solid front and low wicker panels; two six-spoked wheels on an axle under the back of the floor; a pole curving up from under the car to a bowed yoke over the withers;
  - the team is horse.py's horse, twice, in a yoke harness instead of the Greek sheepskin: yoke saddles, a girth, breast straps, tall ostrich plumes, a light bay coat with white socks and a blaze;
  - the crew are MakeHuman men of 1.70 m with shaven heads and linen kilts, each branch with its own pair as on the sheets: the archer stands left of his driver, the spearman right of his;
  - one armature holds them all: the car's bone pivots on the axle so the pole stays on the yoke saddles, the wheels turn at the speed the hooves cover the ground, and each horse and man has his own copy of horse.py's or hoplite.py's bones;
  - the archer branch: `L1_` Chariot Archer, bare chests, a composite bow, the wooden car with a bow case and two quivers; `L2_` Veteran Chariot Archer, bronze scale corselets, red and blue striped saddle cloths and breast bands with tassels, gilded fittings; `L3_` Elite Chariot Archer, broad collars, the car sheathed in gold with reliefs of captives and the king's chariot, gilded harness and a large gilded bow;
  - the spear branch: `L4_` Chariot Spearman, padded linen corselets, cowhide shields, a 2.5 m spear, a bronze khopesh, red and blue trappings and a rack of spare spears; `L5_` Royal Chariot Guard, scale corselets and broad collars, gilded shields, a long bronze spear, a gilded khopesh, the gold car, and horses in coats of bronze scales with gold face plates. Shared parts are tagged with every level that has them (`L24_` the trappings, `L35_` the gold car); level 0 shows the car and team alone with `L0_Reins` tied to the front rail;
  - animations: Idle, Walk, Gallop, Shoot, Thrust, Hit and Death. In Shoot the archer draws to the jaw and looses at the gallop, the string following his hand, and the arrow, `ShootArrow`, leaves it at frame 15; in Death the team falls and rolls apart, the car tips forward onto the fallen horses and the crew are thrown out.
- `tools/blender/akhekh.py` builds Kemet's Akhekh Griffin line and exports `assets/models/akhekh.glb`:
  - Akhekh of the Beni Hasan tomb paintings: a pale sandy lion 3 m from chest to rump with a long tufted tail, the head of a lanner falcon twice a griffin's size (half as long as the body, as wide as the chest) on a thick cream neck, and falcon wings spanning about 9 m;
  - the lion is traced from the side view and inflated as the horse is, sized to widths measured on the front and back views, with legs laid joint to joint and paws, toes and muscle masses; the falcon head is lofted from traced sections and fused with the body by a voxel remesh, and the hooked beak and lower mandible are lofted along their curves. The markings (rufous crown and nape, dark moustache stripe, dark skin round the large eyes) are painted from the side view and baked with the fur and the feathering of the neck;
  - each wing is a chain of three bones carrying layered feather cards drawn in one barred atlas: ten primaries, twelve secondaries and three tertials each on its own bone, with the primary, greater, median and lesser coverts riding on them. Folding turns every bone to its place in the closed wing, which lies over the flank and back with the primaries past the root of the tail, and the beats and the opening of the wings are drawn from the same fold;
  - `L1_` Akhekh Griffin: bare; `L2_` Veteran Akhekh Griffin: a wide plain band of hammered gold round the base of the neck; `L3_` Elite Akhekh Griffin: a fitted cover of gilded bronze inlaid with rows of lapis lazuli over the shoulders, back and hips, a broad gold and lapis collar, the neck band, gold cuffs and gilded claws. The shared griffin is untagged, `L12_` are the bare claws and `L23_` the band;
  - animations: Idle (wings folded), Walk, Fly (hovering on beating wings, half-folding on the upstroke), Strike (it rears on opening wings, rakes down with the fore claws and stabs with the beak), Hit and Death (it sinks onto its belly, the head and wings coming to rest on the ground).
- `tools/blender/priest.py` builds Kemet's Priest of Thoth line on the infantry pipeline and exports `assets/models/priest.glb`:
  - the MakeHuman man at 1.72 m, a scholar's build, medium brown, his head and face shaven, his fists bent into the mesh as for Talos (the right round the staff, the left a little looser round a roll of papyrus); every tier wears a long robe of white pleated linen (the bodice and its wide sleeves grown from the body and wrapped over at the front with a V at the throat, the skirt to the lower calf made as a hundred knife pleats and draped with the cloth simulator), a woven sash knotted at the front and sandals of woven papyrus;
  - `L1_` Priest of Thoth: a scribe's palette with its ink wells and reed pens tucked into the sash, a closed scroll, and a walnut staff carved at the top into an ibis head, banded in turquoise and gold (`L12_`, shared with the second tier); `L2_` Veteran Priest of Thoth: the lector's broad woven bands crossed over the chest and back and an open roll written in columns of hieroglyphs; `L3_` Elite Priest of Thoth: the skin of a single leopard as a mantle (its head over the left shoulder, a foreleg down the chest, the hide hanging to the knees with the hind paws at its corners and the tail down the middle), a broad collar of gold and turquoise, and a staff topped by a gilded ibis in a crescent moon under the moon's disc;
  - magic light that grows with the tiers, one node per tier (`L1_Magic`, `L2_Magic`, `L3_Magic`), each a skinned mesh of unbaked emissive materials riding the staff and hands so it can be restyled or hidden by name: the ibis's eyes glowing, then the writing on the roll lit gold, then the moon disc in a halo and a soft light at both fists. The gallery lets nodes named Magic cast no shadow;
  - the staff rides its own bone, `staff.R`; animations: Idle, Walk, Cast (the staff raised, then pointed, the roll held out), Heal (both hands raised in blessing), Strike (the staff slid down through the fist and swung), Hit and Death (he falls backwards and the staff drops beside him).
- `tools/blender/anubite.py` builds Kemet's Anubite Warden line and exports `assets/models/anubite.glb`:
  - the MakeHuman man, lean and muscular with black skin as Anubis is painted in the tombs, his head replaced by a jackal's head and neck traced from the sheet's side view, inflated as for the Minotaur, narrowed along the muzzle and set under the collar; built at the infantry's scale and exported at 2.1 m to the top of the head;
  - tall cupped ears with a brown, haired lining, amber eyes with gold eye-lines painted from the side view, a black nose pad, and short fur strands that soften the outline of the head and neck;
  - every tier wears a pleated linen kilt (cloth-draped, following the thighs towards the hem), an embroidered apron, a sash and Egyptian sandals;
  - `L1_` Anubite Warden: a broad bead collar of turquoise, lapis and carnelian with drop pendants, and a bronze khopesh traced from the sheet; `L2_` Veteran: a corselet of feather-shaped scales (each a separate plate), gold armlets and wristguard, a cowhide shield strapped to the left forearm and a long engraved khopesh; `L3_` Elite, a dual wielder: a gilded round-scale corselet, a gold and lapis collar, gold armlets and wristguards and a gilded khopesh in each hand. `L12_Body` has the open left hand, `L3_Body` both hands closed; `L23_` are the armlets and right wristguard;
  - the fists are bent into the mesh as for Talos;
  - animations: Idle, Walk, Cleave (the right blade down from over the shoulder, then the left arm sweeps across: the elite's second blade, the veteran's shield, the warden's open hand), Block (the elite crosses both blades), Hit and Death.
- `tools/blender/bennu.py` builds Kemet's Bennu Firebird line and exports `assets/models/bennu.glb`:
  - the Bennu of Heliopolis as a giant heron about 2 m tall to the crown: the torso lofted from sections traced from the side view of the sheet and sized to its front view, the neck lofted along the sheet's S on a chain of six bones and fused into it by a voxel remesh, a dagger bill with its lower mandible on its own bone, and long legs ending in heron feet with three toes forward and one behind;
  - the wings are layered feather cards (ten primaries, fourteen secondaries and four tertials, each with greater, median and lesser coverts), stacked so each feather lies over the one beyond it; every pair of flight feathers rides its own bone, so a wing blends between spread (3.5 m), folded in the bird's Z against the flank, and raised as on the sheet's front view. The feathers are thin cambered meshes in one painted atlas per tier; the body, head and legs are baked from procedural materials;
  - `L1_` Bennu Firebird: grey, the flight feathers shading to fiery red and orange at their tips, a crest of two lanceolate feathers; `L2_` Veteran Bennu Firebird: slender and blue-grey, a white foreneck streaked black, a black stripe to the nape, two long thin plumes streaming back, dark flight feathers; `L3_` Elite Bennu Firebird: a grey-blue head and neck, the body glowing like coals through the seams of its feathers, ember wings, and `L3_Flames`, emissive cards at the tips of the flight feathers, the tail and the crest and at the bend of each wing. The legs, lower mandible and eyes are shared;
  - animations: Idle, Walk, Fly (hovering on beating wings, the neck drawn in and the legs trailing), Strike (the neck drawn back into its S and the bill driven forward), Cast (wings raised, the neck coiled and thrust forward with the bill open as it throws fire), Hit and Death (it sinks onto its folded legs and topples onto its side). The neck poses are solved so the bill tip reaches its mark; the legs are placed from foot targets.
- `tools/blender/scorpion.py` builds Kemet's Serket Scorpion line and exports `assets/models/scorpion.glb`:
  - a giant black fat-tailed scorpion (Androctonus), about 2.5 m from the chelicerae to the sting along the body and the arched tail, standing about 1.4 m to the top of the tail;
  - its exoskeleton is the animal's own rigid plates, lofted from sections traced from the side view of the sheet and sized to its front and back views: the carapace with its median and lateral eyes, seven overlapping tergites and five sternites on the folded pleural membrane, the pectines, five swollen keeled tail segments, the bulbous telson and its curved sting, the pedipalps with their chelae, and the legs segment by segment;
  - every plate rides rigidly on its own bone, with dark brown membranes bending at the joints; the chitin is glossy black and granular, baked to textures, and turns dark brown near the joints;
  - `L1_` Serket Scorpion: bare black chitin and a dark red-brown telson; `L2_` Veteran Serket Scorpion: larger, with a band of hammered gold round the second tail segment; `L3_` Elite Serket Scorpion: the largest, in fitted armour of gilded bronze inlaid with lapis lazuli (lotus fans on the carapace and abdomen, feathers on the tail segments and pincers, drawn as cloisonné into one atlas), gilded fingers, a gold-sheathed sting and the band of the second tier, the legs left bare. The shared body is untagged; `L12_` are the bare fingers and telson and `L23_` the band;
  - animations: Idle, Walk (the alternating tetrapod gait with the body level), Strike (the tail lashes forward over the head, its pose solved so the sting stabs just past the pincers), Pinch (both chelae lunge and snap shut), Hit and Death (it rolls onto its back and curls its legs). Legs are placed from foot targets and pedipalps from wrist targets, all keyed as plain rotations.
- `tools/blender/render_views.py` renders inspection views (any clip, frame, level and camera) from the `.blend` that each build saves next to its `.glb`.
- `tools/blender/glb2json.py` turns a `.glb` into a self-contained `.json` glTF for hosts that cannot serve binary files, quantizing skin weights and UVs to keep it small.

### Reference sheets

Each model is built from a turnaround sheet: one image per tier with the subject in front, side and back views on a plain background. `tools/refs/roster.py` holds the 100 sheets the remaining units need (the rest of the Greek roster and Kemet, now made, then the Norsemen, Yamato and the neutral creatures), each with its prompt; `tools/refs/generate.py` makes them with an image API, checks each one (plain background, nothing cut off, three separate views), retries failures and saves them under `refs/` with a manifest. Riders are sent the horse sheet in `refs/hippeis/`, and tiers 2 and 3 are sent tier 1's sheet, so a line keeps one look. The models edit an attached sheet rather than redraw it, so a tier that changes the anatomy (the hydras' heads) or would come back as a copy of tier 1 (two of the riders) sets `tier1=False` and describes the whole subject instead.

```
python3 tools/refs/generate.py --list            # every sheet and its state
python3 tools/refs/generate.py --dry-run hydra   # read the prompts without calling anything
python3 tools/refs/generate.py greek             # a faction, a line or sheet ids; "all" for everything
python3 tools/refs/generate.py --contact sheets.jpg
```

It uses Google's Gemini (`GEMINI_API_KEY`) by default, or xAI's Grok with `--provider xai` (`XAI_API_KEY`; text prompts only, and `api.x.ai` must be allowed by the network policy). `--models` lists the image models a provider offers and `--model` picks one. Gemini's image models need billing enabled on the key's project; the free tier allows none. The Greek sheets were made with `--model gemini-3-pro-image`, which follows the prompts far better than the default `gemini-2.5-flash-image` (the nine-headed hydra took `gemini-3.1-flash-image`, the only one that counted the heads). The Kemet sheets were made with `gemini-3.1-flash-image` while the Pro model was overloaded, and kept up well. When a line's first tier fails, its later tiers are skipped rather than made without it.

When no model holds a design across a whole sheet, the views can be made one at a time and put together with `tools/refs/compose.py`, which scales them to one size and ground line and evens out their backgrounds. The Akhekh Griffin's first tier was made that way (whole sheets kept shrinking its doubled head); its views are in `refs/akhekh/sources` and the command is in the script.

The game still draws units as emoji. The models are shown by two preview pages while the art direction is settled. Both load the `.glb` files from `assets/models`, so serve the repository over HTTP to open them (for example `python -m http.server`):

- `preview/unit.html` is a gallery for one unit line: the three tiers on plinths with their game stats and kit, buttons for every clip the model has, speed, pause, loop and turntable controls, a close-up per tier, and javelins and arrows that fly and stick in the ground on Throw and Shoot. Pick the line with the link (`/preview/unit.html#hoplite`, `#peltast`, `#hamippoi`, `#minotaur`, `#hippeis`, `#hydra`, `#talos`, `#medjay`, `#scorpion`, `#chariot`, `#priest`, `#anubite`, `#bennu` or `#akhekh`). The Hippeis page puts the horse alone on the first plinth and both branches after the Prodromos (a tier's `tag` is the level its nodes are tagged with); the Talos page stands each tier at its own height.
- `preview/pantheon-3d.html` covers the adventure map and battle looks, the unit roster, a scripted Greek-vs-Greek battle with switchable effect styles, and the Blender Hoplite and Peltast lines.

## Code layout

| File | Contents |
|---|---|
| `js/data.js` | All game data: creature lines and levels (`defLine`, `autoLine`), abilities, heroes, factions, buildings, terrain, artifacts, shrines. Add a faction or creature here. |
| `js/core.js` | Helpers, stacks (`makeStack`, `stackHp`, `addToArmy`), hero stats, Heroes III damage maths, army power ratings. |
| `js/battle.js` | The tactical battle: map generation, input state machine, combat animation, enemy AI, god powers. `startBattle(opt)` returns a Promise. |
| `js/campaign.js` | Adventure-map state `G`: map generation, pathfinding with guard zones, interactions, towns, the day/week cycle, AI players. |
| `js/mapview.js` | Adventure-map canvas rendering, fog of war, minimap and input. |
| `js/ui.js` | Modals, side panel, town screen, main menu, save/load (`localStorage`, with an autosave each day). |
| `preview/unit.html` | A three.js gallery for one Blender unit line: tiers, stats, kit and animations. |
| `preview/pantheon-3d.html` | The standalone three.js look-development page (map, battle, roster, battle sim, Blender model tabs). |
| `tools/blender/` | The Blender model builds and their helpers; output goes to `assets/models/`. |

### Adding a faction

1. Add 7 creature lines with `autoLine(id, faction, tier, name, icon, weapon, move, cls, opts)` (stats come from the tier templates in `TIER`) or hand-tune them with `defLine`. Add a hero to `HEROES`.
2. Add an entry to `FACTIONS` with colour, biome, town name and icon, dwelling names, temple, god power (`bolt`, `flare`, `hammer` or `dawn`, or add a new kind in `usePower`) and a blurb.
3. If it needs a new biome, add it to `TERRAIN` (adventure map) and `BTHEMES` (battles).

## Ideas for next steps

- Multiple heroes per player, a tavern, and hero skills or spellbooks (HoMM3).
- Pair Up / Dual Guard and support conversations (Awakening).
- 3D models for the remaining creature lines (see `preview/unit.html` and `preview/pantheon-3d.html`).
- More pantheons: Aztec, Celtic, Chinese, Hindu, Mesopotamian.
- Sprite art and sound in place of emoji, and a scripted campaign with story maps.
