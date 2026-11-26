"""Рисует иконки приложения и собирает .ico для ярлыков.

Запуск: .venv\\Scripts\\python.exe tools\\make_icons.py
Нужны Pillow и numpy (уже стоят).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icons"
FONT = Path("C:/Windows/Fonts/seguisym.ttf")
KNIGHT = "\u265E"

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
BASE = 1024
SS = 2  # сглаживание: рисуем в 2 раза крупнее и уменьшаем


def gradient(size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    ramp = np.linspace(0.0, 1.0, size, dtype=np.float32)[:, None]
    rows = np.array(top, dtype=np.float32) * (1 - ramp) + np.array(bottom, dtype=np.float32) * ramp
    array = np.repeat(rows[:, None, :], size, axis=1).astype(np.uint8)
    return Image.fromarray(array, "RGB").convert("RGBA")


def glow(image: Image.Image, color: tuple[int, int, int], strength: float = 0.45) -> None:
    size = image.width
    y, x = np.mgrid[0:size, 0:size]
    cx, cy = size * 0.5, size * 0.42
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / (size * 0.55)
    alpha = np.clip(1.0 - dist, 0, 1) ** 2 * strength
    overlay = Image.new("RGBA", (size, size), color + (0,))
    overlay.putalpha(Image.fromarray((alpha * 255).astype(np.uint8), "L"))
    image.alpha_composite(overlay)


def rounded_mask(size: int, radius: float) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def knight_layer(size: int, scale: float, color: tuple[int, int, int, int]) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = ImageFont.truetype(str(FONT), int(size * scale))
    left, top, right, bottom = draw.textbbox((0, 0), KNIGHT, font=font)
    x = (size - (right - left)) / 2 - left
    y = (size - (bottom - top)) / 2 - top
    draw.text((x, y), KNIGHT, font=font, fill=color)
    return layer


def badge_magnifier(size: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy, r = size * 0.735, size * 0.735, size * 0.105
    width = max(2, int(size * 0.023))
    ring = (87, 209, 122, 255)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ring, width=width)
    start = (cx + r * 0.72, cy + r * 0.72)
    end = (cx + r * 1.55, cy + r * 1.55)
    draw.line((start, end), fill=ring, width=width)
    for point in (start, end):
        draw.ellipse(
            (point[0] - width / 2, point[1] - width / 2, point[0] + width / 2, point[1] + width / 2),
            fill=ring,
        )
    return layer


def badge_phone(size: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    width = max(2, int(size * 0.021))
    left, top = size * 0.655, size * 0.625
    right, bottom = size * 0.845, size * 0.915
    green = (87, 209, 122, 255)
    draw.rounded_rectangle(
        (left, top, right, bottom), radius=int(size * 0.032), fill=(17, 22, 18, 255), outline=green, width=width
    )
    # мини-шахматка 2x2
    inner_l, inner_t = left + width * 2, top + width * 2
    inner_r, inner_b = right - width * 2, bottom - width * 2
    step = (inner_r - inner_l) / 2
    for row in range(2):
        for col in range(2):
            if (row + col) % 2 == 0:
                draw.rectangle(
                    (
                        inner_l + col * step,
                        inner_t + row * step,
                        inner_l + (col + 1) * step,
                        inner_t + (row + 1) * step,
                    ),
                    fill=(232, 236, 232, 255),
                )
    return layer


def build(kind: str) -> Image.Image:
    size = BASE * SS
    image = gradient(size, (30, 33, 41), (13, 40, 27))
    glow(image, (46, 160, 92), 0.55 if kind == "assistant" else 0.40)

    # тень под фигурой
    shadow = knight_layer(size, 0.66, (0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(size * 0.012))
    image.alpha_composite(shadow, (0, int(size * 0.018)))

    image.alpha_composite(knight_layer(size, 0.66, (247, 249, 247, 255)))
    image.alpha_composite(badge_magnifier(size) if kind == "assistant" else badge_phone(size))

    # тонкая внутренняя рамка
    border = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(border)
    draw.rounded_rectangle(
        (size * 0.012, size * 0.012, size - size * 0.012, size - size * 0.012),
        radius=size * 0.205,
        outline=(255, 255, 255, 30),
        width=max(2, int(size * 0.004)),
    )
    image.alpha_composite(border)

    mask = rounded_mask(size, size * 0.22)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(image, (0, 0), mask)
    return result.resize((BASE, BASE), Image.LANCZOS)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for kind in ("assistant", "phone"):
        png = build(kind)
        png_path = OUT / f"{kind}.png"
        png.save(png_path, "PNG")
        ico_path = OUT / f"{kind}.ico"
        png.save(ico_path, sizes=SIZES)
        print(f"{png_path.name}: {png_path.stat().st_size // 1024} КБ")
        print(f"{ico_path.name}: {ico_path.stat().st_size // 1024} КБ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
