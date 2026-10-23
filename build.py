#!/usr/bin/env python3
"""Bake a Layer Type page with your own font and starting letters.

The page already computes the body in the browser, so this script is optional. It only
writes a copy of template.html with a font embedded and three letters to start with.

    python3 build.py ABC
    python3 build.py XYZ --font fonts/Figtree.ttf --weight 900 --out index.html
    python3 build.py ЖЭЮ --font path/to/YourFont.ttf --out my.html

Needs: fonttools (see requirements.txt). The font must contain the letters, and its license
must allow embedding it in a web page. Figtree (SIL OFL) is bundled.
"""
import argparse, base64, json, os
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))


def font_info(path):
    f = TTFont(path)
    cmap = f.getBestCmap()
    name = next((str(r) for r in f['name'].names if r.nameID == 16), None) or \
        next((str(r) for r in f['name'].names if r.nameID == 1), 'font')
    chars = ''.join(chr(c) for c in sorted(cmap) if c > 32 and chr(c).isprintable() and not chr(c).isspace())
    return name, chars


def bake(letters, font_path, weight, out, template):
    if len(letters) != 3 or any(c.isspace() for c in letters):
        raise SystemExit('give exactly three letters, for example: python3 build.py XYZ')
    name, chars = font_info(font_path)
    missing = [c for c in letters if c not in chars]
    if missing:
        raise SystemExit('the font has no glyph for: ' + ' '.join(missing))
    with open(font_path, 'rb') as f:
        raw = f.read()
    ext = os.path.splitext(font_path)[1].lower()
    mime, fmt = ('font/otf', 'opentype') if ext == '.otf' else ('font/ttf', 'truetype')
    face = ('@font-face{font-family:LTFont;src:url(data:%s;base64,%s) format("%s");font-weight:100 900;font-display:block}'
            % (mime, base64.b64encode(raw).decode(), fmt))
    with open(template, encoding='utf-8') as f:
        page = f.read()
    for key in ('__FONTFACE__', '__WEIGHT__', '__CHARS__', '__FONTNAME__', '__LETTERS__'):
        if key not in page:
            raise SystemExit('template.html has no %s slot' % key)
    page = (page.replace('__FONTFACE__', face).replace('__WEIGHT__', str(weight)).replace('__CHARS__', json.dumps(chars, ensure_ascii=False))
            .replace('__FONTNAME__', json.dumps(name)).replace('__LETTERS__', json.dumps(letters, ensure_ascii=False)))
    with open(out, 'w', encoding='utf-8') as f:
        f.write(page)
    print('wrote %s, %d KB, font %s, letters %s' % (out, os.path.getsize(out) // 1024, name, ' '.join(letters)))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('letters', nargs='?', default='XYZ', help='three starting letters: front, side, top (default XYZ)')
    ap.add_argument('--font', default=os.path.join(HERE, 'fonts', 'Figtree.ttf'), help='TTF or OTF with the letters (default: bundled Figtree)')
    ap.add_argument('--weight', type=int, default=900, help='weight for variable fonts (default 900)')
    ap.add_argument('--out', default=os.path.join(HERE, 'index.html'), help='output file (default: index.html next to this script)')
    ap.add_argument('--template', default=os.path.join(HERE, 'template.html'))
    a = ap.parse_args()
    bake(a.letters, a.font, a.weight, a.out, a.template)
