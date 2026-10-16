"""Reference sheets still to make: one turnaround sheet per tier, and the prompt for each.

A sheet shows one subject in three views (front, side facing right, back) on a plain
background, which is all a Blender build needs: the side view gives the outline to trace
and the front and back views the widths. Animations are written in the builds, so no
action poses are asked for.

Each entry: id (line-tier; the Hippeis javelin branch is 2r and 3r), faction, the kind of
subject (it sets the views and pose), the subject itself, and optional reference images
under refs/ to attach (providers that take images use them; the others ignore them).
Tiers 2 and 3 of a line are also sent tier 1's sheet, so a line keeps one look, unless the
entry sets tier1=False: the image models edit an attached sheet rather than redraw it, so a
tier that changes the anatomy (more heads) or looks too like tier 1 comes back as a copy.
Such entries describe the whole subject instead of saying "the same build".
"""

STYLE = {
    'greek': ('ancient Greece, based on archaeological finds, Greek vase painting and sculpture; mythological '
              'creatures as Greek art shows them, made believably real'),
    'egypt': ('New Kingdom Egypt, c. 1550-1070 BC, based on tomb paintings, temple reliefs and finds such as '
              "the objects from Tutankhamun's tomb; sacred creatures as Egyptian art shows them, made believably real"),
    'norse': ('Viking Age Scandinavia, c. 800-1050 AD, based on finds such as the Gjermundbu helmet, the Birka '
              'graves and the Oseberg ship, and on picture stones; creatures from the Eddas and sagas, made believably real'),
    'japan': ('Sengoku-period Japan, c. 1550-1600, based on surviving armour, folding screens and scroll paintings; '
              'yokai as Edo-period scrolls and prints show them, made believably real'),
    'neutral': 'a grounded bestiary drawn from ancient and medieval European folklore, natural history made believably real',
}
AVOID = {
    'greek': 'Roman armour, transverse crests, studded leather, "300"-movie or fantasy armour, ornate gold filigree, horned helmets',
    'egypt': 'Hollywood costume, fantasy armour, gold-plated armour on common soldiers, Greek or Roman items, horned helmets',
    'norse': 'horned or winged helmets, studded leather, plate armour, fantasy armour, face paint',
    'japan': 'Chinese or Korean armour, fantasy armour, anime styling, ninja costume',
    'neutral': 'cartoon styling, glowing magic effects, extra ornament',
}
COMMON_AVOID = 'text, labels, numbers, borders, watermark, extra figures, props on the ground, motion blur, modern items'

VIEWS = {
    'figure': ('A character turnaround sheet: three full-body views of the same figure side by side, left to right: '
               'front view, side view facing right, back view. Neutral modelling pose: standing straight, arms held a '
               'little away from the body, legs slightly apart, weapons held clear of the body so every limb shows in outline.'),
    'winged': ('A character turnaround sheet: three full-body views of the same figure side by side, left to right: '
               'front view with the wings spread wide, side view facing right with the wings folded against the back, '
               'back view with the wings spread wide. Neutral modelling pose: standing straight, arms a little away '
               'from the body, legs slightly apart, weapons held clear of the body.'),
    'mounted': ('A turnaround sheet of horse and rider together: three full views side by side, left to right: front '
                'view, side view with the horse facing right, back view. The horse stands square with all four legs '
                'visible; the rider sits upright without stirrups, legs hanging long, reins in the left hand, weapons '
                'held upright and clear of the horse.'),
    'chariot': ('A turnaround sheet of the chariot, its team and crew together: three full views side by side, left to '
                'right: front view, side view facing right, back view. The horses stand square with all legs visible; '
                'the crew stand upright in the car, weapons held clear of the body.'),
    'beast': ('A creature turnaround sheet: three full views of the same creature side by side, left to right: side '
              'view facing right, front view, back view. Standing square on all its legs, every leg visible, tail and '
              'any necks held clear of the body.'),
    'flyer': ('A creature turnaround sheet: three full views of the same creature side by side, left to right: side '
              'view facing right with the wings folded, front view with the wings spread wide, back view with the '
              'wings spread wide. Standing on the ground, every leg visible, tail held clear of the body.'),
}
RULES = ('Photorealistic. Plain light grey seamless background, even soft studio lighting, sharp detail. Orthographic '
         'views with no perspective. All three views at the same scale, standing on one flat ground line, each '
         'whole subject in frame with clear space between and around them.')

HORSE = ['hippeis/horse.jpg', 'hippeis/hippeis-1.jpg']
HORSE_NOTE = ('The horse must match the first attached sheet exactly (build, colour, mane, tail, sheepskin, bridle). '
              'The second attached sheet shows the tier one rider on it: match only its rendering style and how the '
              'rider sits. The rider\'s helmet, clothing, armour and weapons are a different unit\'s: make them exactly '
              'as this prompt describes, not as on that sheet, and copy none of its text.')
# The horse alone, for riders the model would otherwise draw as the tier one rider.
HORSE_ALONE = HORSE[:1]
HORSE_ALONE_NOTE = 'The horse must match the attached sheet exactly (build, colour, mane, tail, sheepskin, bridle).'

ROSTER = [
    # ── Hellenes ──────────────────────────────────────────────────────────────
    dict(id='minotaur-1', faction='greek', kind='figure', name='Minotaur', subject=(
        'The Minotaur of Crete, about 2.3 m tall: the head and thick neck of a dark brown Cretan bull with long '
        'forward-curving horns, on a massively muscled man\'s body with short dark body hair, human legs and bare feet, '
        'and a short bull\'s tail. Minoan loincloth with a wide leather belt. A bronze double axe (labrys) about 1 m '
        'long in the right hand, head down beside the leg.')),
    dict(id='minotaur-2', faction='greek', kind='figure', name='Labrys Guard', subject=(
        'The same bull-headed creature as a guard of the palace of Knossos, c. 1450 BC: a padded linen kilt, a wide '
        'bronze belt, bronze armbands, a figure-of-eight oxhide shield on the back, and a long-hafted bronze labrys '
        'with an engraved head held upright in the right hand.')),
    dict(id='minotaur-3', faction='greek', kind='figure', name='Asterion', subject=(
        'Asterion, the Minotaur at his most terrible, larger than before: near-black hide with pale flecks like stars, '
        'gilded horn tips, a bronze plate corselet with shoulder guards like the Dendra panoply, bronze greaves, a '
        'crimson kilt, gold armlets, and a huge two-handed ceremonial labrys held upright.')),
    dict(id='hippeis-2', faction='greek', kind='mounted', name='Hippeus', ref=HORSE_ALONE, note=HORSE_ALONE_NOTE,
         tier1=False, subject=(
        'An Athenian citizen cavalryman (hippeus) c. 420 BC, as on the Parthenon frieze: bronze Attic helmet with '
        'hinged cheek pieces, a linothorax over a short chiton, a flowing chlamys, high soft riding boots; no shield; '
        'a cornel-wood cavalry spear about 2.5 m long with an iron head and a bronze butt-spike, held upright in the right hand.')),
    dict(id='hippeis-3', faction='greek', kind='mounted', name='Hetairos', ref=HORSE, note=HORSE_NOTE, subject=(
        'A Macedonian Companion cavalryman (hetairos) of Alexander c. 333 BC: bronze Boeotian helmet with a white '
        'plume, a linothorax reinforced with bronze scales, a purple chlamys with a yellow border, high leather boots; '
        'no shield; a xyston lance about 3.5 m long of cornel wood with an iron blade at each end, held upright in the '
        'right hand; a kopis sword on a baldric at the left hip.')),
    dict(id='hippeis-2r', faction='greek', kind='mounted', name='Hippakontistes', ref=HORSE_ALONE, note=HORSE_ALONE_NOTE,
         tier1=False, subject=(
        'A Greek mounted javelin thrower (hippakontistes) c. 400 BC: wide-brimmed felt petasos, short chiton, chlamys '
        'pinned at the right shoulder, soft boots; no armour, no shield; three javelins about 1.6 m long with leather '
        'throwing loops, one upright in the right hand and two held with the reins in the left.')),
    dict(id='hippeis-3r', faction='greek', kind='mounted', name='Tarantine', ref=HORSE, note=HORSE_NOTE, subject=(
        'A Tarantine light cavalryman c. 300 BC, as on the silver coins of Taras: bareheaded with a laurel wreath, '
        'short chiton, chlamys, soft boots; no body armour; a small round shield about 60 cm across on the left arm; '
        'three javelins with leather throwing loops, one upright in the right hand and two held behind the shield.')),
    dict(id='hydra-1', faction='greek', kind='beast', name='Marsh Hydra', subject=(
        'A marsh hydra about 6 m long: a heavy, low, scaly body on four short splayed legs like a giant monitor lizard, '
        'a long tapering tail, and five long snake necks rising from the shoulders, each with a serpent head; olive '
        'green and mud-brown scales. The necks spread apart so that every head shows in outline.')),
    dict(id='hydra-2', faction='greek', kind='beast', name='Lernaean Hydra', tier1=False, subject=(
        'The Hydra of Lerna, larger than a marsh hydra: a heavy, low, scaly body on four short splayed legs like a '
        'giant monitor lizard, a long tapering tail, and exactly seven long snake necks rising from the shoulders, '
        'each with a serpent head; dark green-black scales with a bronze sheen, a ridge of spines along the back. '
        'The necks spread apart so that all seven heads show in outline.')),
    dict(id='hydra-3', faction='greek', kind='beast', name='Hydra Matriarch', tier1=False, subject=(
        'The hydra matriarch, largest of all: a heavy, low, scaly body on four short splayed legs like a giant '
        'monitor lizard, a long tapering tail, and nine long snake necks rising from the shoulders, each with a '
        'serpent head: one central neck, longer and thicker with a larger head (the immortal head of the myth), and '
        'four necks on each side of it; scarred black-green hide, pale gold eyes. The necks fan out like the fingers '
        'of two hands either side of the central one, so that all nine heads show in outline.')),
    dict(id='talos-1', faction='greek', kind='figure', name='Bronze Automaton', subject=(
        'A bronze automaton forged by Hephaestus, about 2.6 m tall: an athletic cast-bronze body like the Riace '
        'bronzes, dark bronze with green patina in the recesses, joints shown as clean seams, inlaid stone eyes, a single '
        'bronze vein running from the neck down to the right ankle where a bronze nail closes it; fists clenched.')),
    dict(id='talos-2', faction='greek', kind='figure', name='Talos', subject=(
        'Talos, the bronze giant who guarded Crete, as on the Talos vase from Ruvo, about 3 m tall: polished bronze '
        'with darker patina, sculpted short curly hair and beard, the ichor vein to the nail at the right ankle, a '
        'boulder held in the right hand.')),
    dict(id='talos-3', faction='greek', kind='figure', name='Colossus', subject=(
        'A colossal bronze statue come to life, about 4 m tall, in the manner of the Colossus of Rhodes: gleaming '
        'polished bronze, a radiate crown of sun rays, a cloak of hammered bronze over the left shoulder and arm, the '
        'ichor vein to the nail at the right ankle, fists clenched.')),

    # ── Kemet ─────────────────────────────────────────────────────────────────
    # The Medjay were put together from chosen sheets kept in refs/medjay/sources: the first tier as he was
    # with a new shield, the second in the archer's armour with the spear and sword of one elite sample, the
    # third in the royal guard's armour with a new shield and spear.
    dict(id='medjay-1', faction='egypt', kind='figure', name='Medjay', ref=['medjay/sources/medjay-1-base.png'],
         note=('The attached sheet shows this same Medjay: keep the man exactly as he is there (face, build, skin, hair '
               'and feather, necklace, kilt, belt and dagger, sandals, the spear in his right hand) in the same pose '
               'and rendering. Replace his shield completely: remove the tall round-topped shield on the wooden frame '
               'and give him the new small oval shield this prompt describes, a different shape and size.'), subject=(
        'A Medjay desert scout and policeman, c. 1300 BC: a man of Arab appearance with medium olive-brown skin, short '
        'cropped dark hair with an ostrich feather, a white linen kilt with a leather belt, sandals, no shirt and no '
        'armour; a spear about 2 m long with a bronze leaf blade in the right hand, and in the left hand a small oval '
        'shield only about 60 cm tall and 40 cm wide, an egg-shaped oval with no corners, of black-and-white cowhide '
        'laced round its rim with a rawhide thong, held by a grip at its centre.')),
    dict(id='medjay-2', faction='egypt', kind='figure', name='Veteran Medjay',
         ref=['medjay/sources/elite-desert-archer.png', 'medjay/sources/elite-same-prompt.png'],
         note=('Attached sheets, in order: the first shows an elite Medjay archer: copy his armour exactly, the tan '
               'leather corselet with its plain leather yoke and edging and its straight rows of small flat bronze '
               'plates, and take none of his bow, quiver, feathers, armlets or apron. The second '
               'shows an elite Medjay: take only how he holds his spear upright in his right hand and the khopesh in '
               'its sheath at his hip, and none of his feathers, collar, armlets, armour or shield.'), subject=(
        'A veteran Medjay: the same man as the first tier, his single ostrich feather, white kilt, belt and sandals, '
        'wearing a sleeveless corselet of tan leather with a plain leather yoke over the shoulders and a leather band '
        'round its lower edge, sewn between them with straight horizontal rows of small flat rectangular bronze plates '
        'with slightly rounded lower ends (not round fish scales); the spear upright in his right hand, a bronze khopesh in '
        'its sheath at his left hip, and in his left hand a new shield, not the small oval shield of the first tier: '
        'a cowhide shield about 90 cm tall and 50 cm wide with a rounded top and a straight bottom edge, dappled '
        'brown and white hide on a wooden frame with a leather edging, held by its grip. Bare arms with no armlets; '
        'no bow and no quiver.')),
    dict(id='medjay-3', faction='egypt', kind='figure', name='Elite Medjay', ref=['medjay/sources/elite-royal-guard.png'],
         note=('The first attached sheet shows a Medjay of the royal guard: take only his armour and dress as this '
               'prompt lists them, not his shield, his spear or his khopesh.'), subject=(
        'An elite Medjay of the royal guard: the same man as the first tier, his single ostrich feather, wearing a '
        'long coat of bronze scales to mid-thigh with short sleeves, a broad bead collar, gold armlets and wristlets, '
        'and a pleated kilt with a triangular apron below the coat; in his right hand a new spear about 2.2 m long with '
        'a broad leaf-shaped bronze blade, a gilded socket and a bronze butt-spike, and on his left arm a new shield: '
        'a tall cowhide shield about 1.1 m with a rounded top, dappled black and white hide edged with a gilded bronze '
        'rim, and a gilded bronze boss in the shape of a sun disc. No sword in the hands.')),
    # The scorpion's tiers were chosen from samples (the black fat-tailed direction): the first describes the whole
    # creature; the second and third are the chosen sheets kept in refs/scorpion/sources with their carnelian beads
    # taken off.
    dict(id='scorpion-1', faction='egypt', kind='beast', name='Serket Scorpion', subject=(
        'A giant black fat-tailed scorpion of the Egyptian desert, sacred to Serket, about 2.5 m long with the tail: '
        'glossy black chitin like Androctonus, a thick heavy tail of swollen segments arched over the back with the '
        'sting, smaller pincers held forward.')),
    dict(id='scorpion-2', faction='egypt', kind='beast', name='Veteran Serket Scorpion', tier1=False,
         ref=['scorpion/sources/tier2-with-carnelian.png'],
         note=('The attached sheet shows this scorpion: keep it exactly as it is there (body, pose, glossy black chitin, '
               'the thick tail and the hammered gold band round it) in the same views and rendering, and take off the '
               'strings of red carnelian beads entirely, leaving its back and tail bare black chitin.'), subject=(
        'A larger black fat-tailed temple scorpion of Serket: glossy black chitin, a thick heavy arched tail with a '
        'band of hammered gold round one tail segment; no beads.')),
    dict(id='scorpion-3', faction='egypt', kind='beast', name='Elite Serket Scorpion', tier1=False,
         ref=['scorpion/sources/tier3-armour-with-carnelian.png'],
         note=('The attached sheet shows this scorpion: keep it exactly as it is there (body, pose, its armour and the '
               'hammered gold band on its tail) in the same views and rendering, and take off the strings of red '
               'carnelian beads entirely, showing the armour plates beneath them.'), subject=(
        'The largest war scorpion of Serket: the black fat-tailed scorpion in fitted armour of gilded bronze plates '
        'inlaid with lapis lazuli on the carapace, every tail segment and the pincers, a gold-sheathed sting, and the '
        'hammered gold band of the second tier on its tail; no beads.')),
    dict(id='chariot-1', faction='egypt', kind='chariot', name='Chariot Archer', subject=(
        'A New Kingdom war chariot c. 1300 BC, as in the reliefs of Ramesses II and the chariots of Tutankhamun: a '
        'light wooden car with a floor of woven leather straps and six-spoked wheels set at the back of the car, drawn '
        'by two small horses with tall plumes; a crew of two in linen kilts: a driver holding the reins and a shield, '
        'and an archer holding a composite bow at his side, with a bow case and quiver on the side of the car.')),
    dict(id='chariot-2', faction='egypt', kind='chariot', name='Veteran Chariot Archer', subject=(
        'The same chariot with a veteran crew in bronze scale corselets, the horses in red and blue painted trappings '
        'with tall ostrich plumes, and gilded fittings on the car.')),
    dict(id='chariot-3', faction='egypt', kind='chariot', name='Elite Chariot Archer', subject=(
        'A chariot of the royal guard: the car sheathed in gold with relief decoration like Tutankhamun\'s state '
        'chariot, the horses in gilded harness with tall plumes, the crew in bronze scale corselets with broad collars.')),
    dict(id='priest-1', faction='egypt', kind='figure', name='Priest of Thoth', subject=(
        'A priest of Thoth: shaven head, a long white pleated linen robe, sandals, a scribal palette at the belt, a '
        'papyrus scroll in the left hand and a wooden staff topped with a carved ibis head in the right.')),
    dict(id='priest-2', faction='egypt', kind='figure', name='Veteran Priest of Thoth', subject=(
        'A lector priest of Thoth: shaven head, the broad sash of the lector priest across the chest over the white '
        'robe, an open papyrus roll in the left hand and the ibis staff in the right.')),
    dict(id='priest-3', faction='egypt', kind='figure', name='Elite Priest of Thoth', subject=(
        'The high priest of Thoth at Hermopolis: shaven head, a mantle of a single leopard skin, its one head lying over '
        'the left shoulder and the hide hanging down the back to the tail (no second head), a gold broad collar, the '
        'white robe, and a staff topped with a gilded ibis and a moon disc.')),
    dict(id='anubite-1', faction='egypt', kind='figure', name='Anubite Warden', subject=(
        'A jackal-headed guardian of the underworld, about 2.1 m tall: a lean muscular man\'s body with black skin as '
        'Anubis is painted in tombs, the head of a black jackal with tall pointed ears, a white pleated kilt, a broad '
        'bead collar, and a single bronze khopesh in the right hand; the left hand empty and open.')),
    dict(id='anubite-2', faction='egypt', kind='figure', name='Veteran Anubite Warden', subject=(
        'The same jackal-headed guardian in a corselet of overlapping feather-shaped scales, gold armlets, a cowhide '
        'shield on the left arm and a single long bronze khopesh in the right hand; nothing else in the hands.')),
    dict(id='anubite-3', faction='egypt', kind='figure', name='Elite Anubite Warden', subject=(
        'The jackal-headed guardian at its grandest: a gilded scale corselet, a broad collar of gold and lapis lazuli, '
        'a single khopesh with a gilded blade in the right hand and a was-sceptre in the left; nothing else in the hands.')),
    # The Bennu's tiers were chosen from separate samples, so each describes the whole bird: the heron with
    # fire-coloured wing tips, the heron of the tomb paintings, and the firebird with burning feathers.
    dict(id='bennu-1', faction='egypt', kind='flyer', name='Bennu Firebird', subject=(
        'The Bennu bird of Heliopolis, a giant heron about 2 m tall as tomb paintings show it: long legs and neck, a '
        'two-feathered crest, grey plumage that shades to fiery red and orange at the wing tips (colour only, no flames).')),
    dict(id='bennu-2', faction='egypt', kind='flyer', name='Veteran Bennu Firebird', tier1=False, subject=(
        'The Bennu bird of Heliopolis as the vignettes of the Book of the Dead paint it, made real: a giant grey '
        'heron about 2 m tall, slender, with blue-grey plumage, a long neck held in an S, long legs, and a crest of two long '
        'thin plumes streaming back from the head; dark flight feathers, no other colours.')),
    dict(id='bennu-3', faction='egypt', kind='flyer', name='Elite Bennu Firebird', tier1=False, subject=(
        'The Bennu firebird of Heliopolis: a giant heron about 2 m tall with long legs and neck and a two-feathered '
        'crest, grey on the head and neck, its body and wings glowing ember-red and orange like coals, with small flames '
        'licking from the tips of the wing and tail feathers.')),
    # Akhekh, the falcon-headed griffin of the Beni Hasan tomb paintings, takes the Sphinx's place. Its first tier
    # was put together from views generated one at a time (whole sheets kept shrinking the doubled head and lost
    # views); the views are kept in refs/akhekh/sources. The later tiers are edits of it.
    dict(id='akhekh-1', faction='egypt', kind='flyer', name='Akhekh Griffin', subject=(
        'Akhekh, the griffin of the Egyptian desert, made real: a pale sandy lion\'s body about 3 m long with a long '
        'tufted tail, and the head of a lanner falcon, cream with a rufous crown and a dark moustache stripe below the '
        'eye. The falcon head is huge, twice the size it would be on a normal griffin: about half as long as the lion\'s '
        'body from chest to rump and as wide as its chest, with a heavy hooked beak, large fierce dark eyes and a thick '
        'cream feathered neck. Enormous falcon wings in pale sandy brown barred with darker brown, spanning about 9 m, '
        'three times the length of the body; folded, the closed wing covers the flank and back and its long primary '
        'feathers reach past the base of the tail nearly to the ground.')),
    dict(id='akhekh-2', faction='egypt', kind='flyer', name='Veteran Akhekh Griffin', subject=(
        'The same Akhekh griffin with the same huge falcon head and enormous wings, wearing a wide plain band of hammered '
        'gold around the base of its neck. Nothing else is added.')),
    dict(id='akhekh-3', faction='egypt', kind='flyer', name='Elite Akhekh Griffin', subject=(
        'The same Akhekh griffin with the same huge falcon head and enormous wings, armoured for war: a fitted cover of '
        'gilded bronze plates inlaid with lapis lazuli over its shoulders, back and hips (the wings stay bare feathers), '
        'a broad collar of gold and lapis lazuli across the chest, a wide plain band of hammered gold around the base of '
        'the neck, and gold-sheathed claws.')),

    # ── Norsemen ──────────────────────────────────────────────────────────────
    dict(id='huskarl-1', faction='norse', kind='figure', name='Huskarl', subject=(
        'A huskarl, a sworn warrior of a jarl\'s household, c. 1000 AD: a rounded iron helmet with a spectacle guard '
        'like the Gjermundbu helmet, a mail shirt to mid-thigh over a wool tunic, trousers with leg wraps, leather '
        'shoes; a long-hafted Dane axe held upright and a round linden shield slung on the back.')),
    dict(id='huskarl-2', faction='norse', kind='figure', name='Veteran Huskarl', subject=(
        'A veteran huskarl: mail with elbow-length sleeves over a padded tunic, a fur-trimmed cloak pinned at the right '
        'shoulder with a ring-headed pin, a sword on a baldric, a painted round shield, and the Dane axe.')),
    dict(id='huskarl-3', faction='norse', kind='figure', name='Elite Huskarl', subject=(
        'A jarl\'s champion: a helmet with spectacle guard and mail curtain, a long mail shirt, a bear-fur cloak, silver '
        'arm rings, and a Dane axe with a silver-inlaid head like the Mammen axe.')),
    dict(id='shieldm-1', faction='norse', kind='figure', name='Shieldmaiden', subject=(
        'A shieldmaiden, a woman warrior c. 900 AD like the warrior of Birka grave Bj 581: hair in a long braid, a '
        'knee-length wool tunic over trousers, leg wraps, a leather belt with a knife, a round painted linden shield '
        'with an iron boss and a sword.')),
    dict(id='shieldm-2', faction='norse', kind='figure', name='Veteran Shieldmaiden', subject=(
        'A veteran shieldmaiden: a padded tunic, a rounded iron helmet, a seax at the belt, the shield and sword.')),
    dict(id='shieldm-3', faction='norse', kind='figure', name='Elite Shieldmaiden', subject=(
        'An elite shieldmaiden: a mail shirt, a red wool cloak with a penannular brooch, silver arm rings, a pattern-welded '
        'sword and a painted shield.')),
    dict(id='volva-1', faction='norse', kind='figure', name='Völva', subject=(
        'A völva, a Norse seeress as Eiríks saga describes her: a long dark blue cloak set with stones along the hem, a '
        'black lambskin hood lined with white catskin, a necklace of glass beads, catskin gloves, a leather pouch of '
        'charms, and a long iron staff with a brass-knobbed top.')),
    dict(id='volva-2', faction='norse', kind='figure', name='Veteran Völva', subject=(
        'An older völva: a fuller fur-trimmed blue cloak, many amulets and small Thor\'s hammers on cords, the iron staff wrapped in cloth.')),
    dict(id='volva-3', faction='norse', kind='figure', name='Elite Völva', subject=(
        'A great völva: a white catskin hood, a necklace of amber and glass beads to the waist, and an iron staff topped '
        'with a bronze house-shaped finial like the Fyrkat staff.')),
    dict(id='ulfhedinn-1', faction='norse', kind='figure', name='Úlfheðinn', subject=(
        'An úlfheðinn, a wolf-warrior of Odin: a whole grey wolf pelt worn over the head and shoulders with the wolf\'s '
        'head as a hood, as on the Torslunda helmet plate; bare arms, wool trousers with leg wraps, a sword and a round shield.')),
    dict(id='ulfhedinn-2', faction='norse', kind='figure', name='Veteran Úlfheðinn', subject=(
        'A veteran wolf-warrior: a larger grey wolf pelt reaching the knees, iron arm rings, a sword and a seax.')),
    dict(id='ulfhedinn-3', faction='norse', kind='figure', name='Elite Úlfheðinn', subject=(
        'A leader of the wolf-warriors: a black wolf pelt with the head as a hood, silver arm rings, a sword in each hand.')),
    dict(id='valkyrie-1', faction='norse', kind='winged', name='Valkyrie', subject=(
        'A valkyrie, a chooser of the slain, as on Viking Age valkyrie pendants: a woman with her hair in a long knotted '
        'ponytail, a long trailing dress and cloak, large white swan wings, a spear and a round shield.')),
    dict(id='valkyrie-2', faction='norse', kind='winged', name='Veteran Valkyrie', subject=(
        'A valkyrie in a mail shirt over the dress and a rounded iron helmet, with the swan wings, spear and shield.')),
    dict(id='valkyrie-3', faction='norse', kind='winged', name='Elite Valkyrie', subject=(
        'A valkyrie in gilded mail with a rounded helmet with a gilded brow band, great white swan wings, a spear and a '
        'painted shield.')),
    dict(id='troll-1', faction='norse', kind='figure', name='Mountain Troll', subject=(
        'A mountain troll of Norse folklore, about 3 m tall: hunched, grey stone-like skin patched with lichen, a huge '
        'nose, long arms, a crude fur loincloth, and a heavy stone axe.')),
    dict(id='troll-2', faction='norse', kind='figure', name='Veteran Mountain Troll', subject=(
        'An older troll, larger and mossier, with a huge iron axe taken from men and a belt of trophies.')),
    dict(id='troll-3', faction='norse', kind='figure', name='Elite Mountain Troll', subject=(
        'A troll king: boulder-like shoulders, a beard of moss, a crude crown of iron, a bear-skin cloak and a great iron axe.')),
    dict(id='jotunn-1', faction='norse', kind='figure', name='Frost Jötunn', subject=(
        'A frost giant of Jötunheimr, about 5 m tall: pale blue-grey skin rimed with frost, long white hair and a braided '
        'beard, hides and furs, iron arm rings, and a huge two-handed iron axe.')),
    dict(id='jotunn-2', faction='norse', kind='figure', name='Veteran Frost Jötunn', subject=(
        'A veteran frost giant in a mail shirt of huge rings and a bear-skin cloak, ice in the beard, the great axe.')),
    dict(id='jotunn-3', faction='norse', kind='figure', name='Elite Frost Jötunn', subject=(
        'A king of the frost giants like Thrymr: an iron crown, a long fur cloak, gold arm rings, an ice-crusted beard and a great axe.')),

    # ── Yamato ────────────────────────────────────────────────────────────────
    dict(id='ashigaru-1', faction='japan', kind='figure', name='Ashigaru', subject=(
        'An ashigaru foot soldier c. 1570: a conical iron jingasa helmet lacquered black with a clan crest, a plain '
        'okegawa-do cuirass of lacquered iron plates, cotton hakama gathered at the shins, kyahan leggings, straw sandals; '
        'a yari spear about 3 m long held upright and a sashimono banner on the back.')),
    dict(id='ashigaru-2', faction='japan', kind='figure', name='Veteran Ashigaru', subject=(
        'A veteran ashigaru: armoured kote sleeves and suneate shin guards added, a wakizashi in the sash, the yari and sashimono.')),
    dict(id='ashigaru-3', faction='japan', kind='figure', name='Elite Ashigaru', subject=(
        'An ashigaru squad leader: a full okegawa-do with shoulder guards, a jingasa with a gold crest, a katana and '
        'wakizashi in the sash, the yari and sashimono.')),
    dict(id='yumi-1', faction='japan', kind='figure', name='Yumi Archer', subject=(
        'An archer c. 1570: a jingasa helmet, a simple lacquered cuirass, hakama, kyahan leggings, straw sandals; an '
        'asymmetric yumi longbow about 2.2 m long in the left hand with the grip below the middle, and an ebira quiver '
        'of arrows at the right hip.')),
    dict(id='yumi-2', faction='japan', kind='figure', name='Veteran Yumi Archer', subject=(
        'A veteran archer: kote sleeves, a lacquered box quiver, a wakizashi in the sash, the yumi.')),
    dict(id='yumi-3', faction='japan', kind='figure', name='Elite Yumi Archer', subject=(
        'A samurai archer in laced do-maru armour with a kabuto helmet, the yumi and a full quiver of arrows.')),
    dict(id='samurai-1', faction='japan', kind='figure', name='Samurai', subject=(
        'A samurai c. 1580 in tosei-gusoku armour of lacquered iron plates laced in dark blue silk: a kabuto with a neck '
        'guard and a simple crest, a menpo face mask, sode shoulder guards, kote, haidate and suneate; a katana held in '
        'the right hand pointing down, the wakizashi in the sash.')),
    dict(id='samurai-2', faction='japan', kind='figure', name='Veteran Samurai', subject=(
        'A veteran samurai: a kabuto with gilded kuwagata crests and a jinbaori surcoat with a clan crest over the armour, the katana.')),
    dict(id='samurai-3', faction='japan', kind='figure', name='Elite Samurai', subject=(
        'A great lord\'s retainer in red-lacquered armour with gold fittings, a tall crest on the kabuto, a jinbaori with '
        'a crest, and a katana.')),
    dict(id='miko-1', faction='japan', kind='figure', name='Miko', subject=(
        'A miko, a Shinto shrine maiden: a white kosode, red hakama, long black hair tied back with white paper, and a '
        'gohei wand with zigzag paper streamers.')),
    dict(id='miko-2', faction='japan', kind='figure', name='Veteran Miko', subject=(
        'A senior miko: a white chihaya over-robe patterned in green, and kagura suzu bells in the right hand.')),
    dict(id='miko-3', faction='japan', kind='figure', name='Elite Miko', subject=(
        'A high priestess of the shrine: a golden floral hana-kanzashi crown, the chihaya, a gohei and a sakaki branch.')),
    dict(id='kitsune-1', faction='japan', kind='beast', name='Kitsune', subject=(
        'A kitsune fox spirit as Edo-period prints show it: a red fox as large as a pony, with three full tails held '
        'clear of the body.')),
    dict(id='kitsune-2', faction='japan', kind='beast', name='Veteran Kitsune', subject=(
        'An older kitsune, red-gold fur paling at the muzzle, with six full tails fanned out.')),
    dict(id='kitsune-3', faction='japan', kind='beast', name='Elite Kitsune', subject=(
        'A celestial kitsune: white-gold fur and nine full tails fanned out.')),
    dict(id='tengu-1', faction='japan', kind='winged', name='Tengu', subject=(
        'A karasu-tengu, a crow tengu: a man-sized figure with a crow\'s head and beak and black-feathered wings, dressed '
        'as a yamabushi mountain ascetic: a small black tokin cap, a checked robe with pom-pom bands, hakama, high '
        'one-toothed geta; a katana.')),
    dict(id='tengu-2', faction='japan', kind='winged', name='Veteran Tengu', subject=(
        'A larger crow tengu with broader wings, a feather fan in the left hand and the katana.')),
    dict(id='tengu-3', faction='japan', kind='winged', name='Elite Tengu', subject=(
        'A great tengu (daitengu): a red face with a long nose, white hair and beard, great dark wings, yamabushi robes, '
        'a feather fan and a sword.')),
    dict(id='oni-1', faction='japan', kind='figure', name='Oni', subject=(
        'An oni as Edo-period scrolls show it, about 3 m tall: red skin, two horns, wild hair, a tusked mouth, a '
        'tiger-skin loincloth, and an iron kanabo club studded with iron knobs.')),
    dict(id='oni-2', faction='japan', kind='figure', name='Veteran Oni', subject=(
        'A blue-skinned oni with iron armlets and a larger kanabo.')),
    dict(id='oni-3', faction='japan', kind='figure', name='Elite Oni', subject=(
        'An oni lord like Shuten-doji: dark red skin, a white mane, a tiger-skin cloak over black lacquered armour '
        'plates, and a huge kanabo.')),

    # ── Neutral creatures ─────────────────────────────────────────────────────
    dict(id='wolf-1', faction='neutral', kind='beast', name='Dire Wolf', subject=(
        'A dire wolf, the extinct Ice Age wolf: heavier than a grey wolf, about 90 cm at the shoulder, thick tawny-grey '
        'fur, a broad head, tail held down and clear of the legs.')),
    dict(id='wolf-2', faction='neutral', kind='beast', name='Grey Wolf', subject=(
        'A larger wolf in dark grey winter fur with a pale mask, battle-scarred.')),
    dict(id='wolf-3', faction='neutral', kind='beast', name='Alpha Wolf', subject=(
        'The pack leader: a huge black wolf with a silver-grey muzzle, scarred ears and a heavy ruff.')),
    dict(id='skeleton-1', faction='neutral', kind='figure', name='Skeleton', subject=(
        'The animated skeleton of a dead warrior: bones stained with earth, scraps of rotted leather straps, a rusted '
        'iron sword and a battered round shield.')),
    dict(id='skeleton-2', faction='neutral', kind='figure', name='Skeleton Warrior', subject=(
        'A skeleton warrior in a dented iron helmet and the remains of a rusty mail shirt, with sword and shield.')),
    dict(id='skeleton-3', faction='neutral', kind='figure', name='Skeleton Champion', subject=(
        'A skeleton champion in corroded bronze scale armour, a crested bronze helmet and a tattered red cloak, with a '
        'heavy two-handed sword.')),
    dict(id='harpy-1', faction='neutral', kind='flyer', name='Harpy', subject=(
        'A harpy as archaic Greek vase paintings show her: the body, wings and talons of a large dark brown bird of prey, '
        'with the head and shoulders of a gaunt woman with wild dark hair.')),
    dict(id='harpy-2', faction='neutral', kind='flyer', name='Harpy Hag', subject=(
        'An older, larger harpy with grey feathers and long talons.')),
    dict(id='harpy-3', faction='neutral', kind='flyer', name='Harpy Queen', subject=(
        'The harpy queen: larger still, black and bronze plumage, a band of bronze leaves in her hair.')),
    dict(id='draugr-1', faction='neutral', kind='figure', name='Draugr', subject=(
        'A draugr, an undead barrow-dweller of the sagas: swollen black-blue skin, long matted hair, rotted Viking Age '
        'clothes, and an old iron axe.')),
    dict(id='draugr-2', faction='neutral', kind='figure', name='Barrow Draugr', subject=(
        'A barrow draugr in a rusted mail shirt and a helmet with a spectacle guard, with grave goods on its belt.')),
    dict(id='draugr-3', faction='neutral', kind='figure', name='Draugr Lord', subject=(
        'A draugr lord, a dead chieftain: huge, black-blue skin, gold arm rings, a rotting fur cloak and a broad axe with silver inlay.')),
    dict(id='spider-1', faction='neutral', kind='beast', name='Giant Spider', subject=(
        'A giant spider about 2 m across the legs: a hairy dark brown body like a huntsman spider, all eight legs spread.')),
    dict(id='spider-2', faction='neutral', kind='beast', name='Venom Spider', subject=(
        'A glossy black venom spider with red markings like a widow spider, all eight legs spread.')),
    dict(id='spider-3', faction='neutral', kind='beast', name='Spider Queen', subject=(
        'The spider queen: huge, banded black and amber, a swollen abdomen, all eight legs spread.')),
    dict(id='basilisk-1', faction='neutral', kind='beast', name='Basilisk', subject=(
        'A basilisk made real: a massive lizard about 4 m long with a serpent\'s head and a crest of crown-shaped spines '
        '(the "little king" of Pliny), olive-green scales and yellow eyes.')),
    dict(id='basilisk-2', faction='neutral', kind='beast', name='Greater Basilisk', subject=(
        'A greater basilisk: larger, darker scales and a taller crown of spines.')),
    dict(id='basilisk-3', faction='neutral', kind='beast', name='Basilisk King', subject=(
        'The basilisk king: deep black-green scales and a gold-tinged crown of spines.')),
    dict(id='griffin-1', faction='neutral', kind='flyer', name='Griffin', subject=(
        'A griffin as Greek and Scythian art shows it: the body of a lion with the head, wings and foreclaws of an eagle, '
        'a tawny lion body and golden-brown eagle feathers, standing on all fours.')),
    dict(id='griffin-2', faction='neutral', kind='flyer', name='Royal Griffin', subject=(
        'A royal griffin: larger, a white-feathered head like a sea eagle and a golden body.')),
    dict(id='griffin-3', faction='neutral', kind='flyer', name='Griffin Lord', subject=(
        'A griffin lord with the long upright crest and spiral forelock of Greek griffins, dark gold plumage.')),
    dict(id='wyrm-1', faction='neutral', kind='flyer', name='Young Wyrm', subject=(
        'A young dragon of medieval European tradition made real: a long serpentine body on four legs, leathery bat-like '
        'wings, a long tail, a horned head; green-bronze scales.')),
    dict(id='wyrm-2', faction='neutral', kind='flyer', name='Ancient Wyrm', subject=(
        'An ancient dragon: much larger, scarred dark bronze scales, heavier horns.')),
    dict(id='wyrm-3', faction='neutral', kind='flyer', name='Elder Wyrm', subject=(
        'The elder dragon: vast, near-black scales edged with gold, tattered wings, a crown of horns.')),
]


def line(entry): return entry['id'].split('-')[0]


def prompt(entry, refs=(), same_line=None):
    """The full prompt for an entry. refs: the reference images being attached, in order;
    same_line: the id of the earlier tier sent with it, if any."""
    f = entry['faction']
    parts = [VIEWS[entry['kind']], RULES,
             f'Realistic and historically accurate for {STYLE[f]}.',
             f'The subject: {entry["subject"]}',
             f'Do not include: {AVOID[f]}, {COMMON_AVOID}.']
    if refs and entry.get('note'): parts.append(entry['note'])
    if same_line:
        parts.append(f'The last attached sheet is the first tier of this line ({same_line}): keep the same build, '
                     'proportions, skin and rendering style, and change only what this prompt describes. Where this '
                     'prompt differs from that sheet (number of heads or limbs, size, colours, clothing, armour, '
                     'weapons), follow this prompt.')
    return '\n\n'.join(parts)
