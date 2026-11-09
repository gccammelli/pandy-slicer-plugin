"""Continuous extrusion geometry, independent of path ordering and segmentation.

Target distances are analytic. Adaptive source intervals use the 1-Lipschitz
property of distance along a curve to bound the directed maximum within ERROR_MM.
Exact collinear and co-circular coverage is recognized without sampling.
"""
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
import math
import heapq
import itertools
import re
import zipfile

import numpy as np
from scipy.spatial import cKDTree

TAU = 2 * math.pi
ERROR_MM = 0.0005
COVER_EPS = 1e-9
TOKEN = re.compile(r'([A-Za-z])([+-]?(?:\d+(?:\.\d*)?|\.\d+))')


def intervals(start, sweep):
    if abs(sweep) >= TAU - 1e-12:
        return [(0., TAU)]
    lo = (start + min(0., sweep)) % TAU
    hi = lo + abs(sweep)
    return [(lo, min(hi, TAU))] + ([(0., hi - TAU)] if hi > TAU else [])


def interval_covered(interval, cover):
    lo, hi = interval
    cursor = lo
    for a, b in sorted(cover):
        if b < cursor - COVER_EPS:
            continue
        if a > cursor + COVER_EPS:
            return False
        cursor = max(cursor, b)
        if cursor >= hi - COVER_EPS:
            return True
    return False


@dataclass(frozen=True)
class Primitive:
    start: tuple
    end: tuple
    center: tuple | None = None
    sweep: float = 0.

    @property
    def radius(self):
        return math.dist(self.start, self.center) if self.center else 0.

    @property
    def angle(self):
        return math.atan2(self.start[1] - self.center[1], self.start[0] - self.center[0]) if self.center else 0.

    @property
    def length(self):
        return self.radius * abs(self.sweep) if self.center else math.dist(self.start, self.end)

    def points(self, t):
        t = np.asarray(t)
        if self.center:
            angles = self.angle + self.sweep * t
            return np.asarray(self.center) + self.radius * np.stack((np.cos(angles), np.sin(angles)), axis=-1)
        return np.asarray(self.start) + t[..., None] * (np.asarray(self.end) - self.start)

    @property
    def bounds(self):
        points = [self.start, self.end]
        if self.center:
            for angle in (0., math.pi / 2, math.pi, 3 * math.pi / 2):
                delta = (angle - self.angle) % TAU if self.sweep > 0 else (self.angle - angle) % TAU
                if delta <= abs(self.sweep) + 1e-12:
                    points.append((self.center[0] + self.radius * math.cos(angle), self.center[1] + self.radius * math.sin(angle)))
        p = np.asarray(points)
        return p.min(axis=0), p.max(axis=0)


class PathGeometry:
    def __init__(self, primitives):
        self.primitives = tuple(p for p in primitives if p.length > 1e-12)

    def __len__(self):
        return len(self.primitives)

    @cached_property
    def bounds(self):
        bounds = [p.bounds for p in self.primitives]
        return np.min([b[0] for b in bounds], axis=0), np.max([b[1] for b in bounds], axis=0)

    def min(self, axis=0):
        if axis != 0: raise ValueError('Path bounds support axis=0 only')
        return self.bounds[0]

    def max(self, axis=0):
        if axis != 0: raise ValueError('Path bounds support axis=0 only')
        return self.bounds[1]

    @cached_property
    def coverage(self):
        circles, lines = defaultdict(list), defaultdict(list)
        for p in self.primitives:
            if p.center:
                key = (*p.center, p.radius)
                circles[key].extend(intervals(p.angle, p.sweep))
            else:
                a, b = np.asarray(p.start), np.asarray(p.end)
                u = (b - a) / p.length
                if u[0] < -1e-12 or (abs(u[0]) <= 1e-12 and u[1] < 0):
                    u = -u
                # Quantization indexes possible matches only; coverage is checked geometrically below.
                key = tuple(np.round(np.r_[u, u[0] * a[1] - u[1] * a[0]], 8))
                lines[key].append(p)
        return circles, lines

    def covers(self, source):
        circles, lines = self.coverage
        if source.center:
            cover = circles.get((*source.center, source.radius), [])
            return all(interval_covered(i, cover) for i in intervals(source.angle, source.sweep))
        a, b = np.asarray(source.start), np.asarray(source.end)
        u = (b - a) / source.length
        if u[0] < -1e-12 or (abs(u[0]) <= 1e-12 and u[1] < 0):
            u = -u
        key = tuple(np.round(np.r_[u, u[0] * a[1] - u[1] * a[0]], 8))
        cover = []
        for p in lines.get(key, []):
            ends = np.asarray([p.start, p.end]) - a
            if np.max(np.abs(ends[:, 1] * u[0] - ends[:, 0] * u[1])) <= COVER_EPS:
                projection = ends @ u
                cover.append((float(projection.min()), float(projection.max())))
        own = np.asarray([source.start, source.end]) @ u - a @ u
        return interval_covered((float(own.min()), float(own.max())), cover)

    @cached_property
    def spatial(self):
        return SpatialPaths(self.primitives)

    def close_seams(self, max_gap, min_gap=0.):
        """Diagnostic contour completion: close only long extrusion chains with a bounded end gap."""
        chains, chain = [], []
        for p in self.primitives:
            if chain and math.dist(chain[-1].end, p.start) > COVER_EPS:
                chains.append(chain)
                chain = []
            chain.append(p)
        if chain: chains.append(chain)
        result, gaps = list(self.primitives), []
        for chain in chains:
            gap = math.dist(chain[-1].end, chain[0].start)
            if max(COVER_EPS, min_gap) < gap <= max_gap and sum(p.length for p in chain) >= max(1., 4 * max_gap):
                result.append(Primitive(chain[-1].end, chain[0].start))
                gaps.append(gap)
        return PathGeometry(result), gaps


class SpatialPaths:
    """Bounded nearest-primitive search; midpoint distance alone never determines the result."""
    def __init__(self, primitives):
        pieces = []
        for p in primitives:
            n = max(1, math.ceil(p.length))
            for i in range(n):
                a, b = p.points(np.asarray([i / n, (i + 1) / n]))
                pieces.append(Primitive(tuple(a), tuple(b), p.center, p.sweep / n))
        self.start = np.asarray([p.start for p in pieces])
        self.end = np.asarray([p.end for p in pieces])
        self.center = np.asarray([p.center or p.start for p in pieces])
        self.arc = np.asarray([p.center is not None for p in pieces])
        self.radius = np.asarray([p.radius for p in pieces])
        self.angle = np.asarray([p.angle for p in pieces])
        self.sweep = np.asarray([p.sweep for p in pieces])
        midpoints = np.asarray([p.points(.5) for p in pieces])
        self.bound = max(p.length / 2 for p in pieces)
        self.tree = cKDTree(midpoints)

    def exact_distances(self, points, index):
        a, b = self.start[index], self.end[index]
        q = points[:, None, :]
        ab = b - a
        denominator = np.sum(ab * ab, axis=-1)
        t = np.divide(np.sum((q - a) * ab, axis=-1), denominator, out=np.zeros_like(denominator), where=denominator > 0)
        line = np.linalg.norm(q - (a + np.clip(t, 0, 1)[..., None] * ab), axis=-1)
        delta = q - self.center[index]
        theta = np.arctan2(delta[..., 1], delta[..., 0])
        sweep = self.sweep[index]
        progress = np.where(sweep >= 0, (theta - self.angle[index]) % TAU, (self.angle[index] - theta) % TAU)
        on_arc = progress <= np.abs(sweep) + 1e-12
        radial = np.abs(np.linalg.norm(delta, axis=-1) - self.radius[index])
        endpoints = np.minimum(np.linalg.norm(q - a, axis=-1), np.linalg.norm(q - b, axis=-1))
        return np.where(self.arc[index], np.where(on_arc, radial, endpoints), line)

    def nearest(self, points):
        result = np.empty(len(points))
        # Even an exhaustive k=M fallback has bounded intermediate array sizes.
        batch_size = max(1, min(2048, 131072 // len(self.start)))
        for begin in range(0, len(points), batch_size):
            q = points[begin:begin + batch_size]
            pending = np.arange(len(q))
            k = min(8, len(self.start))
            while len(pending):
                center_d, index = self.tree.query(q[pending], k=list(range(1, k + 1)))
                best = np.full(len(pending), math.inf)
                width = max(1, 131072 // len(pending))
                for column in range(0, index.shape[1], width):
                    best = np.minimum(best, self.exact_distances(q[pending], index[:, column:column + width]).min(axis=1))
                done = np.ones(len(pending), dtype=bool) if k == len(self.start) else center_d[:, -1] > best + self.bound + 1e-12
                result[begin + pending[done]] = best[done]
                pending = pending[~done]
                k = min(k * 2, len(self.start))
        return result


def directed_distance(source, target):
    primitives = [p for p in source.primitives if not target.covers(p)]
    if not primitives:
        return 0.
    endpoints = np.asarray([p.points(np.array([0., 1.])) for p in primitives])
    distances = target.spatial.nearest(endpoints.reshape((-1, 2))).reshape((-1, 2))
    lower = float(distances.max())
    serial = itertools.count()

    def push(queue, p, lo, hi, d0, d1):
        # From either endpoint, distance can increase at most by travelled arc length.
        upper = (d0 + d1 + p.length * (hi - lo)) / 2
        if upper > lower + ERROR_MM:
            heapq.heappush(queue, (-upper, next(serial), p, lo, hi, d0, d1))

    # Resolve one root interval of <=1 mm at a time. A constant-offset path
    # cannot grow a heap proportional to the whole path length / error target.
    for p in primitives:
        count = max(1, math.ceil(p.length))
        for start in range(0, count, 4096):
            times = np.arange(start, min(start + 4096, count) + 1) / count
            ds = target.spatial.nearest(p.points(times))
            lower = max(lower, float(ds.max()))
            for lo, hi, d0, d1 in zip(times[:-1], times[1:], ds[:-1], ds[1:]):
                queue = []
                push(queue, p, lo, hi, d0, d1)
                while queue and -queue[0][0] > lower + ERROR_MM:
                    batch = []
                    while queue and len(batch) < 128 and -queue[0][0] > lower + ERROR_MM:
                        batch.append(heapq.heappop(queue))
                    middle = target.spatial.nearest(np.asarray([p.points((a + b) / 2) for _, _, p, a, b, _, _ in batch]))
                    lower = max(lower, float(middle.max()))
                    for (_, _, p, a, b, da, db), dm in zip(batch, middle):
                        mid = (a + b) / 2
                        push(queue, p, a, mid, da, dm)
                        push(queue, p, mid, b, dm, db)
    return lower + ERROR_MM


def distance(a, b):
    if not len(a) and not len(b):
        return 0.
    if not len(a) or not len(b):
        return math.inf
    return max(directed_distance(a, b), directed_distance(b, a))


def parse(path, group_of=lambda f: f):
    """layer -> feature -> (continuous XY paths, deposited filament mm)."""
    with zipfile.ZipFile(path) as z:
        text = z.read('Metadata/plate_1.gcode').decode(errors='replace')
    layers = defaultdict(lambda: defaultdict(lambda: [[], 0.]))
    layer, feature = -1, ''
    xy = np.zeros(2); offset = np.zeros(2)
    absolute_xy, relative_e, last_e = True, True, 0.
    plane, absolute_center = 'G17', False
    for line in text.splitlines():
        if line.startswith('; CHANGE_LAYER'):
            layer += 1
        elif line.startswith('; FEATURE:'):
            feature = line[10:].strip()
        code = line.split(';', 1)[0].strip()
        words = TOKEN.findall(code)
        if not words:
            continue
        number = float(words[0][1])
        command = words[0][0].upper() + (str(int(number)) if number.is_integer() else words[0][1])
        args = {k.upper(): float(v) for k, v in words[1:]}
        if command == 'G90': absolute_xy = True
        elif command == 'G91': absolute_xy = False
        elif command == 'G90.1': absolute_center = True
        elif command == 'G91.1': absolute_center = False
        elif command in ('G17', 'G18', 'G19'): plane = command
        elif command == 'M83': relative_e = True
        elif command == 'M82': relative_e = False
        elif command == 'G92':
            for i, axis in enumerate(('X', 'Y')):
                if axis in args: offset[i] = xy[i] - args[axis]
            if 'E' in args: last_e = args['E']
        elif command == 'G39' and args.get('S') == 1 and 'E' not in args and all(
                axis not in args or abs(args[axis] + offset[i] - xy[i]) <= .001
                for i, axis in enumerate(('X', 'Y'))):
            # Pinned A1 inspection macro: its optional XY arguments repeat the
            # immediately preceding travel location. Upstream's model G-code
            # processor also treats this as a non-depositing command.
            pass
        elif command in ('G0', 'G1', 'G2', 'G3'):
            end = xy.copy()
            for i, axis in enumerate(('X', 'Y')):
                if axis in args: end[i] = args[axis] + offset[i] if absolute_xy else xy[i] + args[axis]
            e = args.get('E', 0.) if relative_e else args.get('E', last_e) - last_e
            if 'E' in args: last_e = last_e + e if relative_e else args['E']
            arc = command in ('G2', 'G3') and ('I' in args or 'J' in args)
            if layer >= 0 and e > 0 and command in ('G2', 'G3'):
                if not arc or plane != 'G17' or absolute_center:
                    raise ValueError('Only XY-plane extruding arcs with relative I/J centres are supported')
            if layer >= 0 and e > 0 and command != 'G0' and (np.any(end != xy) or arc):
                slot = layers[layer][group_of(feature)]
                slot[1] += e
                if command in ('G2', 'G3'):
                    if not arc: raise ValueError('Unsupported extruding arc without I/J centre')
                    center = xy + (args.get('I', 0.), args.get('J', 0.))
                    a0 = math.atan2(xy[1] - center[1], xy[0] - center[0])
                    a1 = math.atan2(end[1] - center[1], end[0] - center[0])
                    sweep = (a1 - a0) % TAU if command == 'G3' else -((a0 - a1) % TAU)
                    if abs(sweep) < 1e-12: sweep = TAU if command == 'G3' else -TAU
                    radius = np.linalg.norm(xy - center)
                    if radius <= 1e-12: raise ValueError('Extruding arc has zero radius')
                    arc_end = center + radius * np.asarray([math.cos(a0 + sweep), math.sin(a0 + sweep)])
                    slot[0].append(Primitive(tuple(xy), tuple(arc_end), tuple(center), sweep))
                    # G-code rounds coordinates; retain the specified endpoint too.
                    if np.linalg.norm(arc_end - end) > 1e-12:
                        slot[0].append(Primitive(tuple(arc_end), tuple(end)))
                else:
                    slot[0].append(Primitive(tuple(xy), tuple(end)))
            xy = end
        elif layer >= 0 and (command[0] not in ('M', 'T')) and (
                command[0] in 'XYZE' or any(axis in args for axis in ('X', 'Y', 'E'))):
            raise ValueError(f'Unsupported motion syntax: {code[:120]}')
    return {l: {f: (PathGeometry(p), e) for f, (p, e) in fs.items()} for l, fs in layers.items()}
