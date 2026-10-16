"""Render PWA icons from assets/icon.svg (needs: pip install playwright && playwright install chromium-headless-shell).

Usage: python assets/render-icons.py   (from frontend/)
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

svg = Path("assets/icon.svg").read_text()
out = Path("static/icons")
out.mkdir(parents=True, exist_ok=True)

# (file, size, inner scale): maskable icons keep the motif inside the 80 % safe zone
targets = [
    ("icon-192.png", 192, 1.0, 0.22),
    ("icon-512.png", 512, 1.0, 0.22),
    ("maskable-512.png", 512, 0.8, 0.0),
    ("apple-touch-icon.png", 180, 1.0, 0.0),
]

# App icon shortcuts (manifest "shortcuts"): Lucide glyphs used in the UI, white on the brand gradient
GLYPHS = {
    "shortcut-home.png": [
        "M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8",
        "M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    ],
    "shortcut-office.png": [
        "M10 12h4",
        "M10 8h4",
        "M14 21v-3a2 2 0 0 0-4 0v3",
        "M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2",
        "M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16",
    ],
    "shortcut-stop.png": [
        "M4 22V4a1 1 0 0 1 .4-.8A6 6 0 0 1 8 2c3 0 5 2 7.333 2q2 0 3.067-.8A1 1 0 0 1 20 4v10a1 1 0 0 1-.4.8"
        "A6 6 0 0 1 16 16c-3 0-5-2-8-2a6 6 0 0 0-4 1.528",
    ],
}


def glyph_svg(paths: list[str]) -> str:
    strokes = "".join(f'<path d="{d}"/>' for d in paths)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">'
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#14b8a6"/><stop offset="1" stop-color="#0f766e"/></linearGradient></defs>'
        '<circle cx="48" cy="48" r="48" fill="url(#bg)"/>'
        '<g transform="translate(24 24) scale(2)" fill="none" stroke="#fff" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{strokes}</g></svg>'
    )


with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, paths in GLYPHS.items():
        page = browser.new_page(viewport={"width": 96, "height": 96})
        page.set_content(f'<html><body style="margin:0;background:transparent">{glyph_svg(paths)}</body></html>')
        page.screenshot(path=str(out / name), omit_background=True)
        page.close()
    for name, size, scale, radius in targets:
        page = browser.new_page(viewport={"width": size, "height": size})
        icon = svg.replace("<svg ", '<svg width="100%" height="100%" ', 1)
        if scale != 1.0:  # shrink only the motif, keep the full-bleed background
            offset = 256 * (1 - scale)
            icon = icon.replace('<g id="motif">', f'<g id="motif" transform="translate({offset} {offset}) scale({scale})">')
        html = f"""<html><body style="margin:0;background:transparent">
        <div style="width:{size}px;height:{size}px;border-radius:{radius * size}px;overflow:hidden">{icon}</div>
        </body></html>"""
        page.set_content(html)
        page.screenshot(path=str(out / name), omit_background=True)
        page.close()
    browser.close()
print("rendered", [t[0] for t in targets] + list(GLYPHS))
