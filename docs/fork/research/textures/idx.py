#!/usr/bin/env python3
"""Resolve CDDA tileset tile ids to (sheet, pixel box). fg values are global sprite indices."""
import json, subprocess, sys, os, functools

ROOT = os.environ.get("BN_REPO", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

@functools.lru_cache(maxsize=None)
def dims(path):
    out = subprocess.run(['magick', 'identify', '-format', '%w %h', path],
                         capture_output=True, text=True, check=True).stdout
    w, h = out.split()
    return int(w), int(h)

RAW = {}

def load(tsdir):
    cfg = os.path.join(ROOT, 'gfx', tsdir, 'tile_config.json')
    d = json.load(open(cfg))
    dflt = d.get('tile_info', [{}])[0]
    sheets, off = [], 0
    for s in d['tiles-new']:
        f = s['file']
        path = os.path.join(ROOT, f) if f.startswith('gfx/') else os.path.join(ROOT, 'gfx', tsdir, f)
        sw = s.get('sprite_width') or dflt.get('width', 32)
        sh = s.get('sprite_height') or dflt.get('height', 32)
        w, h = dims(path)
        cols, rows = w // sw, h // sh
        sheets.append(dict(file=f, path=path, sw=sw, sh=sh, w=w, h=h, cols=cols, rows=rows,
                           count=cols * rows, base=off, ox=s.get('sprite_offset_x', 0),
                           oy=s.get('sprite_offset_y', 0), raw=s))
        off += cols * rows
    idx = {}
    for si, s in enumerate(sheets):
        for t in s['raw'].get('tiles', []):
            tid = t.get('id')
            keys = tid if isinstance(tid, list) else [tid]
            for k in keys:
                if k is None:
                    continue
                idx.setdefault(k, []).append((si, t.get('fg'), t.get('bg')))
                RAW.setdefault(tsdir, {}).setdefault(k, []).append(t)
    return sheets, idx

def locate(sheets, gid):
    for i in range(len(sheets) - 1, -1, -1):
        if gid >= sheets[i]['base']:
            n = gid - sheets[i]['base']
            if n < sheets[i]['count']:
                return i, n
            return i, None
    return None, None

def box(sheets, si, n):
    s = sheets[si]
    return (s['sw'], s['sh'], n % s['cols'] * s['sw'], n // s['cols'] * s['sh'])

def crop_cmd(sheets, gid, out):
    si, n = locate(sheets, gid)
    if si is None or n is None:
        return None
    b = box(sheets, si, n)
    return ['magick', sheets[si]['path'], '-crop', '%dx%d+%d+%d' % b, '+repage', out]

if __name__ == '__main__':
    cmd = sys.argv[1]
    ts = sys.argv[2]
    sheets, idx = load(ts)
    if cmd == 'sheets':
        for i, s in enumerate(sheets):
            print(i, s['file'], '%dx%d' % (s['sw'], s['sh']), 'cols', s['cols'], 'rows', s['rows'],
                  'count', s['count'], 'base', s['base'], 'off', s['ox'], s['oy'])
    elif cmd == 'find':
        pat = sys.argv[3]
        for k in sorted(idx):
            if pat in k:
                for si, fg, bg in idx[k]:
                    print(k, '|', sheets[si]['file'], 'fg', fg, 'bg', bg)
    elif cmd == 'one':
        for k in sys.argv[3:]:
            print(k, idx.get(k))
    elif cmd == 'count':
        print(len(idx), 'ids')
