"""Prepara logotipo Soretrac — recorta conteudo, mantem proporcao original."""
from pathlib import Path
from PIL import Image

ASSETS = Path(__file__).parent / "assets"
LOGO_SRC = ASSETS / "logo.png"
SORETRAC_BLUE = (0, 86, 150, 255)


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


def _crop_content(img: Image.Image) -> Image.Image:
    bbox = img.getbbox()
    if bbox:
        return img.crop(bbox)
    return img


def _make_assets() -> None:
    raw = Image.open(LOGO_SRC)
    transparent = _crop_content(_remove_dark_bg(raw))
    white = _to_white(transparent)

    transparent.save(ASSETS / "logo_transparent.png", "PNG")
    white.save(ASSETS / "logo_white.png", "PNG")

    # Header: logo horizontal com proporcao original (sem achatar)
    w, h = white.size
    logo_h = 48
    logo_w = max(1, int(logo_h * w / h))
    header_img = white.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
    header_img.save(ASSETS / "logo_header.png", "PNG")

    # Icone quadrado
    size = 256
    canvas = Image.new("RGBA", (size, size), SORETRAC_BLUE)
    scale = min((size - 48) / w, (size - 48) / h)
    nw, nh = int(w * scale), int(h * scale)
    resized = white.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas.paste(resized, ((size - nw) // 2, (size - nh) // 2), resized)
    canvas.save(ASSETS / "icon.ico", format="ICO", sizes=[(256, 256), (64, 64), (32, 32), (16, 16)])

    print(f"Logo OK — proporcao {w}x{h} -> header {logo_w}x{logo_h}")


if __name__ == "__main__":
    if not LOGO_SRC.exists():
        raise FileNotFoundError(f"Coloque logo.png em {ASSETS}")
    _make_assets()
