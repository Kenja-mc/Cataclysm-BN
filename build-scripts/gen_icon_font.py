#!/usr/bin/env python3
"""Build data/font/bno-icons.ttf from the SVGs in data/font/icons-src/.

Setup and run:
    python3 -m venv /tmp/iconfont-venv && /tmp/iconfont-venv/bin/pip install fonttools
    /tmp/iconfont-venv/bin/python build-scripts/gen_icon_font.py [output.ttf]

Sources:
- pinhead/: Pinhead v16.26.0 stance figures (CC0 1.0), at U+10F000..U+10F003, two cells wide.
- mdi/: Material Design Icons from npm @mdi/svg 7.4.47 (Apache-2.0), one cell wide at their
  official codepoints (each matches @mdi/svg meta.json), plus two-cell copies at
  U+10F010 upward in MDI order.

Metrics match data/font/JetBrainsMonoNL-Regular.ttf (1000 UPM, 600-unit advance, ascent 1020,
descent 300), so a one-cell icon is a 600-unit square and a two-cell icon a 1200-unit square,
both centred on the middle of the line. Output is byte-identical across runs.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.misc.timeTools import timestampFromString
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import SVGPath

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "font" / "icons-src"
DEFAULT_OUT = ROOT / "data" / "font" / "bno-icons.ttf"

FAMILY = "BN Overhaul Icons"
VERSION = "1.000"
TIMESTAMP = timestampFromString("Thu Oct 22 00:00:00 2026")

UPM = 1000
ASCENT = 1020
DESCENT = 300
CELL = 600
LINE_MIDDLE = (ASCENT - DESCENT) // 2

PINHEAD = {
    "walk": 0x10F000,
    "run": 0x10F001,
    "crouch": 0x10F002,
    "prone": 0x10F003,
}

# Two-cell copies of MDI, in MDI table order; src/icon_font.h names them.
MDI_WIDE_START = 0x10F010

MDI = {
    "weather-sunny": 0xF0599,
    "weather-night": 0xF0594,
    "weather-cloudy": 0xF0590,
    "weather-rainy": 0xF0597,
    "weather-lightning": 0xF0593,
    "weather-snowy": 0xF0598,
    "weather-fog": 0xF0591,
    "stairs-down": 0xF12BE,
    "boxing-glove": 0xF0B65,
    "sword": 0xF04E5,
    "pistol": 0xF0703,
    "bow-arrow": 0xF1841,
    "karate": 0xF082C,
    "walk": 0xF0583,
    "run": 0xF070E,
    "star-four-points": 0xF0AE2,
    "compass": 0xF018B,
    "gas-station": 0xF0298,
    "battery": 0xF0079,
    "bandage": 0xF0DAF,
    "cup-water": 0xF01AB,
    "food-drumstick": 0xF141F,
    "power-sleep": 0xF0904,
    "thermometer": 0xF050F,
    "clock-outline": 0xF0150,
    "lightbulb-on": 0xF06E8,
    "weather-windy": 0xF059D,
    "check": 0xF012C,
    "moon-new": 0xF0F64,
    "moon-waxing-crescent": 0xF0F67,
    "moon-first-quarter": 0xF0F61,
    "moon-waxing-gibbous": 0xF0F68,
    "moon-full": 0xF0F62,
    "moon-waning-gibbous": 0xF0F66,
    "moon-last-quarter": 0xF0F63,
    "moon-waning-crescent": 0xF0F65,
    # Appended last so the wide-copy codepoints of the icons above do not shift.
    "lock": 0xF033E,
}


def glyph_name(codepoint: int) -> str:
    return f"u{codepoint:X}"


def draw_svg(svg: Path, size: int):
    """Return a TrueType glyph of `svg` scaled into a `size` square centred on the line."""
    root = ET.parse(svg).getroot()
    for element in root.iter():
        if element.get("fill-rule") == "evenodd" or element.get("transform") is not None:
            raise SystemExit(f"{svg}: unsupported fill-rule or transform")
    min_x, min_y, width, height = (float(v) for v in root.get("viewBox").split())
    if width != height:
        raise SystemExit(f"{svg}: viewBox is not square")
    scale = size / width
    bottom = LINE_MIDDLE - size / 2
    # SVG y grows downwards; flip it and place the view box on [bottom, bottom + size].
    transform = (scale, 0, 0, -scale, -min_x * scale, bottom + size + min_y * scale)
    outline = RecordingPen()
    SVGPath.fromstring(svg.read_bytes(), transform=transform).draw(outline)
    # Fills close open subpaths implicitly; glyph contours must say so.
    outline.value = [("closePath", ()) if op == "endPath" else (op, args) for op, args in outline.value]

    area = AreaPen()
    outline.replay(area)
    tt_pen = TTGlyphPen(None)
    # TrueType outer contours run clockwise (negative area).
    target = ReverseContourPen(tt_pen) if area.value > 0 else tt_pen
    outline.replay(Cu2QuPen(target, max_err=1.0, reverse_direction=False))
    return tt_pen.glyph()


def build(out: Path) -> None:
    glyphs = {".notdef": TTGlyphPen(None).glyph()}
    advances = {".notdef": CELL}
    cmap = {}

    def add(codepoint: int, svg: Path, cells: int) -> None:
        gname = glyph_name(codepoint)
        glyphs[gname] = draw_svg(svg, cells * CELL)
        advances[gname] = cells * CELL
        cmap[codepoint] = gname

    for name, codepoint in PINHEAD.items():
        add(codepoint, SRC / "pinhead" / f"{name}.svg", 2)
    for index, (name, codepoint) in enumerate(MDI.items()):
        add(codepoint, SRC / "mdi" / f"{name}.svg", 1)
        add(MDI_WIDE_START + index, SRC / "mdi" / f"{name}.svg", 2)

    order = [".notdef", *sorted((g for g in glyphs if g != ".notdef"), key=lambda g: int(g[1:], 16))]
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    glyf = fb.font["glyf"]
    fb.setupHorizontalMetrics({g: (advances[g], glyf[g].xMin if glyf[g].numberOfContours else 0) for g in order})
    fb.setupHorizontalHeader(ascent=ASCENT, descent=-DESCENT)
    fb.setupNameTable(
        {
            "copyright": "Pinhead figures: CC0 1.0 (waysidemapping/pinhead). "
            "Material Design Icons: Pictogrammers, Apache License 2.0.",
            "familyName": FAMILY,
            "styleName": "Regular",
            "uniqueFontIdentifier": f"{FAMILY} Regular {VERSION}",
            "fullName": f"{FAMILY} Regular",
            "psName": "BNOverhaulIcons-Regular",
            "version": f"Version {VERSION}",
            "licenseDescription": "Licensed under the Apache License, Version 2.0; "
            "Pinhead glyphs are CC0 1.0. See data/font/icons-src/.",
            "licenseInfoURL": "https://www.apache.org/licenses/LICENSE-2.0",
        }
    )
    fb.setupOS2(
        version=4,
        sTypoAscender=ASCENT,
        sTypoDescender=-DESCENT,
        sTypoLineGap=0,
        usWinAscent=ASCENT,
        usWinDescent=DESCENT,
        fsSelection=0x40 | 0x80,  # REGULAR | USE_TYPO_METRICS
        fsType=0,
        achVendID="NONE",
    )
    fb.setupPost(keepGlyphNames=False)
    fb.setupHead(unitsPerEm=UPM, created=TIMESTAMP, modified=TIMESTAMP, fontRevision=float(VERSION))
    fb.font.recalcTimestamp = False
    fb.save(out)


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    build(out)
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
