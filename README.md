# Layer Type

Type any three letters and get one layered 3D body. The first letter reads from the front, the second from the side, the third from above. It is the intersection of three letter prisms, cut into flat slices, so you can fan it out like a deck of slides, spread it as a layer cake, or draw it as a blueprint.

One HTML page. It computes the body in your browser: no server, no install, no Python needed to use it.

![Layer Type](docs/preview.png)

## Use it

Open `index.html` in a modern browser. It starts with **X Y Z**. Click a letter field, type another letter or a digit, and the body rebuilds in a moment. Drag to rotate, scroll to zoom, pick a preset. **Export frame** saves the current view as SVG or PNG; the SVG is built from the same shapes the canvas draws.

Not every triple makes a body: the three prisms have to overlap. When they barely do, the panel says so quietly and keeps the previous body. The line at the bottom of the panel shows how much of each letter still shows in the body's shadow (above 85 % reads well). Capitals with heavy strokes work best, and swapping the order changes which letter reads from the front.

The letters are drawn with the bundled Figtree (weight 900), which covers Latin letters, digits and common punctuation. For other scripts, bake a page with your own font (below).

## What is on the panel

- **Letters**: front, side, top.
- **Body**: Intersection (one body, three readings) or Blend (the stack flows from the first letter to the second to the third).
- **Drawing**: Layers (flat slides), Edges (a line drawing with hidden lines removed), Mesh (one smooth surface drawn along its form edges).
- **Presets**: Deck, Fan, Row, Cake, Trail, Slab, Night, Blueprint, Slant.
- **Shape**: depth stretch, slant, bend, stack twist. **Stack**: how many slides, solidity, layer spacing, spread. **Color**: near layer, far layer, background, fade curve, tone steps and wave.
- **Motion**: spin, camera tours (front, side, top in turn; rock; tumble) and layer behaviors (shuffle, riffle, wave, spiral, explode, assemble and more).
- Every number can be dragged, typed, or stepped with the arrow keys (Shift = 10x). Typing a value beyond the slider range widens the range.
- Reduced motion is respected: with it on, the spin, tours and layer behaviors start switched off.

## Bake a page with your own font or letters

`build.py` writes a copy of the page with another font embedded and other starting letters. It needs only `fonttools` (`pip install -r requirements.txt`):

```sh
python3 build.py ABC                                   # starts with A B C
python3 build.py ЖЭЮ --font fonts/YourFont.ttf --out my.html
```

Use a font whose license lets you embed it in a web page. `--weight` sets the weight for variable fonts (default 900).

## How it works

Each letter is drawn on a canvas with the font, then turned into a signed distance field. The body is the maximum of the three fields, which is the intersection with smooth edges on any grid. Flat slices come from the zero level of that field (marching squares). The Blend stack morphs between the letters on distance, so counters open and close by themselves. The mesh comes from surface nets on the same field, with volume-keeping smoothing and quadric decimation to about 3000 triangles; it is built right after the slices and drawn along the edges where faces meet at a sharp angle.

## Requirements

Any current browser (Canvas 2D). Baking a page: Python 3.9+ and `fonttools`.

## License

MIT, see [LICENSE](LICENSE). The bundled font Figtree is under the SIL Open Font License 1.1, see [fonts/OFL.txt](fonts/OFL.txt).
