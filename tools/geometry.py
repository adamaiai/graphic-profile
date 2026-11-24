"""
Geometry for the adamai and cosa logos (release 1.0).

Every logo is constructed, not drawn: circles, arcs and straight strokes of one
stroke width are thickened with Shapely and merged into a single outline.
All measurements are in design units; the SVG viewBox uses the same units.

    stroke width        48   (2 * W)
    x-height            288  (2 * R + 2 * W)  — height of a, o, c, s, m
    round-letter radius 120  (centre line)

Change a constant below and run `python tools/build.py` to regenerate every asset.
"""

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Point, box
from shapely.ops import substring, unary_union

# ---------------------------------------------------------------------------
# Shared construction constants
W = 24.0  # half stroke width (stroke = 48)
R = 120.0  # radius of round letters, measured on the stroke centre line
C = np.array([500.0, 500.0])
TOP, BASE = C[1] - R, C[1] + R  # centre-line top / bottom of the round letters

# adamai
GAP = 11.0  # weave gap where the infinity strands cross
DX = 150.0  # distance from the infinity crossing to each loop centre
ASC = 24.0  # how far the d stem and the i rise above the x-height
RA = 84.0  # arch radius of the m
G_ROUND = 48.0  # space before a round letter (a)
G_STRAIGHT = 54.0  # space before a straight letter (m, i)
I_GAP = 14.0  # gap between the i stem and its square dot

# cosa
C_OPEN = 42.0  # opening of the c: angle (deg) of each end from the horizontal
S_HALF = 104.0  # half-width of the s bowls
S_TENSION = 70.0  # tension of the s spine
S_END = 0.0  # s ends cut straight across at the widest point of each bowl (deg offset)
CELL = 340.0  # equal letter cell width for cosa


def _arc(c, rad, a0, a1, n=240):
    a = np.linspace(a0, a1, n)
    return np.c_[c[0] + rad * np.cos(a), c[1] + rad * np.sin(a)]


def _ring(cx):
    return (
        Point(cx, C[1])
        .buffer(R + W, resolution=64)
        .difference(Point(cx, C[1]).buffer(R - W, resolution=64))
    )


def _letter_a(xl):
    cx = xl + W + R
    stem = box(cx + R - W, C[1], cx + R + W, BASE + W)  # stem on the lower half only
    return unary_union([_ring(cx), stem]), cx + R + W


# ---------------------------------------------------------------------------
# adamai
def _infinity():
    """The woven infinity whose left loop is the a and right loop the bowl of the d."""
    c_right, c_left = C + [DX, 0], C - [DX, 0]
    phi = np.arccos(R / DX)  # tangent angle: crossing strands meet the circles smoothly
    inf = LineString(
        np.vstack(
            [
                C,
                _arc(c_right, R, np.pi + phi, 3 * np.pi - phi),
                C,
                _arc(c_left, R, -phi, phi - 2 * np.pi),
                C,
            ]
        )
    )
    n = inf.length
    over = substring(inf, n / 2 - 90, n / 2 + 90)  # the strand that passes on top
    gap = over.buffer(W + GAP, cap_style=2).intersection(Point(C).buffer(W * 2.8))
    mark = unary_union(
        [inf.buffer(W, resolution=64).difference(gap), over.buffer(W, cap_style=2)]
    )
    stem_x = c_right[0] + R
    d_stem = box(stem_x - W, TOP - W - ASC, stem_x + W, BASE + W)
    return [mark, d_stem], stem_x + W


def adamai_mark():
    """The 'ad' mark on its own: the infinity with the d stem."""
    parts, _ = _infinity()
    return unary_union(parts).simplify(0.05)


def adamai():
    """Return (letters, dot) for the adamai wordmark."""
    parts, x = _infinity()

    def letter_m(xl):
        x0, cy = xl + W, TOP + RA
        arches = []
        for k in range(2):
            xa = x0 + 2 * RA * k
            line = LineString(
                np.vstack(
                    [
                        [xa, BASE + W],
                        [xa, cy],
                        _arc((xa + RA, cy), RA, np.pi, 2 * np.pi),
                        [xa + 2 * RA, BASE + W],
                    ]
                )
            )
            arches.append(line.buffer(W, cap_style=2, join_style=1, resolution=48))
        return unary_union(arches), x0 + 4 * RA + W

    dot = []

    def letter_i(xl):
        xc = xl + W
        dot.append(
            box(xc - W, TOP - W - ASC, xc + W, TOP + W - ASC)
        )  # square dot, top = d top
        return box(xc - W, TOP + W - ASC + I_GAP, xc + W, BASE + W), xc + W

    for ch, spacing in [
        ("a", G_ROUND),
        ("m", G_STRAIGHT),
        ("a", G_ROUND),
        ("i", G_STRAIGHT),
    ]:
        shape, x = {"a": _letter_a, "m": letter_m, "i": letter_i}[ch](x + spacing)
        parts.append(shape)
    return unary_union(parts).simplify(0.05), dot[0].simplify(0.05)


# ---------------------------------------------------------------------------
# cosa
def _letter_c(xl):
    cx = xl + W + R
    t = np.radians(C_OPEN)
    line = LineString(_arc((cx, C[1]), R, -t, -2 * np.pi + t))  # open on the right
    return line.buffer(W, cap_style=2, resolution=64), cx + R + W


def _letter_o(xl):
    cx = xl + W + R
    return _ring(cx), cx + R + W


def _letter_s(xl, half=S_HALF):
    """Point-symmetric s: two half-ellipse bowls joined by a smooth S-curve spine."""
    a, v = half, (BASE - TOP) / 4
    cx = xl + W + a
    ct, cb = np.array([cx, TOP + v]), np.array([cx, BASE - v])

    def ell(c, a0, a1):
        t = np.linspace(a0, a1, 200)
        return np.c_[c[0] + a * np.cos(t), c[1] + v * np.sin(t)]

    t = np.radians(S_END)
    dep = max(-t, 0.0)
    ext = dep + (np.radians(25) if dep > 0 else 0)
    upper = ell(ct, ext, -np.pi)
    p0, p3 = upper[-1], np.array([cx + a, cb[1]])
    p1, p2 = p0 + [0, S_TENSION], p3 - [0, S_TENSION]
    u = np.linspace(0, 1, 200)[:, None]
    spine = (
        (1 - u) ** 3 * p0
        + 3 * (1 - u) ** 2 * u * p1
        + 3 * (1 - u) * u**2 * p2
        + u**3 * p3
    )
    lower = ell(cb, 0, np.pi + ext)
    shape = LineString(np.vstack([upper, spine[1:], lower[1:]])).buffer(
        W, cap_style=2, resolution=64
    )
    yt = ct[1] - v * np.sin(t)
    if t > 0:
        cut = box(cx, yt, cx + a + W + 2, ct[1] + 1)
    else:
        tip = np.array([cx + a * np.cos(dep), yt])
        cut = box(cx, yt, cx + a + W + 2, yt + 200).intersection(
            Point(*tip).buffer(W * 2.4)
        )
        cut = cut.difference(LineString(spine).buffer(W + 0.5, resolution=64))
    shape = shape.difference(cut).difference(
        affinity.rotate(cut, 180, origin=(cx, C[1]))
    )
    return shape, cx + a + W


def cosa():
    """The cosa wordmark: every letter is centred in an equal cell."""
    glyphs = [
        _letter_c(0)[0],
        _letter_o(0)[0],
        _letter_s(0)[0],
        _letter_a(0)[0],
    ]
    parts = []
    for i, g in enumerate(glyphs):
        xmin, _, xmax, _ = g.bounds
        parts.append(
            affinity.translate(
                g, C[0] + i * CELL + CELL / 2 - (xmin + xmax) / 2, 0
            )
        )
    return unary_union(parts).simplify(0.05)
