"""Render inspection views of a saved model .blend (written next to the .glb by hoplite.py / peltast.py).

    VIEWS="[('front.png', 'Idle', 1, 2, ((0.4, -3.0, 1.0), (88, 0, 8)), [], (330, 520))]" \
        python tools/blender/render_views.py third_party/makehuman OUT_DIR OUT_DIR/peltast.blend

Each view is (file, action, frame, level, (camera location, camera rotation in degrees),
[substrings of object names to hide], (width, height)); files are written to OUT_DIR.
"""
import bpy, sys, os
blend = [a for a in sys.argv[1:] if a.endswith('.blend')][0]
sys.argv = [a for a in sys.argv if not a.endswith('.blend')]   # hoplite.py reads the two directory arguments
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
H.SC = bpy.context.scene
rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
for name, action, frame, level, cam, hide, res in eval(os.environ.get('VIEWS', '[]')):
    H.render(rig, os.path.join(H.OUT, name), action, frame, level, cam=cam, res=res, samples=20, hide=hide)
