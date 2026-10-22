#!/usr/bin/env python3
"""Metrics for tileset sprites: coverage, luminance, contrast, pairwise diff,
silhouette IoU, and deuteranopia simulation distance.

usage:
  metrics.py TS stats FLOORTILE ID...
  metrics.py TS diff A,B ...
  metrics.py TS sim A,B ...
  metrics.py TS cvd A,B ...
"""
import sys, subprocess, math
sys.path.insert(0, '/tmp/texture-sweep')
import idx as I

SHEETS = {}
DEUT = ((0.625, 0.375, 0.0), (0.700, 0.300, 0.0), (0.000, 0.300, 0.700))


def fv(v):
    if isinstance(v, list):
        return fv(v[0])
    if isinstance(v, dict):
        return fv(v.get('sprite'))
    return v


def sheet(ts):
    if ts not in SHEETS:
        SHEETS[ts] = I.load(ts)
    return SHEETS[ts]


def resolve(ts, tid):
    if isinstance(tid, int):
        return tid
    var = None
    if '[' in tid and tid.endswith(']'):
        tid, var = tid[:-1].split('[', 1)
    sheet(ts)
    tile = I.RAW[ts][tid][0]
    if var:
        for at in tile.get('additional_tiles', []):
            if at['id'] == var:
                return fv(at.get('fg'))
        raise KeyError('%s has no variant %s' % (tid, var))
    return fv(sheet(ts)[1][tid][0][1])


def rgba(ts, gid):
    sheets, _ = sheet(ts)
    si, n = I.locate(sheets, gid)
    if n is None:
        raise ValueError('sprite %s outside sheet %s' % (gid, sheets[si]['file']))
    b = I.box(sheets, si, n)
    out = subprocess.run(['magick', sheets[si]['path'], '-crop', '%dx%d+%d+%d' % b,
                          '+repage', 'rgba:-'], capture_output=True, check=True).stdout
    px = [(out[i], out[i + 1], out[i + 2], out[i + 3]) for i in range(0, len(out), 4)]
    return px, b[0], b[1]


def lum(p):
    return 0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2]


def meancol(ts, tid):
    px, _, _ = rgba(ts, resolve(ts, tid))
    op = [p for p in px if p[3] > 127]
    if not op:
        return None
    return tuple(sum(p[i] for p in op) / len(op) for i in range(3))


def cvd(c, m=DEUT):
    return tuple(sum(m[i][j] * c[j] for j in range(3)) for i in range(3))


def stats(ts, floor, tids):
    for tid in tids:
        si, fg, bg = sheet(ts)[1][tid][0]
        gid = fv(fg)
        px, _, _ = rgba(ts, gid)
        op = [p for p in px if p[3] > 127]
        cov = len(op) / len(px)
        L = sum(lum(p) for p in op) / len(op) if op else float('nan')
        semi = sum(1 for p in px if 0 < p[3] <= 127) / len(px)
        fpx, _, _ = rgba(ts, resolve(ts, floor))
        fl = sum(lum(p) for p in fpx) / len(fpx)
        print('%-26s %-26s #%-6d cov=%.2f L=%5.1f floorL=%5.1f dL=%5.1f semi=%.2f' % (
            tid, sheet(ts)[0][si]['file'], gid, cov, L, fl, abs(L - fl), semi))


def diff(ts, pairs):
    for pair in pairs:
        a, b = [resolve(ts, x) for x in pair.split(',')]
        pa, _, _ = rgba(ts, a)
        pb, _, _ = rgba(ts, b)
        n, acc = 0, 0.0
        for x, y in zip(pa, pb):
            ac = (x[3] + y[3]) / 510.0
            d = (abs(x[0] - y[0]) + abs(x[1] - y[1]) + abs(x[2] - y[2]) + abs(x[3] - y[3])) / 4.0
            if d > 8:
                n += 1
            acc += d * ac
        print('%-26s vs %-26s changed=%5.1f%% meanabs=%5.1f' % (
            pair.split(',')[0], pair.split(',')[1], 100.0 * n / len(pa), acc / len(pa)))


def sim(ts, pairs):
    for pair in pairs:
        a, b = pair.split(',')
        pa, _, _ = rgba(ts, resolve(ts, a))
        pb, _, _ = rgba(ts, resolve(ts, b))
        ma = [p[3] > 127 for p in pa]
        mb = [p[3] > 127 for p in pb]
        inter = sum(1 for x, y in zip(ma, mb) if x and y)
        union = sum(1 for x, y in zip(ma, mb) if x or y)
        ca, cb = meancol(ts, a), meancol(ts, b)
        d = math.dist(ca, cb) if ca and cb else float('nan')
        print('%-26s vs %-26s maskIoU=%.2f colourd=%6.1f' % (a, b, inter / union if union else 0, d))


def cvd_report(ts, pairs):
    for pair in pairs:
        a, b = pair.split(',')
        ca, cb = meancol(ts, a), meancol(ts, b)
        if ca is None or cb is None:
            print('%-26s vs %-26s NO DATA' % (a, b))
            continue
        da, db = cvd(ca), cvd(cb)
        d0, d1 = math.dist(ca, cb), math.dist(da, db)
        print('%-24s vs %-24s RGB=%s/%s d=%.1f deut=%.1f (%.0f%% kept)' % (
            a, b, tuple(round(x) for x in ca), tuple(round(x) for x in cb),
            d0, d1, 100 * d1 / d0))


if __name__ == '__main__':
    ts, mode = sys.argv[1], sys.argv[2]
    if mode == 'stats':
        stats(ts, sys.argv[3], sys.argv[4:])
    elif mode == 'diff':
        diff(ts, sys.argv[3:])
    elif mode == 'sim':
        sim(ts, sys.argv[3:])
    elif mode == 'cvd':
        cvd_report(ts, sys.argv[3:])
