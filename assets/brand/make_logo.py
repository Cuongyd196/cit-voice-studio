"""Ve logo CIT Voice Studio: nen bo goc gradient emerald, chu CIT + song am."""
import sys
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "cit-logo.png"
S = 1024
K = 4  # supersample cho canh min
W = S * K

def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))

top, bot = (16, 185, 129), (13, 116, 144)  # emerald-500 -> teal/cyan dam
grad = Image.new("RGB", (W, W))
gd = ImageDraw.Draw(grad)
for y in range(W):
    gd.line([(0, y), (W, y)], fill=lerp(top, bot, y / (W - 1)))

mask = Image.new("L", (W, W), 0)
margin = 40 * K
ImageDraw.Draw(mask).rounded_rectangle(
    [margin, margin, W - margin, W - margin], radius=220 * K, fill=255)

img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
img.paste(grad, (0, 0), mask)
d = ImageDraw.Draw(img)

# Chu CIT
font = ImageFont.truetype("C:/Windows/Fonts/seguibl.ttf", 330 * K)
text = "CIT"
bbox = d.textbbox((0, 0), text, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
tx = (W - tw) / 2 - bbox[0]
ty = 250 * K - bbox[1]
d.text((tx, ty), text, font=font, fill="white")

# Song am: cac thanh bo tron, cao dan vao giua
heights = [70, 140, 230, 300, 230, 140, 70]
bar_w, gap = 56 * K, 34 * K
total = len(heights) * bar_w + (len(heights) - 1) * gap
x = (W - total) / 2
cy = 740 * K
for h in heights:
    h *= K
    d.rounded_rectangle([x, cy - h / 2, x + bar_w, cy + h / 2],
                        radius=bar_w / 2, fill=(255, 255, 255, 235))
    x += bar_w + gap

img.resize((S, S), Image.LANCZOS).save(OUT)
print("ok", OUT)
