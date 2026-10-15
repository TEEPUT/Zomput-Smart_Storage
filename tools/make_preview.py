"""Optional maintainer tool: generate the original Workshop preview with Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
image = Image.new('RGB', (512, 512), '#111c22')
draw = ImageDraw.Draw(image)


def font(size):
    for name in ('arialbd.ttf', 'DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


draw.rounded_rectangle((24, 24, 488, 488), radius=24, outline='#385057', width=2)
draw.text((52, 50), 'ZOMPUT', fill='#8ea8ad', font=font(22))
draw.text((50, 94), 'SMART', fill='#f0eee6', font=font(61))
draw.text((50, 158), 'STORAGE', fill='#f0eee6', font=font(55))
draw.polygon([(143, 268), (267, 233), (390, 268), (266, 306)], fill='#d8a655')
draw.polygon([(143, 276), (260, 314), (260, 411), (143, 371)], fill='#94703d')
draw.polygon([(270, 314), (390, 277), (390, 371), (270, 411)], fill='#b68b49')
draw.line([(166, 302), (240, 326)], fill='#d7b578', width=6)
draw.line([(165, 343), (240, 368)], fill='#d7b578', width=6)
draw.line([(287, 327), (367, 302)], fill='#e5c180', width=6)
draw.line([(287, 369), (367, 344)], fill='#e5c180', width=6)
draw.rounded_rectangle((58, 263, 128, 329), radius=12, fill='#67b6a2')
draw.line([(76, 296), (91, 310), (114, 283)], fill='#112d2b', width=7)
draw.text((51, 447), 'BUILD 42.21  /  MULTIPLAYER', fill='#91b7b2', font=font(20))
image.save(ROOT / 'preview.png')
print('Generated preview.png')
