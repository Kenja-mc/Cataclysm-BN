#!/usr/bin/env python3
"""Build labelled contact sheets from a tileset's sprites.

stdin lines:  id            (label = id)
              label | id
Tile ids may carry a multitile variant suffix: t_water_sh[center]
A raw global sprite index may be given as: spr:12345

options: --ts DIR --out FILE --cols N --scale N --post-scale N --bg hex
         --floor tileid  --points N --debug 1
"""
import argparse, subprocess, sys, os, tempfile
sys.path.insert(0, '/tmp/texture-sweep')
import idx as I

ap = argparse.ArgumentParser()
ap.add_argument('--ts', default='MSX++UnDeadPeopleEdition')
ap.add_argument('--out', required=True)
ap.add_argument('--cols', type=int, default=6)
ap.add_argument('--scale', type=int, default=3)
ap.add_argument('--post-scale', type=int, default=1)
ap.add_argument('--bg', default='#2b2b2b')
ap.add_argument('--floor', default=None)
ap.add_argument('--points', type=float, default=9)
ap.add_argument('--debug', type=int, default=0)
a = ap.parse_args()

sheets, index = I.load(a.ts)
tmp = tempfile.mkdtemp()
files = []


def resize_in_place(path, pct):
    if pct != 100:
        subprocess.run(['magick', path, '-filter', 'point', '-resize', '%d%%' % pct, path], check=True)


def spr_file(gid, name, scale):
    cmd = I.crop_cmd(sheets, gid, name)
    if cmd is None:
        return None
    subprocess.run(cmd, check=True)
    resize_in_place(name, scale * 100)
    return name


def size_of(path):
    out = subprocess.run(['magick', 'identify', '-format', '%w %h', path],
                         capture_output=True, text=True, check=True).stdout.split()
    return int(out[0]), int(out[1])


def composite(base, top):
    """Composite top over base without cropping either; canvas = max size."""
    bw, bh = size_of(base)
    tw, th = size_of(top)
    w, h = max(bw, tw), max(bh, th)
    subprocess.run(['magick', base, '-colorspace', 'sRGB', '-background', 'none',
                    '-gravity', 'northwest', '-extent', '%dx%d' % (w, h),
                    top, '-composite', top], check=True)


def tile_floor(floor_tile, w, h, out):
    subprocess.run(['magick', '-size', '%dx%d' % (w, h), 'tile:' + floor_tile, out], check=True)


def first_val(v):
    if isinstance(v, list):
        return first_val(v[0])
    if isinstance(v, dict):
        return first_val(v.get('sprite', next(iter(v.values()))))
    return v


floorname = None
if a.floor:
    floorname = spr_file(first_val(index[a.floor][0][1]), os.path.join(tmp, 'floor.png'), a.scale)

for line in sys.stdin:
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    label, tid = [x.strip() for x in line.split('|', 1)] if '|' in line else (line, line)

    variant = None
    if '[' in tid and tid.endswith(']'):
        tid, variant = tid[:-1].split('[', 1)

    if tid.startswith('spr:'):
        gid = int(tid[4:])
    else:
        if tid not in index:
            print('MISSING', tid, file=sys.stderr)
            continue
        fg, bg = index[tid][0][1], index[tid][0][2]
        if variant:
            tile = I.RAW[a.ts][tid][0]
            for at in tile.get('additional_tiles', []):
                if at['id'] == variant:
                    fg, bg = at.get('fg'), at.get('bg')
                    break
            else:
                print('NOVARIANT', tid, variant, file=sys.stderr)
                continue
        gid = first_val(fg)
        if gid is None:
            print('NOFG', tid, file=sys.stderr)
            continue
    si2, n = I.locate(sheets, gid)
    where = '%s#%d' % (sheets[si2]['file'], gid)
    name = os.path.join(tmp, '%05d.png' % len(files))
    if spr_file(gid, name, a.scale) is None:
        print('BADBOX', tid, gid, file=sys.stderr)
        continue
    if not tid.startswith('spr:') and bg is not None:
        bname = os.path.join(tmp, 'b%05d.png' % len(files))
        if spr_file(first_val(bg), bname, a.scale) is not None:
            composite(bname, name)
    if floorname:
        tw, th = size_of(name)
        fname = os.path.join(tmp, 'f%05d.png' % len(files))
        tile_floor(floorname, tw, th, fname)
        composite(fname, name)
    resize_in_place(name, a.post_scale * 100)
    if a.debug:
        print(len(files), label, where, name, file=sys.stderr)
    files.append((label + '\n' + where, name))

if not files:
    sys.exit('no sprites')

cmd = ['magick', 'montage']
for lab, f in files:
    cmd += ['-label', lab, f]
cmd += ['-tile', '%dx' % a.cols, '-geometry', '+3+3', '-background', a.bg,
        '-fill', '#e8e8e8', '-pointsize', str(a.points), a.out]
subprocess.run(cmd, check=True)
print('wrote', a.out, len(files), 'sprites')
