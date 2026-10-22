# Texture sweep data, 2026-10-22

Summary: [`docs/fork/texture-sweep.md`](../../texture-sweep.md) on `main`.

| File | Content |
|---|---|
| `duplicates.md`, `cross_tileset.csv`, `blank_or_solid.csv`, `dupes-top.png` | Identical and blank sprites; `dupes.py` regenerates them (about 8 s). |
| `clarity.md`, `clarity/` | Visual clarity review with contact sheets; `build.sh`, `idx.py`, `mk.py`, `metrics.py` regenerate them. |
| `licenses.md` | Bundled tileset licenses and outside asset candidates, with sources. |
| `verify_MSX_jerky.png` | The default tileset's `jerky` sprite (`normal_items.png#2823`), 8x. |

The scripts read the repository from `BN_REPO` (default: four levels up) and write to
`/tmp/texture-sweep/`. They need ImageMagick (`magick`).
