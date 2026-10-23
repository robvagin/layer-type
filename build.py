#!/usr/bin/env python3
"""Layer Type: three letters become one layered 3D body.

The body is the intersection of three letter prisms: the first letter reads from the
front, the second from the side, the third from above. This script cuts that body
into flat slices (and builds a blended stack and a smooth mesh), then writes one
standalone HTML file that draws it.

    python3 build.py TYP
    python3 build.py ABC --out abc.html
    python3 build.py TYP --font fonts/Figtree.ttf --weight 900

Needs: numpy, scipy, scikit-image, fonttools, pillow, trimesh, fast-simplification
(see requirements.txt). The font must contain the three letters; Figtree (SIL OFL)
is bundled and covers Latin letters.
"""
import argparse, base64, json, os, sys, warnings
warnings.filterwarnings('ignore')
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage import measure
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.basePen import BasePen

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, 'fonts', 'Figtree.ttf')
GRID = 256            # slice grid
SQUASH = 0.82         # letters are squeezed vertically so the body is not a cube
GROW = 0.45           # a light thickening closes hairline bridges and keeps the body in one piece
EPS = 0.55            # contour simplification, in grid pixels
CREASE_DEG = 34.0     # an edge is drawn as a form edge when its two faces meet at more than this


class PolyPen(BasePen):
    def __init__(self, glyphs):
        super().__init__(glyphs)
        self.polys, self.cur = [], []

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, c1, c2, p):
        p0 = self.cur[-1]
        for i in range(1, 13):
            t = i / 12
            m = 1 - t
            self.cur.append((m ** 3 * p0[0] + 3 * m * m * t * c1[0] + 3 * m * t * t * c2[0] + t ** 3 * p[0],
                             m ** 3 * p0[1] + 3 * m * m * t * c1[1] + 3 * m * t * t * c2[1] + t ** 3 * p[1]))

    def _qCurveToOne(self, c, p):
        p0 = self.cur[-1]
        for i in range(1, 9):
            t = i / 8
            m = 1 - t
            self.cur.append((m * m * p0[0] + 2 * m * t * c[0] + t * t * p[0],
                             m * m * p0[1] + 2 * m * t * c[1] + t * t * p[1]))

    def _closePath(self):
        if len(self.cur) > 2:
            self.polys.append(self.cur)
        self.cur = []

    def _endPath(self):
        self._closePath()


class Font:
    def __init__(self, path, weight):
        f = TTFont(path)
        if 'fvar' in f:
            axes = {a.axisTag: a for a in f['fvar'].axes}
            loc = {}
            if 'wght' in axes:
                loc['wght'] = min(axes['wght'].maxValue, max(axes['wght'].minValue, weight))
            if 'wdth' in axes:
                loc['wdth'] = axes['wdth'].defaultValue
            f = instantiateVariableFont(f, loc, inplace=False)
        self.glyphs = f.getGlyphSet()
        self.cmap = f.getBestCmap()
        self.name = next((str(r) for r in f['name'].names if r.nameID == 16), None) or \
            next((str(r) for r in f['name'].names if r.nameID == 1), 'font')
        self.weight = weight

    def has(self, ch):
        return ord(ch) in self.cmap

    def mask(self, ch, n, sq):
        """Letter as a boolean n x n picture: fitted to the frame, centered, squeezed by sq."""
        name = self.cmap[ord(ch)]
        pen = PolyPen(self.glyphs)
        self.glyphs[name].draw(pen)
        if not pen.polys:
            raise SystemExit('the font draws nothing for %r' % ch)
        xs = [p[0] for q in pen.polys for p in q]
        ys = [p[1] for q in pen.polys for p in q]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        span = max(x1 - x0, y1 - y0)
        s = (n * 0.88) / span
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        img = np.zeros((n, n), bool)
        for q in pen.polys:
            pts = [((px - cx) * s + n / 2, n / 2 - (py - cy) * s) for px, py in q]
            layer = Image.new('L', (n, n), 0)
            ImageDraw.Draw(layer).polygon(pts, fill=255)
            img ^= np.array(layer) > 127        # even-odd: counters stay open
        h = max(8, int(n * sq))
        sq_img = Image.fromarray((img * 255).astype('uint8')).resize((n, h))
        out = np.zeros((n, n), bool)
        k = (n - h) // 2
        out[k:k + h, :] = np.array(sq_img) > 127
        return out

    def sdf(self, ch, n, sq, ss=4):
        """Signed distance of the letter on an n x n grid, in cells of that grid: negative inside."""
        m = self.mask(ch, n * ss, sq)
        din = ndimage.distance_transform_edt(m)
        dout = ndimage.distance_transform_edt(~m)
        d = (dout - din - 0.5) / ss            # the edge lies between pixels
        return d.reshape(n, ss, n, ss).mean(axis=(1, 3)).astype(np.float32)


def chaikin(pts, k=1):
    for _ in range(k):
        out, m = [], len(pts)
        for i in range(m):
            a, b = pts[i], pts[(i + 1) % m]
            out.append((a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25))
            out.append((a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75))
        pts = out
    return pts


def contours(f, n):
    """Zero level of a distance field -> simplified polygons in [-1, 1]."""
    out = []
    for c in measure.find_contours(np.pad(f - GROW, 1, constant_values=1e3), 0.0):
        c = c - 1
        if len(c) < 12:
            continue
        pts = chaikin([(float(q[1]), float(q[0])) for q in c], 1)
        a = measure.approximate_polygon(np.array([[y, x] for x, y in pts]), tolerance=EPS)
        if len(a) < 4:
            continue
        out.append([[round(float(q[1] / (n - 1) * 2 - 1), 4), round(float(q[0] / (n - 1) * 2 - 1), 4)] for q in a])
    return out


def slices(font, letters, n=GRID):
    """Three stacks of flat slices, one per axis. The solid is max(front, side, top) in distance terms."""
    Bs, Rs, Zs = (font.sdf(ch, n, SQUASH) for ch in letters)

    def field(axis, i):
        if axis == 'front':
            return np.maximum(Bs, np.maximum(Rs[:, i][:, None], Zs[i, :][None, :]))
        if axis == 'side':
            return np.maximum(Rs, np.maximum(Bs[:, i][:, None], Zs[:, i][None, :]))
        return np.maximum(Zs.T, np.maximum(Bs[i, :][:, None], Rs[i, :][None, :]))

    def stack(axis):
        res = []
        for i in range(n):
            f = field(axis, i)
            if (f < GROW).sum() < 40:
                continue
            cs = contours(f, n)
            if cs:
                res.append({'d': round(i / (n - 1) * 2 - 1, 4), 'p': cs})
        return res

    data = {'font': '%s %d' % (font.name, font.weight), 'layers': n,
            'letters': list(letters),
            'axes': {'front': stack('front'), 'side': stack('side'), 'top': stack('top')}}
    return data, (Bs, Rs, Zs)


def silhouettes(fields):
    """Share of each letter that still shows in the body's shadow, in percent. The body is closed by max()."""
    Bs, Rs, Zs = fields
    vol = np.maximum(np.maximum(Bs[:, :, None], Rs[:, None, :]), Zs.T[None, :, :]) < GROW
    shadows = (vol.any(2), vol.any(1), vol.any(0).T)
    letters = (Bs < 0, Rs < 0, Zs < 0)
    return [round(float((s & l).sum() / max(1, l.sum())) * 100, 1) for s, l in zip(shadows, letters)]


def blend(font, letters, n=GRID, layers=132):
    """A layer cake: the stack flows from the first letter to the second to the third.
    The morph runs on signed distance, so holes appear and vanish by themselves."""
    def sdf(ch):
        m = font.mask(ch, n, 1.0)
        return ndimage.distance_transform_edt(~m) - ndimage.distance_transform_edt(m)

    D = [sdf(ch) for ch in letters]
    plateau, bridge = 0.17, 0.245          # each letter holds a few layers pure, then melts into the next

    def at(u):
        if u < plateau: return 0, 0.0
        if u < plateau + bridge: return 0, (u - plateau) / bridge
        if u < plateau * 2 + bridge: return 1, 0.0
        if u < plateau * 2 + bridge * 2: return 1, (u - plateau * 2 - bridge) / bridge
        return 2, 0.0

    def smooth(x): return x * x * (3 - 2 * x)

    def outline(m, eps=0.8):
        out = []
        f = ndimage.gaussian_filter(m.astype(np.float32), 0.7)
        for c in measure.find_contours(np.pad(f, 1), 0.5):
            c = c - 1
            if len(c) < 10:
                continue
            a = measure.approximate_polygon(c, tolerance=eps)
            if len(a) < 4:
                continue
            out.append([[round(float(q[1] / (n - 1) * 2 - 1), 4), round(float(q[0] / (n - 1) * 2 - 1), 4)] for q in a])
        return out

    stack, pure = [], {}
    for i in range(layers):
        u = i / (layers - 1)
        k, s = at(u)
        f = D[k] if s == 0.0 else D[k] * (1 - smooth(s)) + D[min(k + 1, 2)] * smooth(s)
        m = f < 0
        if m.sum() < 40:
            continue
        cs = outline(m)
        if not cs:
            continue
        w = 1.0 if s == 0.0 else round(float(1 - np.sin(np.pi * s)), 4)   # purity of the layer: 1 on a letter's plateau
        stack.append({'d': round((1 - u) * 2 - 1, 4), 'p': cs, 'u': round(u, 4), 'w': w})
        if s == 0.0 and letters[k] not in pure:
            pure[letters[k]] = round((1 - u) * 2 - 1, 4)
    return {'font': '%s %d' % (font.name, font.weight), 'layers': layers, 'pure': pure, 'stack': stack}


def mesh(font, letters, n=224, tris=3000):
    """One smooth surface: marching cubes on the zero level, light smoothing, decimation, crease edges."""
    import trimesh
    import fast_simplification
    Bs, Rs, Zs = (font.sdf(ch, n, SQUASH) for ch in letters)
    vol = np.maximum(np.maximum(Bs[:, :, None], Rs[:, None, :]), Zs.T[None, :, :]).astype(np.float32)
    v, f, _, _ = measure.marching_cubes(vol, level=GROW, step_size=1)
    v = v[:, [1, 0, 2]]                    # volume order (v, u, w) -> viewer world (x = u, y = v, z = w)
    f = f[:, ::-1]                         # swapping two axes flips handedness; restore the winding
    m = trimesh.Trimesh(vertices=v, faces=f, process=True)
    m.update_faces(m.nondegenerate_faces())
    m.remove_unreferenced_vertices()
    parts = sorted(m.split(only_watertight=False), key=lambda x: len(x.faces), reverse=True)
    m = parts[0]
    trimesh.smoothing.filter_taubin(m, lamb=0.5, nu=-0.53, iterations=8)   # keeps volume, unlike a plain laplacian
    ratio = max(0.02, 1 - tris / len(m.faces))
    v2, f2 = fast_simplification.simplify(m.vertices.astype(np.float32), m.faces.astype(np.uint32), ratio)
    m = trimesh.Trimesh(vertices=v2, faces=f2, process=True)
    m.remove_unreferenced_vertices()
    m.fix_normals()
    if m.volume < 0:
        m.invert()
    m.vertices -= m.bounds.mean(0)
    m.vertices /= np.abs(m.bounds).max()
    fn = m.face_normals
    e_faces = m.face_adjacency
    e_verts = m.face_adjacency_edges
    ang = np.degrees(np.arccos(np.clip((fn[e_faces[:, 0]] * fn[e_faces[:, 1]]).sum(1), -1, 1)))
    crease = ang > CREASE_DEG
    face_edges = [[] for _ in range(len(m.faces))]
    for ei, (fa, fb) in enumerate(e_faces):
        face_edges[fa].append(ei)
        face_edges[fb].append(ei)
    FE = np.full((len(m.faces), 3), -1, np.int32)
    for fi, lst in enumerate(face_edges):
        for k, ei in enumerate(lst[:3]):
            FE[fi, k] = ei

    def b64(a):
        return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()

    return {'font': '%s %d' % (font.name, font.weight), 'tris': int(len(m.faces)), 'verts': int(len(m.vertices)),
            'v': b64(m.vertices.astype(np.float32)), 'f': b64(m.faces.astype(np.uint32)),
            'ev': b64(e_verts.astype(np.uint32)), 'ef': b64(e_faces.astype(np.uint32)),
            'ec': b64(crease.astype(np.uint8)), 'fe': b64(FE.astype(np.int32))}


def build(letters, font_path, weight, out, template):
    if len(letters) != 3 or any(c.isspace() for c in letters):
        raise SystemExit('give exactly three letters, for example: python3 build.py TYP')
    font = Font(font_path, weight)
    missing = [c for c in letters if not font.has(c)]
    if missing:
        raise SystemExit('the font has no glyph for: ' + ' '.join(missing))
    print('letters %s (front, side, top), font %s %d' % (' '.join(letters), font.name, weight))
    data, fields = slices(font, letters)
    data['match'] = silhouettes(fields)
    for k, v in data['axes'].items():
        print('  %-5s stack: %d slices' % (k, len(v)))
    if not all(len(v) for v in data['axes'].values()) or min(data['match']) < 40:
        raise SystemExit('these three letters leave no readable body (the prisms barely overlap); try other letters')
    print('  silhouette match, letter inside the body shadow: %s %%' % ' / '.join('%s %.1f' % t for t in zip(letters, data['match'])))
    bl = blend(font, letters)
    ms = mesh(font, letters)
    print('  blend %d layers, mesh %d triangles' % (len(bl['stack']), ms['tris']))
    with open(template, encoding='utf-8') as f:
        page = f.read()
    for key in ('__DATA__', '__BLEND__', '__MESH__'):
        if key not in page:
            raise SystemExit('template.html has no %s slot' % key)
    comp = lambda d: json.dumps(d, separators=(',', ':'))
    page = page.replace('__DATA__', comp(data)).replace('__BLEND__', comp(bl)).replace('__MESH__', comp(ms))
    page = page.replace('__TITLE__', 'Layer Type · %s' % letters)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(page)
    print('wrote %s, %d KB' % (out, os.path.getsize(out) // 1024))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('letters', help='three letters: front, side, top')
    ap.add_argument('--font', default=FONT, help='a TTF or OTF with the letters (default: bundled Figtree)')
    ap.add_argument('--weight', type=int, default=900, help='weight for variable fonts (default 900)')
    ap.add_argument('--out', default=None, help='output file (default: index.html next to this script)')
    ap.add_argument('--template', default=os.path.join(HERE, 'template.html'))
    a = ap.parse_args()
    build(a.letters, a.font, a.weight, a.out or os.path.join(HERE, 'index.html'), a.template)
