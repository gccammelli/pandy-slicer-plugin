"""Procedurally generated test models, written as plain 3MF projects (geometry and placement only, like a model
dropped on the plate in Bambu Studio). Generated rather than downloaded, so the corpus is exact, redistributable and
reproducible. Each one exercises different slicer code: walls, infill, supports, bridges, seams, thin features."""
import math
import zipfile
from pathlib import Path


class Mesh:
    def __init__(self):
        self.v, self.t = [], []

    def add(self, other, dx=0.0, dy=0.0, dz=0.0):
        base = len(self.v)
        self.v += [(x + dx, y + dy, z + dz) for x, y, z in other.v]
        self.t += [(a + base, b + base, c + base) for a, b, c in other.t]
        return self


def box(sx, sy, sz):
    m = Mesh()
    m.v = [(x, y, z) for z in (0, sz) for y in (0, sy) for x in (0, sx)]
    m.t = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 5), (0, 5, 4), (2, 6, 7), (2, 7, 3), (0, 4, 6), (0, 6, 2), (1, 3, 7), (1, 7, 5)]
    return m


def lathe(profile, segments=64):
    """Solid of revolution around Z from (radius, z) points, bottom to top; radius 0 ends close the solid."""
    m = Mesh()
    rings = []
    for r, z in profile:
        if r == 0:
            rings.append([len(m.v)])
            m.v.append((0.0, 0.0, z))
        else:
            rings.append(list(range(len(m.v), len(m.v) + segments)))
            m.v += [(r * math.cos(2 * math.pi * i / segments), r * math.sin(2 * math.pi * i / segments), z) for i in range(segments)]
    for a, b in zip(rings, rings[1:]):
        for i in range(segments):
            j = (i + 1) % segments
            if len(a) == 1:
                m.t.append((a[0], b[j], b[i]))
            elif len(b) == 1:
                m.t.append((a[i], a[j], b[0]))
            else:
                m.t += [(a[i], a[j], b[j]), (a[i], b[j], b[i])]
    return m


def cylinder(r, h, segments=64):
    return lathe([(0, 0), (r, 0), (r, h), (0, h)], segments)


def sphere(r, rings=32, segments=64):
    pts = [(0, 0)] + [(r * math.sin(math.pi * i / rings), r - r * math.cos(math.pi * i / rings)) for i in range(1, rings)] + [(0, 2 * r)]
    return lathe(pts, segments)


def tube(r_out, r_in, h, segments=64):
    """A hollow cylinder (a hole through the middle)."""
    m = Mesh()
    for k, (r, z) in enumerate([(r_out, 0), (r_out, h), (r_in, h), (r_in, 0)]):
        m.v += [(r * math.cos(2 * math.pi * i / segments), r * math.sin(2 * math.pi * i / segments), z) for i in range(segments)]
    for k in range(4):
        a, b = k * segments, ((k + 1) % 4) * segments
        for i in range(segments):
            j = (i + 1) % segments
            m.t += [(a + i, a + j, b + j), (a + i, b + j, b + i)]
    return m


def torus(R, r, seg=64, sides=24):
    m = Mesh()
    for i in range(seg):
        for j in range(sides):
            u, v = 2 * math.pi * i / seg, 2 * math.pi * j / sides
            m.v.append(((R + r * math.cos(v)) * math.cos(u), (R + r * math.cos(v)) * math.sin(u), r + r * math.sin(v)))
    for i in range(seg):
        for j in range(sides):
            a, b = i * sides + j, ((i + 1) % seg) * sides + j
            c, d = ((i + 1) % seg) * sides + (j + 1) % sides, i * sides + (j + 1) % sides
            m.t += [(a, b, c), (a, c, d)]
    return m


def extrude(poly, h):
    """A prism from a simple counter-clockwise polygon, triangulated by ear clipping."""
    n = len(poly)
    m = Mesh()
    m.v = [(x, y, 0.0) for x, y in poly] + [(x, y, h) for x, y in poly]
    idx = list(range(n))

    def is_ear(i0, i1, i2):
        (ax, ay), (bx, by), (cx, cy) = poly[i0], poly[i1], poly[i2]
        if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) <= 0:
            return False
        for k in idx:
            if k in (i0, i1, i2):
                continue
            px, py = poly[k]
            d1 = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
            d2 = (cx - bx) * (py - by) - (cy - by) * (px - bx)
            d3 = (ax - cx) * (py - cy) - (ay - cy) * (px - cx)
            if d1 >= 0 and d2 >= 0 and d3 >= 0:
                return False
        return True

    while len(idx) > 3:
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            if is_ear(i0, i1, i2):
                m.t += [(i0, i2, i1), (i0 + n, i1 + n, i2 + n)]
                idx.pop(k)
                break
        else:
            raise ValueError("polygon is not simple")
    m.t += [(idx[0], idx[2], idx[1]), (idx[0] + n, idx[1] + n, idx[2] + n)]
    for i in range(n):
        j = (i + 1) % n
        m.t += [(i, j, j + n), (i, j + n, i + n)]
    return m


def gear(teeth=17, module=2.0, h=8.0):
    r_pitch = module * teeth / 2
    pts = []
    for i in range(teeth * 4):
        a = 2 * math.pi * i / (teeth * 4)
        r = r_pitch + (module if i % 4 in (1, 2) else -1.25 * module)
        pts.append((r * math.cos(a), r * math.sin(a)))
    return extrude(pts, h)


def overhang_wedge(angle_deg, w=10.0, h=15.0):
    run = h * math.tan(math.radians(angle_deg))
    m = extrude([(0, 0), (6, 0), (6 + run, h), (run, h)], w)
    # extrude() builds along Z; turn the profile upright (XZ plane) by swapping Y and Z.
    m.v = [(x, z, y) for x, y, z in m.v]
    m.t = [(a, c, b) for a, b, c in m.t]
    return m


def thin_features():
    m = Mesh()
    for i, t in enumerate([0.4, 0.6, 0.8, 1.2, 2.0]):
        m.add(box(t, 15, 12), dx=i * 4)
    m.add(box(22, 15, 1.0), dz=0)
    return m


MODELS = {
    "cube": lambda: box(20, 20, 20),
    "cylinder": lambda: cylinder(12, 25),
    "tube": lambda: tube(15, 9, 18),
    "sphere": lambda: sphere(14),
    "torus": lambda: torus(16, 5),
    "gear": lambda: gear(),
    "bridge": lambda: Mesh().add(box(4, 12, 20)).add(box(4, 12, 20), dx=36).add(box(40, 12, 4), dz=20),
    "overhangs": lambda: Mesh().add(overhang_wedge(45)).add(overhang_wedge(60), dy=14).add(overhang_wedge(75), dy=28),
    "thin": thin_features,
    "tower": lambda: box(8, 8, 80),
}


def write_3mf(path: Path, objects):
    """objects: [(name, Mesh, (x, y, z) placement of the mesh's origin)]. Units mm, Bambu-style plain project."""
    res, build = [], []
    for i, (name, mesh, (px, py, pz)) in enumerate(objects, start=1):
        verts = "".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in mesh.v)
        tris = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in mesh.t)
        res.append(f'<object id="{i}" name="{name}" type="model"><mesh><vertices>{verts}</vertices><triangles>{tris}</triangles></mesh></object>')
        # All twelve numbers in fixed notation, as the app writes any placement (rotations included).
        t = [1, 0, 0, 0, 1, 0, 0, 0, 1, px, py, pz]
        build.append(f'<item objectid="{i}" transform="{" ".join(f"{v:.6f}" for v in t)}" printable="1"/>')
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<resources>{"".join(res)}</resources><build>{"".join(build)}</build></model>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr("3D/3dmodel.model", model)


def centred(mesh, cx, cy):
    """Placement that puts the mesh's footprint centre at (cx, cy) and its bottom on the bed."""
    xs, ys, zs = [p[0] for p in mesh.v], [p[1] for p in mesh.v], [p[2] for p in mesh.v]
    return (cx - (min(xs) + max(xs)) / 2, cy - (min(ys) + max(ys)) / 2, -min(zs))
