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

with sync_playwright() as p:
    browser = p.chromium.launch()
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
print("rendered", [t[0] for t in targets])
