"""Prepara logotipo Soretrac — branco sobre azul #005696."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).parent / "assets"
LOGO_SRC = ASSETS / "logo.png"
SORETRAC_BLUE = (0, 86, 150, 255)  # #005696


def _remove_dark_bg(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r < 50 and g < 50 and b < 50:
                px[x, y] = (0, 0, 0, 0)
    return img


def _to_white(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 30:
                px[x, y] = (255, 255, 255, a)
    return img


def _make_header() -> None:
    src = _to_white(_remove_dark_bg(Image.open(LOGO_SRC)))
    w, h = src.size
    logo_h = 46
    logo_w = int(logo_h * w / h)
    resized = src.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (logo_w + 20, 54), SORETRAC_BLUE)
    canvas.paste(resized, (10, 4), resized)
    canvas.save(ASSETS / "logo_header.png", "PNG")
    src.save(ASSETS / "logo_white.png", "PNG")
    _remove_dark_bg(Image.open(LOGO_SRC)).save(ASSETS / "logo_transparent.png", "PNG")


def _make_icon() -> None:
    src = _to_white(_remove_dark_bg(Image.open(LOGO_SRC)))
    w, h = src.size
    size = 256
    canvas = Image.new("RGBA", (size, size), SORETRAC_BLUE)
    scale = min((size - 50) / w, (size - 50) / h)
    nw, nh = int(w * scale), int(h * scale)
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas.paste(resized, ((size - nw) // 2, (size - nh) // 2), resized)
    canvas.save(ASSETS / "icon.ico", format="ICO", sizes=[(256, 256), (64, 64), (32, 32), (16, 16)])


if __name__ == "__main__":
    if not LOGO_SRC.exists():
        raise FileNotFoundError(f"Coloque logo.png em {ASSETS}")
    _make_header()
    _make_icon()
    print("Logo Soretrac #005696 pronto.")
