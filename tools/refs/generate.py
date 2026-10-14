"""Generate the reference sheets in roster.py with an image API, check them, keep the good ones.

    python3 tools/refs/generate.py --list                 # every sheet and its state
    python3 tools/refs/generate.py --dry-run minotaur-1   # print a prompt, call nothing
    python3 tools/refs/generate.py greek                  # a faction, a line (hydra) or ids (hippeis-2r)
    python3 tools/refs/generate.py all --provider xai     # everything, with Grok instead of Gemini
    python3 tools/refs/generate.py --contact sheets.jpg   # thumbnails of every sheet made so far

Providers and the environment variables they read:
    gemini  GEMINI_API_KEY  (GEMINI_IMAGE_MODEL picks the model; attaches reference images)
    xai     XAI_API_KEY     (XAI_IMAGE_MODEL picks the model; text prompt only)

Sheets are saved as refs/<line>/<id>.png with refs/manifest.json recording the prompt,
model and checks. A sheet is made again when its prompt changes, or with --force.
Each result is checked (plain light background, nothing cut off at the edges, three
separate views); one that fails is retried up to --tries times and the best attempt is
kept, marked for review. Needs Pillow and numpy.
"""
import argparse, base64, hashlib, io, json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roster import ROSTER, line, prompt

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REFS = os.path.join(REPO, 'refs')
MANIFEST = os.path.join(REFS, 'manifest.json')
FACTIONS = sorted({e['faction'] for e in ROSTER})


# ── HTTP ────────────────────────────────────────────────────────────────────
class ApiError(Exception):
    def __init__(self, status, body): super().__init__(f'HTTP {status}: {body[:400]}'); self.status, self.body = status, body

def call(url, headers, body=None, timeout=300):
    """JSON request with retries on rate limits and server errors (urllib uses HTTPS_PROXY)."""
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(5):
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', **headers},
                                     method='POST' if data else 'GET')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())
        except urllib.error.HTTPError as e:
            text = e.read().decode('utf-8', 'replace')
            if e.code == 429 and 'limit: 0' in text:   # no quota at all (a free-tier key): waiting will not help
                raise ApiError(e.code, text)
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                wait = float(e.headers.get('Retry-After') or 10 * 2 ** attempt)
                print(f'    HTTP {e.code}, waiting {wait:.0f} s'); time.sleep(wait); continue
            raise ApiError(e.code, text)
        except (urllib.error.URLError, TimeoutError) as e:
            if 'Tunnel connection failed' in str(e):   # the environment's network policy refuses the host
                sys.exit(f'{url.split("/")[2]} is blocked by this environment\'s network policy: add it to the allowed domains.')
            if attempt < 4: print(f'    {e}, retrying'); time.sleep(10 * 2 ** attempt); continue
            raise


# ── Providers ───────────────────────────────────────────────────────────────
class Gemini:
    base = 'https://generativelanguage.googleapis.com/v1beta'
    takes_images = True

    def __init__(self, model):
        self.key = os.environ.get('GEMINI_API_KEY') or sys.exit('Set GEMINI_API_KEY in the environment.')
        self.model = model or os.environ.get('GEMINI_IMAGE_MODEL') or 'gemini-2.5-flash-image'
        self.aspect = True

    def models(self):
        out = call(f'{self.base}/models?pageSize=1000', {'x-goog-api-key': self.key})
        return [m['name'].split('/')[-1] for m in out.get('models', [])
                if 'image' in m['name'] and 'generateContent' in m.get('supportedGenerationMethods', [])]

    def generate(self, text, images):
        parts = [{'text': text}] + [{'inline_data': {'mime_type': mime, 'data': base64.b64encode(b).decode()}} for b, mime in images]
        cfg = {'responseModalities': ['TEXT', 'IMAGE']}
        if self.aspect: cfg['imageConfig'] = {'aspectRatio': '16:9'}
        try:
            out = call(f'{self.base}/models/{self.model}:generateContent', {'x-goog-api-key': self.key},
                       {'contents': [{'parts': parts}], 'generationConfig': cfg})
        except ApiError as e:
            if e.status == 400 and self.aspect and ('imageConfig' in e.body or 'aspect' in e.body.lower()):
                self.aspect = False; return self.generate(text, images)   # a model without the setting
            if e.status == 404:
                found = self.models()
                if found and self.model not in found:
                    print(f'    model {self.model} not found; using {found[-1]} (of {", ".join(found)})')
                    self.model = found[-1]; return self.generate(text, images)
            raise
        for cand in out.get('candidates', []):
            for p in cand.get('content', {}).get('parts', []):
                blob = p.get('inlineData') or p.get('inline_data')
                if blob: return base64.b64decode(blob['data'])
        reason = [c.get('finishReason') for c in out.get('candidates', [])] or out.get('promptFeedback')
        raise ApiError(200, f'no image returned ({reason})')


class XAI:
    base = 'https://api.x.ai/v1'
    takes_images = False

    def __init__(self, model):
        self.key = os.environ.get('XAI_API_KEY') or sys.exit('Set XAI_API_KEY in the environment.')
        self.model = model or os.environ.get('XAI_IMAGE_MODEL') or 'grok-2-image'

    def models(self):
        out = call(f'{self.base}/image-generation-models', {'Authorization': f'Bearer {self.key}'})
        return [m['id'] for m in out.get('models', out.get('data', []))]

    def generate(self, text, images):
        try:
            out = call(f'{self.base}/images/generations', {'Authorization': f'Bearer {self.key}'},
                       {'model': self.model, 'prompt': text, 'n': 1, 'response_format': 'b64_json'})
        except ApiError as e:
            if e.status in (400, 404) and 'model' in e.body.lower():
                found = self.models()
                if found and self.model not in found:
                    print(f'    model {self.model} not found; using {found[0]} (of {", ".join(found)})')
                    self.model = found[0]; return self.generate(text, images)
            raise
        return base64.b64decode(out['data'][0]['b64_json'])

PROVIDERS = {'gemini': Gemini, 'xai': XAI}


# ── Checks ──────────────────────────────────────────────────────────────────
def check(img, views=3):
    """Plain light background, nothing touching the top or sides, and the expected number
    of separate views side by side. Returns (ok, details, score)."""
    a = np.asarray(img.convert('RGB').resize((768, int(768 * img.height / img.width))), dtype=float)
    h, w, _ = a.shape; b = max(4, int(min(h, w) * .02))
    border = np.concatenate([a[:b].reshape(-1, 3), a[:, :b].reshape(-1, 3), a[:, -b:].reshape(-1, 3)])
    bg = np.median(border, 0)
    plain = bg.mean() > 150 and bg.max() - bg.min() < 40 and np.percentile(np.abs(border - bg).sum(1), 90) < 60
    fg = np.abs(a - bg).sum(-1) > 90
    rows = np.where(fg.sum(1) > 3)[0]
    if not len(rows): return False, {'plain_background': bool(plain), 'cut_off': False, 'views_found': 0}, 0
    y0, y1 = rows[0], rows[-1]
    body = fg[y0: y0 + max(1, int((y1 - y0) * .8))]           # above the feet, clear of shadows on the floor
    cut = bool(fg[:b].any() or body[:, :b].sum() > 3 or body[:, -b:].sum() > 3)
    cols = body.sum(0) > max(3, h * .01)
    runs, gap, inside = 0, 0, False
    for c in cols:
        if c:
            if not inside and (runs == 0 or gap >= w * .012): runs += 1
            inside, gap = True, 0
        else:
            gap += 1
            if gap >= w * .012: inside = False
    found = runs
    ok = bool(plain and not cut and found == views)
    score = plain * 2 + (not cut) * 2 + (found == views) * 3 - abs(found - views) * .5
    return ok, {'plain_background': bool(plain), 'cut_off': cut, 'views_found': found}, score


# ── Runs ────────────────────────────────────────────────────────────────────
def load_manifest():
    try:
        with open(MANIFEST) as f: return json.load(f)
    except FileNotFoundError: return {}

def save_manifest(m):
    os.makedirs(REFS, exist_ok=True)
    with open(MANIFEST, 'w') as f: json.dump(m, f, indent=1, ensure_ascii=False, sort_keys=True)

def select(args):
    if not args or args == ['all']: return list(ROSTER)
    out = []
    for e in ROSTER:
        if any(a in (e['id'], e['faction'], line(e)) for a in args): out.append(e)
    unknown = [a for a in args if not any(a in (e['id'], e['faction'], line(e)) for e in ROSTER)]
    if unknown: sys.exit(f'Unknown: {", ".join(unknown)}. Use a faction ({", ".join(FACTIONS)}), a line, an id or "all".')
    return out

def path_of(e): return os.path.join(REFS, line(e), e['id'] + '.png')

def references(e):
    """(images to attach as (bytes, mime, relative path), id of the line's first tier or None)."""
    files = list(e.get('ref', []))
    tier = e['id'].split('-')[1]; same = None
    if tier != '1' and e.get('tier1', True):
        for ext in ('.png', '.jpg'):
            rel = f'{line(e)}/{line(e)}-1{ext}'
            if os.path.exists(os.path.join(REFS, rel)):
                if rel not in files: files.append(rel); same = f'{line(e)}-1'
                break
    out = []
    for rel in files:
        with open(os.path.join(REFS, rel), 'rb') as f:
            out.append((f.read(), 'image/png' if rel.endswith('.png') else 'image/jpeg', rel))
    return out, same

def run(entries, provider, tries, force, delay):
    man = load_manifest(); made = review = skipped = failed = 0
    for i, e in enumerate(entries):
        refs, same = references(e)
        if not provider.takes_images: refs, same = [], None
        text = prompt(e, [r[2] for r in refs], same)
        digest = hashlib.sha256(text.encode()).hexdigest()[:16]
        rec = man.get(e['id'])
        if not force and rec and rec.get('prompt_sha') == digest and os.path.exists(path_of(e)):
            skipped += 1; continue
        print(f'[{i + 1}/{len(entries)}] {e["id"]} ({e["name"]})' + (f', with {", ".join(r[2] for r in refs)}' if refs else ''))
        best = None
        for t in range(tries):
            try:
                raw = provider.generate(text, [(b, m) for b, m, _ in refs])
                img = Image.open(io.BytesIO(raw)); img.load()
            except ApiError as ex:
                if ex.status in (401, 403) or 'API_KEY_INVALID' in ex.body:
                    sys.exit(f'The provider refused the key: {ex}')
                if ex.status == 429 and 'limit: 0' in ex.body:
                    sys.exit(f'The key has no quota for {provider.model}: image models need billing enabled '
                             f'on the key\'s project (the free tier allows none).\n{ex}')
                print(f'    attempt {t + 1}: {ex}'); time.sleep(delay); continue
            except Exception as ex:
                print(f'    attempt {t + 1}: {ex}'); time.sleep(delay); continue
            ok, details, score = check(img)
            print(f'    attempt {t + 1}: {"ok" if ok else "check failed"} {details}')
            if best is None or score > best[0]: best = (score, img, ok, details)
            if ok: break
            time.sleep(delay)
        if best is None:
            failed += 1; print('    no image'); continue
        _, img, ok, details = best
        os.makedirs(os.path.dirname(path_of(e)), exist_ok=True)
        img.convert('RGB').save(path_of(e), optimize=True)
        man[e['id']] = {'file': os.path.relpath(path_of(e), REFS), 'name': e['name'], 'provider': type(provider).__name__.lower(),
                        'model': provider.model, 'prompt_sha': digest, 'prompt': text, 'references': [r[2] for r in refs],
                        'checks': details, 'ok': ok, 'made': datetime.now(timezone.utc).isoformat(timespec='seconds')}
        save_manifest(man); made += 1; review += not ok
        time.sleep(delay)
    print(f'\nMade {made} ({review} to review by eye), kept {skipped} unchanged, {failed} failed.')
    if failed: sys.exit(1)

def contact(out):
    man = load_manifest(); tiles = []
    for e in ROSTER:
        if os.path.exists(path_of(e)):
            im = Image.open(path_of(e)).convert('RGB'); im.thumbnail((480, 270))
            tile = Image.new('RGB', (480, 300), 'white'); tile.paste(im, ((480 - im.width) // 2, 0))
            ok = man.get(e['id'], {}).get('ok')
            ImageDraw.Draw(tile).text((6, 280), f'{e["id"]}  {e["name"]}' + ('' if ok else '  (review)'), fill=(0, 0, 0) if ok else (190, 0, 0))
            tiles.append(tile)
    if not tiles: sys.exit('No sheets yet.')
    cols = 4; rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * 480, rows * 300), 'white')
    for k, t in enumerate(tiles): sheet.paste(t, ((k % cols) * 480, (k // cols) * 300))
    sheet.save(out, quality=88); print(f'{len(tiles)} sheets in {out}')

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('which', nargs='*', help='"all", a faction, a line or sheet ids')
    ap.add_argument('--provider', choices=PROVIDERS, default='gemini')
    ap.add_argument('--model', help='the image model (default from the environment, else the provider default)')
    ap.add_argument('--tries', type=int, default=3, help='attempts per sheet when the checks fail')
    ap.add_argument('--force', action='store_true', help='make sheets again even if their prompt is unchanged')
    ap.add_argument('--delay', type=float, default=2.0, help='seconds between requests')
    ap.add_argument('--dry-run', action='store_true', help='print the prompts and call nothing')
    ap.add_argument('--list', action='store_true', help='list the sheets and their state')
    ap.add_argument('--models', action='store_true', help='list the image models the provider offers')
    ap.add_argument('--contact', metavar='FILE', help='write thumbnails of every sheet made so far')
    a = ap.parse_args()
    if a.contact: return contact(a.contact)
    entries = select(a.which)
    if a.list:
        man = load_manifest()
        for e in entries:
            r = man.get(e['id'])
            state = 'missing' if not r or not os.path.exists(path_of(e)) else ('ok' if r['ok'] else 'review')
            print(f'{e["id"]:14s} {e["faction"]:8s} {e["kind"]:8s} {state:8s} {e["name"]}')
        return print(f'{len(entries)} sheets')
    if a.dry_run:
        for e in entries:
            refs, same = references(e); print(f'── {e["id"]} ({e["name"]})' + (f'  [attach: {", ".join(r[2] for r in refs)}]' if refs else ''))
            print(prompt(e, [r[2] for r in refs], same), end='\n\n')
        return
    provider = PROVIDERS[a.provider](a.model)
    if a.models: return print('\n'.join(provider.models()))
    run(entries, provider, max(1, a.tries), a.force, a.delay)

if __name__ == '__main__':
    main()
