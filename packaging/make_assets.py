"""Render this application's original vector mark into Windows icon sizes."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "desktop-assets"

def main():
    TARGET.mkdir(exist_ok=True)
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
<rect x="8" y="8" width="240" height="240" rx="55" fill="#101a2e"/>
<path d="M151 71H111C79 71 58 95 58 128s21 57 53 57h40" fill="none" stroke="#e9f3ff" stroke-width="24" stroke-linecap="round"/>
<path d="M141 128h44m0-43v86" fill="none" stroke="#53dccb" stroke-width="12" stroke-linecap="round"/>
<circle cx="185" cy="85" r="15" fill="#53dccb"/><circle cx="185" cy="128" r="15" fill="#53dccb"/><circle cx="185" cy="171" r="15" fill="#53dccb"/>
</svg>'''
    (TARGET / "codex-team.svg").write_text(svg, encoding="utf-8")
    scale = 4
    image = Image.new("RGBA", (256 * scale, 256 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    def box(values):
        return tuple(v * scale for v in values)
    draw.rounded_rectangle(box((8, 8, 248, 248)), radius=55 * scale, fill="#101a2e")
    draw.arc(box((57, 59, 165, 197)), 90, 270, fill="#e9f3ff", width=24 * scale)
    draw.line(box((111, 71, 151, 71)), fill="#e9f3ff", width=24 * scale)
    draw.line(box((111, 185, 151, 185)), fill="#e9f3ff", width=24 * scale)
    for x, y in ((151, 71), (151, 185)):
        draw.ellipse(box((x - 12, y - 12, x + 12, y + 12)), fill="#e9f3ff")
    draw.line(box((141, 128, 185, 128)), fill="#53dccb", width=12 * scale)
    draw.line(box((185, 85, 185, 171)), fill="#53dccb", width=12 * scale)
    for y in (85, 128, 171):
        draw.ellipse(box((170, y - 15, 200, y + 15)), fill="#53dccb")
    image = image.resize((256, 256), Image.Resampling.LANCZOS)
    image.save(TARGET / "codex-team.png")
    image.save(TARGET / "codex-team.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])

if __name__ == "__main__":
    main()
