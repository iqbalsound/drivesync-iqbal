"""Generate the SVG / PNG / ICO icons (original Drive-style design, not Google's logo).
Run: python3 tools/make_icons.py   (needs Pillow)"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "drivesync_iqbal" / "assets"
DY = 7   # vertical centring offset in the 100x100 viewBox
POLYS = [
    ("#FFBA00", [(44, 5), (66, 5), (96, 60), (74, 60)]),    # yellow, right edge
    ("#00AC47", [(34, 5), (56, 5), (26, 60), (4, 60)]),     # green, left edge
    ("#2684FC", [(4, 60), (96, 60), (85, 82), (15, 82)]),   # blue, base
]


def svg():
    body = "\n".join(
        f'  <polygon points="{" ".join(f"{x},{y + DY}" for x, y in pts)}" fill="{c}"/>'
        for c, pts in POLYS)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="256" height="256">\n'
            '  <!-- Original Drive-style icon. Replace with official assets if you need Google\'s logo. -->\n'
            f"{body}\n</svg>\n")


def png(size=256, scale=4):
    big = size * scale
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = big / 100
    for color, pts in POLYS:
        d.polygon([(x * k, (y + DY) * k) for x, y in pts], fill=color)
    return im.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "drivesync-iqbal.svg").write_text(svg())
    img = png(256)
    img.save(OUT / "drivesync-iqbal.png")
    img.save(OUT / "drivesync-iqbal.ico",
             sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icons written to", OUT)
