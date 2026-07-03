"""Generate Soretrac logo placeholder."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def create_logo():
    size = 200
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Blue feather-like shape
    draw.ellipse([20, 20, 180, 180], fill="#1a4d8f")
    draw.polygon([(100, 30), (160, 100), (100, 170), (40, 100)], fill="#2e7dd1")

    # S letter
    try:
        font = ImageFont.truetype("arial.ttf", 80)
    except OSError:
        font = ImageFont.load_default()
    draw.text((68, 55), "S", fill="white", font=font)

    out = Path(__file__).parent / "assets" / "logo.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    print(f"Logo criado: {out}")

if __name__ == "__main__":
    create_logo()
