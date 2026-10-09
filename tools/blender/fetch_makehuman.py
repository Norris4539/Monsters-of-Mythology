"""Download the MakeHuman base mesh and the shape targets the Hoplite build uses.

MakeHuman's base mesh and targets are released under CC0 1.0 (public domain).
    python tools/blender/fetch_makehuman.py third_party/makehuman
"""
import os, sys, urllib.request

BASE = 'https://raw.githubusercontent.com/makehumancommunity/makehuman/master/makehuman/data/'
FILES = ['3dobjs/base.obj'] + ['targets/macrodetails/' + f for f in (
    'caucasian-male-young.target', 'african-male-young.target', 'asian-male-young.target',
    'universal-male-young-maxmuscle-averageweight.target', 'universal-male-young-averagemuscle-minweight.target')]

out = sys.argv[1] if len(sys.argv) > 1 else 'third_party/makehuman'
os.makedirs(out, exist_ok=True)
for f in FILES:
    dst = os.path.join(out, os.path.basename(f))
    if not os.path.exists(dst):
        print('fetching', f); urllib.request.urlretrieve(BASE + f, dst)
print('MakeHuman files in', out)
