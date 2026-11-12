"""Ve man hinh cho (--splash) luc dong goi: anh tinh, khong gia lap tien trinh.

Chu dung Be Vietnam Pro nhu tieu de trong app (lay tu node_modules, vi npm build da
chay truoc buoc nay); thieu thi lui ve Segoe UI. Fontsource tach font theo bo ky tu,
nen moi ky tu duoc ve bang file chua no (tieng Viet / latin).
"""
from pathlib import Path
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from apps.app_version import APP_VERSION

SCALE = 3
WIDTH, HEIGHT = 640, 380
FONT_DIR = ROOT / "app-desktop" / "cit-voice-app" / "node_modules" / "@fontsource" / "be-vietnam-pro" / "files"
# unicode-range cua bo "vietnamese" trong @fontsource/be-vietnam-pro.
VI_RANGES = (
    (0x0102, 0x0103), (0x0110, 0x0111), (0x0128, 0x0129), (0x0168, 0x0169),
    (0x01A0, 0x01A1), (0x01AF, 0x01B0), (0x0300, 0x0309), (0x0323, 0x0323),
    (0x1EA0, 0x1EF9), (0x20AB, 0x20AB),
)


def _is_vi(ch: str) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in VI_RANGES)


def _fonts(weight: int, size: int):
    """(font latin, font tieng Viet) cho mot co chu."""
    px = size * SCALE
    latin = FONT_DIR / f"be-vietnam-pro-latin-{weight}-normal.woff"
    vi = FONT_DIR / f"be-vietnam-pro-vietnamese-{weight}-normal.woff"
    try:
        return ImageFont.truetype(str(latin), px), ImageFont.truetype(str(vi), px)
    except OSError:
        name = "segoeuib.ttf" if weight >= 600 else "segoeui.ttf"
        font = ImageFont.truetype("C:/Windows/Fonts/" + name, px)
        return font, font


def _text(draw, x, y, value, size, color, weight=400, anchor_right=False):
    latin, vi = _fonts(weight, size)
    runs = [(ch, vi if _is_vi(ch) else latin) for ch in value]
    total = sum(font.getlength(ch) for ch, font in runs)
    cx = x * SCALE - (total if anchor_right else 0)
    for ch, font in runs:
        # Neo theo baseline de hai file font khop dong.
        draw.text((cx, y * SCALE), ch, font=font, fill=color, anchor="ls")
        cx += font.getlength(ch)


def _background() -> Image.Image:
    h, w = HEIGHT * SCALE, WIDTH * SCALE
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) / SCALE
    t = (xx / WIDTH * 0.35 + yy / HEIGHT * 0.65)[..., None]
    base = np.array([15, 23, 42]) * (1 - t) + np.array([8, 13, 26]) * t  # slate-900 -> toi hon
    glow = np.clip(1 - np.hypot(xx - 520, yy - 40) / 420, 0, 1)[..., None] ** 2
    glow2 = np.clip(1 - np.hypot(xx - 80, yy - 360) / 360, 0, 1)[..., None] ** 2
    rgb = base + glow * np.array([20, 110, 100]) * 0.55 + glow2 * np.array([10, 70, 90]) * 0.35
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")


def _wave(canvas: Image.Image) -> None:
    """Dai song am trang tri, mo dan hai dau."""
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    left, right, mid, count = 48, 592, 246, 68
    step = (right - left) / count
    for i in range(count):
        u = i / (count - 1)
        amp = (0.55 + 0.45 * math.sin(u * 9.1 + 0.6)) * (0.6 + 0.4 * math.sin(u * 23.7))
        amp = abs(amp) * math.sin(math.pi * u) ** 0.8
        bar = 4 + 42 * amp
        alpha = round(70 + 150 * math.sin(math.pi * u) ** 1.5)
        color = (45 + round(50 * u), 212 - round(30 * u), 191 + round(40 * u), alpha)
        x = left + i * step
        draw.rounded_rectangle(
            tuple(round(v * SCALE) for v in (x, mid - bar / 2, x + step * 0.48, mid + bar / 2)),
            radius=round(step * 0.24 * SCALE), fill=color)
    canvas.alpha_composite(layer)


def _logo(canvas: Image.Image, x: int, y: int, size: int) -> None:
    logo = Image.open(ROOT / "assets" / "brand" / "cit-logo.png").convert("RGBA")
    # Bo le trong suot cua anh goc (40/1024) de logo khop dung o vuong.
    inset = round(logo.width * 40 / 1024)
    logo = logo.crop((inset, inset, logo.width - inset, logo.height - inset))
    logo = logo.resize((size * SCALE, size * SCALE), Image.Resampling.LANCZOS)
    canvas.alpha_composite(logo, (x * SCALE, y * SCALE))


def render(output: Path = ROOT / "assets" / "splash.png") -> Path:
    canvas = _background()
    draw = ImageDraw.Draw(canvas)
    s = SCALE

    # Vach mau tren cung va vien.
    for x in range(WIDTH * s):
        u = x / (WIDTH * s)
        draw.line((x, 0, x, 3 * s - 1), fill=(round(16 + 20 * u), round(185 - 40 * u), round(129 + 80 * u)))
    draw.rectangle((0, 0, WIDTH * s - 1, HEIGHT * s - 1), outline="#1e293b", width=s)

    _logo(canvas, 48, 62, 64)
    _text(draw, 130, 98, "CIT Voice Studio", 28, "#f8fafc", 700)
    _text(draw, 131, 122, "Chuyển văn bản thành giọng nói tiếng Việt", 13, "#94a3b8", 400)

    _wave(canvas)
    draw = ImageDraw.Draw(canvas)

    draw.line((48 * s, 316 * s, 592 * s, 316 * s), fill="#1e293b", width=s)
    draw.ellipse((48 * s, 340 * s, 55 * s, 347 * s), fill="#2dd4bf")
    _text(draw, 64, 348, "Đang khởi động…", 12, "#e2e8f0", 600)
    _text(draw, 592, 348, f"v{APP_VERSION}  ·  Cường IT", 11, "#64748b", 500, anchor_right=True)

    canvas.convert("RGB").resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).save(output)
    return output


if __name__ == "__main__":
    print(render())
