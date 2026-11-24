"""
Build every asset of the adamai graphical profile from tools/geometry.py.

    pip install -r requirements.txt
    python tools/build.py

Writes logos (SVG + PNG), app icons and favicons, the colour palette and design
tokens, and the documentation images. Safe to re-run: output is deterministic.
"""

import io
import json
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont
from shapely import affinity

import geometry as g

ROOT = Path(__file__).resolve().parent.parent
VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Colours (single source of truth — also written to colors/*.json|css|scss)
PALETTE = [
    # key, name, hex, role
    ("ink", "Ink", "#000000", "Logos and text on light backgrounds"),
    ("night", "Night", "#111111", "Dark backgrounds, app icon"),
    ("fog", "Fog", "#F4F4F2", "Light panels and tiles"),
    ("paper", "Paper", "#FFFFFF", "Logos and text on dark backgrounds"),
    (
        "signal-yellow",
        "Signal Yellow",
        "#F9A800",
        "Accent only: the i-dot, highlights, status",
    ),
]
HEX = {k: h for k, _, h, _ in PALETTE}
PNG_WIDTHS = (512, 1024, 2048)
ICON_SIZES = (16, 32, 48, 64, 128, 180, 192, 256, 512)


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def cmyk(h):
    r, gg, b = (c / 255 for c in rgb(h))
    k = 1 - max(r, gg, b)
    if k >= 1:
        return (0, 0, 0, 100)
    return tuple(
        round(100 * v)
        for v in (
            (1 - r - k) / (1 - k),
            (1 - gg - k) / (1 - k),
            (1 - b - k) / (1 - k),
            k,
        )
    )


def luminance(h):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, gg, b = (lin(c) for c in rgb(h))
    return 0.2126 * r + 0.7152 * gg + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ---------------------------------------------------------------------------
# SVG writing
def _path(geom):
    def ring(rr):
        return (
            "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in list(rr.coords)[:-1]) + "Z"
        )

    polys = geom.geoms if hasattr(geom, "geoms") else [geom]
    return " ".join(
        ring(p.exterior) + "".join(ring(i) for i in p.interiors) for p in polys
    )


def svg(layers, title, pad=10, bounds=None, background=None):
    """layers: list of (geometry, fill). Returns SVG text."""
    if bounds is None:
        xs = [layer[0].bounds for layer in layers]
        bounds = (
            min(b[0] for b in xs) - pad,
            min(b[1] for b in xs) - pad,
            max(b[2] for b in xs) + pad,
            max(b[3] for b in xs) + pad,
        )
    x0, y0, x1, y1 = bounds
    vb = f"{x0:.0f} {y0:.0f} {x1 - x0:.0f} {y1 - y0:.0f}"
    body = ""
    if background:
        rx = background[1]
        body += f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{x1 - x0:.0f}" height="{y1 - y0:.0f}" rx="{rx:.0f}" fill="{background[0]}"/>'
    for geom, fill in layers:
        body += f'<path fill="{fill}" fill-rule="evenodd" d="{_path(geom)}"/>'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-label="{title}">'
        f"<title>{title}</title>{body}</svg>\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def png_from_svg(svg_text, width=None, height=None, background=None):
    kw = {"output_width": width} if width else {"output_height": height}
    data = cairosvg.svg2png(
        bytestring=svg_text.encode(), background_color=background, **kw
    )
    return Image.open(io.BytesIO(data)).convert("RGBA")


def export_logo(folder, name, svg_text):
    write(ROOT / folder / "svg" / f"{name}.svg", svg_text)
    for w in PNG_WIDTHS:
        out = ROOT / folder / "png" / f"{name}-{w}w.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        png_from_svg(svg_text, width=w).save(out, optimize=True)


# ---------------------------------------------------------------------------
def font(size, weight="Regular"):
    # Use Pillow's bundled font so generated documentation images are stable
    # across Windows, macOS and Linux CI runners.
    return ImageFont.load_default(size)


def build_logos():
    letters, dot = g.adamai()
    ink, paper, yellow = HEX["ink"], HEX["paper"], HEX["signal-yellow"]
    variants = {
        "adamai-primary": (ink, yellow),
        "adamai-reversed": (paper, yellow),
        "adamai-black": (ink, ink),
        "adamai-white": (paper, paper),
    }
    out = {}
    for name, (fg, dc) in variants.items():
        out[name] = svg([(letters, fg), (dot, dc)], "adamai")
        export_logo("logos/adamai", name, out[name])

    mark = g.adamai_mark()
    for name, fg in (("adamai-mark-black", ink), ("adamai-mark-white", paper)):
        out[name] = svg([(mark, fg)], "adamai")
        export_logo("logos/adamai-mark", name, out[name])

    geom = g.cosa()
    for colour, fg in (("black", ink), ("white", paper)):
        name = f"cosa-{colour}"
        out[name] = svg([(geom, fg)], "cosa")
        export_logo("logos/cosa", name, out[name])
    return out, letters, dot, mark


def build_icons(mark):
    """Square app icons and favicons from the 'ad' mark."""
    b = mark.bounds
    side = (b[2] - b[0]) * 1.32  # mark fills ~76 % of the icon width
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    box_ = (cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2)
    radius = side * 0.22
    variants = {
        "app-icon-dark": svg(
            [(mark, HEX["paper"])],
            "adamai",
            bounds=box_,
            background=(HEX["night"], radius),
        ),
        "app-icon-light": svg(
            [(mark, HEX["ink"])],
            "adamai",
            bounds=box_,
            background=(HEX["paper"], radius),
        ),
    }
    folder = ROOT / "logos/adamai-mark/icons"
    for name, text in variants.items():
        write(folder / f"{name}.svg", text)
        for s in ICON_SIZES:
            png_from_svg(text, width=s).save(folder / f"{name}-{s}.png", optimize=True)
    # adaptive favicon: black mark, white in dark mode
    fav = svg([(mark, HEX["ink"])], "adamai", bounds=box_).replace(
        "<title>",
        "<style>path{fill:#000}@media (prefers-color-scheme:dark){path{fill:#fff}}</style><title>",
    )
    write(folder / "favicon.svg", fav)
    ico = png_from_svg(variants["app-icon-dark"], width=256)
    ico.save(folder / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    png_from_svg(variants["app-icon-dark"], width=180).save(
        folder / "apple-touch-icon.png", optimize=True
    )


def build_colors():
    folder = ROOT / "colors"
    tokens = {
        "color": {
            k: {"$type": "color", "$value": h, "$description": role}
            for k, _, h, role in PALETTE
        }
    }
    write(folder / "colors.json", json.dumps(tokens, indent=2) + "\n")
    write(
        folder / "colors.css",
        ":root {\n"
        + "".join(f"  --color-{k}: {h}; /* {role} */\n" for k, _, h, role in PALETTE)
        + "}\n",
    )
    write(
        folder / "colors.scss",
        "".join(f"$color-{k}: {h}; // {role}\n" for k, _, h, role in PALETTE),
    )

    # palette image
    S = 2
    W_, H_ = 1600 * S, 980 * S
    im = Image.new("RGB", (W_, H_), "white")
    d = ImageDraw.Draw(im)
    d.text(
        (80 * S, 70 * S),
        "adamai - colour palette",
        fill="#000",
        font=font(44 * S, "SemiBold"),
    )
    d.text(
        (80 * S, 135 * S),
        f"Graphical profile {VERSION}",
        fill="#777",
        font=font(22 * S),
    )

    # hero: Signal Yellow
    y0 = 210 * S
    d.rounded_rectangle(
        (80 * S, y0, 1520 * S, y0 + 300 * S), radius=24 * S, fill=HEX["signal-yellow"]
    )
    d.text(
        (120 * S, y0 + 40 * S),
        "Signal Yellow",
        fill="#000",
        font=font(40 * S, "SemiBold"),
    )
    r_, g_, b_ = rgb(HEX["signal-yellow"])
    c, m, y, k = cmyk(HEX["signal-yellow"])
    lines = [
        "HEX   #F9A800",
        f"RGB   {r_}  {g_}  {b_}",
        f"CMYK  {c}  {m}  {y}  {k}   (approx.)",
    ]
    for i, t in enumerate(lines):
        d.text(
            (120 * S, y0 + (110 + i * 48) * S),
            t,
            fill="#000",
            font=font(30 * S, "Medium"),
        )
    d.text(
        (900 * S, y0 + 120 * S),
        "Accent only - never for letters.\nUse it for the i-dot, highlights\nand status. Max ~5 % of a surface.",
        fill="#000",
        font=font(24 * S),
        spacing=10 * S,
    )

    # neutrals
    y1 = y0 + 350 * S
    neutrals = [p for p in PALETTE if p[0] != "signal-yellow"]
    cw = (1440 - 3 * 30) / 4
    for i, (key, name, h, role) in enumerate(neutrals):
        x = (80 + i * (cw + 30)) * S
        d.rounded_rectangle(
            (x, y1, x + cw * S, y1 + 200 * S),
            radius=20 * S,
            fill=h,
            outline="#DDDDDD" if key in ("paper", "fog") else None,
            width=2 * S,
        )
        d.text((x, y1 + 220 * S), name, fill="#000", font=font(26 * S, "SemiBold"))
        rr, gg, bb = rgb(h)
        d.text(
            (x, y1 + 262 * S),
            f"{h}\nRGB {rr} {gg} {bb}",
            fill="#555",
            font=font(20 * S),
            spacing=6 * S,
        )
        d.text((x, y1 + 330 * S), role, fill="#888", font=font(16 * S))
    im.save(folder / "palette.png", optimize=True)


def build_docs(out, letters, dot, mark):
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)

    def tile(svg_text, bg, h, w=None):
        logo = png_from_svg(svg_text, height=h)
        if w and logo.width > w - 120:  # keep wide logos inside the tile
            logo = png_from_svg(svg_text, width=w - 120)
        w = w or logo.width + 160
        t = Image.new("RGBA", (w, h + 160), bg)
        t.alpha_composite(logo, ((w - logo.width) // 2, 80 + (h - logo.height) // 2))
        return t

    # overview
    rows = [
        ("adamai-primary", "adamai-reversed"),
        ("adamai-mark-black", "adamai-mark-white"),
        ("cosa-black", "cosa-white"),
    ]
    tiles = [
        (tile(out[a], HEX["paper"], 140, 1100), tile(out[b], HEX["night"], 140, 1100))
        for a, b in rows
    ]
    ov = Image.new("RGBA", (2 * 1100, sum(t[0].height for t in tiles)), "white")
    y = 0
    for lt, dk in tiles:
        ov.alpha_composite(lt, (0, y))
        ov.alpha_composite(dk, (1100, y))
        y += lt.height
    ov.convert("RGB").save(docs / "overview.png", optimize=True)

    # clear space: X = half the x-height
    X = g.R + g.W  # half of the 288 x-height
    for name, layers in (
        ("adamai", [(letters, HEX["ink"]), (dot, HEX["signal-yellow"])]),
        ("cosa", [(g.cosa(), HEX["ink"])]),
    ):
        b = [layer[0].bounds for layer in layers]
        x0, y0 = min(v[0] for v in b), min(v[1] for v in b)
        x1, y1 = max(v[2] for v in b), max(v[3] for v in b)
        pad = X * 1.6
        bounds = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
        txt = svg(layers, name, bounds=bounds)
        guide = (
            f'<rect x="{x0 - X:.0f}" y="{y0 - X:.0f}" width="{x1 - x0 + 2 * X:.0f}" height="{y1 - y0 + 2 * X:.0f}" '
            f'fill="none" stroke="#F9A800" stroke-width="4" stroke-dasharray="16 10"/>'
            f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{x1 - x0:.0f}" height="{y1 - y0:.0f}" fill="none" stroke="#BBBBBB" stroke-width="2"/>'
        )
        for gx, gy in ((x0 - X, y0 - X), (x1, y1)):
            guide += (
                f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{X:.0f}" height="{X:.0f}" fill="#F9A800" fill-opacity="0.18"/>'
                f'<text x="{gx + X / 2:.0f}" y="{gy + X / 2 + 22:.0f}" font-family="Inter, Arial, sans-serif" '
                f'font-size="64" text-anchor="middle" fill="#B07600">X</text>'
            )
        txt = txt.replace("</svg>", guide + "</svg>")
        png_from_svg(txt, width=1600, background="white").convert("RGB").save(
            docs / f"clear-space-{name}.png", optimize=True
        )

    # misuse examples
    bad = []
    lb = letters.bounds
    org = ((lb[0] + lb[2]) / 2, (lb[1] + lb[3]) / 2)
    bad.append(
        (
            "Don't stretch or squash",
            svg(
                [
                    (affinity.scale(letters, 1.0, 0.6, origin=org), HEX["ink"]),
                    (affinity.scale(dot, 1.0, 0.6, origin=org), HEX["signal-yellow"]),
                ],
                "x",
            ),
            HEX["paper"],
        )
    )
    bad.append(
        (
            "Don't colour the letters yellow",
            svg([(letters, HEX["signal-yellow"]), (dot, HEX["ink"])], "x"),
            HEX["paper"],
        )
    )
    rot_c = letters.centroid
    bad.append(
        (
            "Don't rotate",
            svg(
                [
                    (affinity.rotate(letters, -12, origin=rot_c), HEX["ink"]),
                    (affinity.rotate(dot, -12, origin=rot_c), HEX["signal-yellow"]),
                ],
                "x",
            ),
            HEX["paper"],
        )
    )
    bad.append(("Don't use low contrast", out["adamai-black"], HEX["night"]))
    cells = []
    for label, text, bg in bad:
        t = tile(text, bg, 110, 760).convert("RGB")
        dd = ImageDraw.Draw(t)
        dd.line((24, 24, 64, 64), fill="#D0021B", width=8)
        dd.line((64, 24, 24, 64), fill="#D0021B", width=8)
        cell = Image.new("RGB", (760, t.height + 64), "white")
        cell.paste(t, (0, 0))
        ImageDraw.Draw(cell).text((0, t.height + 16), label, fill="#333", font=font(28))
        cells.append(cell)
    sheet = Image.new("RGB", (2 * 760 + 40, 2 * cells[0].height + 40), "white")
    for i, c in enumerate(cells):
        sheet.paste(c, ((i % 2) * 800, (i // 2) * (c.height + 40)))
    sheet.save(docs / "misuse.png", optimize=True)

    # minimum sizes at real pixel size
    ms = Image.new("RGB", (900, 200), "white")
    dd = ImageDraw.Draw(ms)
    x = 30
    for label, text, w in (
        ("adamai 96 px", out["adamai-primary"], 96),
        ("cosa 72 px", out["cosa-black"], 72),
        ("mark 24 px", out["adamai-mark-black"], 24),
    ):
        logo = png_from_svg(text, width=w)
        ms.paste(logo, (x, 60), logo)
        dd.text((x, 120), label, fill="#555", font=font(22))
        x += max(w, 160) + 120
    ms.save(docs / "minimum-size.png", optimize=True)


def main():
    out, letters, dot, mark = build_logos()
    build_icons(mark)
    build_colors()
    build_docs(out, letters, dot, mark)
    print(
        "contrast Signal Yellow on Paper: %.2f:1, on Night: %.2f:1, on Ink: %.2f:1"
        % (
            contrast(HEX["signal-yellow"], HEX["paper"]),
            contrast(HEX["signal-yellow"], HEX["night"]),
            contrast(HEX["signal-yellow"], HEX["ink"]),
        )
    )
    print("built graphical profile", VERSION, "in", ROOT)


if __name__ == "__main__":
    main()
