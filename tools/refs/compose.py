"""Put separately generated views together into one turnaround sheet.

    python3 tools/refs/compose.py OUT.png VIEW.png:CROWN:GROUND [VIEW.png:CROWN:GROUND ...]

Used when an image model cannot hold a design across a whole sheet but can draw one view at a time (the Akhekh's
doubled head shrank on every full sheet). Each view is given with two heights in its own pixels: the top of the head
and the ground under the feet. Every view is scaled so that height matches the first view's, then all share one scale
and one ground line, left to right in the order given. The background of each view is evened out to one flat grey and
only the creature and its shadow are blended in, so no seams show. Example (refs/akhekh/akhekh-1.png):

    python3 tools/refs/compose.py refs/akhekh/akhekh-1.png refs/akhekh/sources/side.png:144:714 \\
        refs/akhekh/sources/front.png:122:726 refs/akhekh/sources/back.png:164:684
"""
import sys
import numpy as np
from PIL import Image, ImageFilter

W, H, BG, GAP, MARGIN, PAD = 2688, 1536, 226.0, 50, 40, 40


def blur(x):
    """A wide blur of a float image: at quarter size, three passes of a separable box filter (close to a Gaussian)."""
    h, w = x.shape
    sm = np.asarray(Image.fromarray(x.astype(np.float32), mode='F').resize((w // 4, h // 4), Image.BILINEAR))
    k = np.ones(31, np.float32) / 31
    for _ in range(3):
        sm = np.apply_along_axis(lambda r: np.convolve(np.pad(r, 15, mode='edge'), k, 'valid'), 1, sm)
        sm = np.apply_along_axis(lambda c: np.convolve(np.pad(c, 15, mode='edge'), k, 'valid'), 0, sm)
    return np.asarray(Image.fromarray(sm.astype(np.float32), mode='F').resize((w, h), Image.BILINEAR))


def normalise(img):
    """Divide out the background so it becomes flat BG: mask the subject, then fill the background in under it with
    a normalised blur of the background around it (smooth enough to follow the studio light falloff)."""
    a = np.asarray(img.convert('RGB')).astype(np.float32)
    left, right = np.median(a[:, :24], axis=1), np.median(a[:, -24:], axis=1)
    t = np.linspace(0, 1, a.shape[1])[None, :, None]
    rough = left[:, None, :] * (1 - t) + right[:, None, :] * t
    subject = (np.abs(a - rough).max(axis=2) > 12).astype(np.uint8) * 255
    keep = (np.asarray(Image.fromarray(subject).filter(ImageFilter.MaxFilter(15))) == 0).astype(np.float32)
    wsum = blur(keep * 255) + 1e-3
    field = np.stack([blur(a[..., c] * keep) / wsum * 255 for c in range(3)], axis=2)
    field = np.where(wsum[..., None] > 8, field, rough)
    return np.clip(a / np.maximum(field, 1) * BG, 0, 255)


def subject_box(n):
    busy = Image.fromarray(((np.abs(n - BG).max(axis=2) > 22) * 255).astype(np.uint8))
    ys, xs = np.nonzero(np.asarray(busy.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(9))))
    return xs.min(), ys.min(), xs.max(), ys.max()


def soft_mask(crop, feather):
    """Alpha for the creature and its shadow, faded out towards the crop's edges."""
    d = np.abs(np.asarray(crop).astype(np.float32) - BG).max(axis=2)
    d = np.asarray(Image.fromarray(np.clip(d * 8, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))) / 8.0
    alpha = Image.fromarray((np.clip((d - 3) / 7, 0, 1) * 255).astype(np.uint8))
    alpha = np.asarray(alpha.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.5))) / 255.0
    ramp = lambda n: np.clip(np.minimum(np.arange(n), np.arange(n)[::-1]) / feather, 0, 1)
    return alpha * ramp(crop.height)[:, None] * ramp(crop.width)[None, :]


def compose(out, specs):
    views = []
    for spec in specs:
        path, crown, ground = spec.rsplit(':', 2); crown, ground = float(crown), float(ground)
        n = normalise(Image.open(path))
        x0, y0, x1, y1 = subject_box(n)
        views.append(dict(n=n, box=(x0, y0, x1, max(y1, ground)), ground=ground, height=ground - crown))
    for v in views: v['k'] = views[0]['height'] / v['height']        # each view to the first view's creature height
    widths = [(v['box'][2] - v['box'][0]) * v['k'] for v in views]
    above = max((v['ground'] - v['box'][1]) * v['k'] for v in views)
    below = max((v['box'][3] - v['ground']) * v['k'] for v in views) + 30
    s = min((W - 2 * MARGIN - GAP * (len(views) - 1)) / sum(widths), (H - 2 * MARGIN) / (above + below))
    ground_y = MARGIN + above * s + (H - 2 * MARGIN - (above + below) * s) / 2
    free = W - 2 * MARGIN - sum(widths) * s
    gap = max(GAP, free / (len(views) + 1))
    x = MARGIN + (free - gap * (len(views) - 1)) / 2
    canvas = np.full((H, W, 3), BG, np.float32)
    for v, w in zip(views, widths):
        x0, y0, x1, y1 = v['box']
        h, wd = v['n'].shape[:2]
        cx0, cy0, cx1, cy1 = max(0, x0 - PAD), max(0, y0 - PAD), min(wd, x1 + PAD), min(h, y1 + PAD + 20)
        f = v['k'] * s
        crop = Image.fromarray(v['n'][cy0:cy1, cx0:cx1].astype(np.uint8))
        crop = crop.resize((max(1, round(crop.width * f)), max(1, round(crop.height * f))), Image.LANCZOS)
        alpha = soft_mask(crop, max(4, int(PAD * f * .9)))
        px, py = int(round(x - (x0 - cx0) * f)), int(round(ground_y - (v['ground'] - cy0) * f))
        ys0, xs0, ys1, xs1 = max(0, py), max(0, px), min(H, py + crop.height), min(W, px + crop.width)
        c = np.asarray(crop).astype(np.float32)[ys0 - py:ys1 - py, xs0 - px:xs1 - px]
        al = alpha[ys0 - py:ys1 - py, xs0 - px:xs1 - px, None]
        canvas[ys0:ys1, xs0:xs1] = canvas[ys0:ys1, xs0:xs1] * (1 - al) + c * al
        x += w * s + gap
    Image.fromarray(canvas.astype(np.uint8)).save(out, optimize=True)


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    compose(sys.argv[1], sys.argv[2:])
