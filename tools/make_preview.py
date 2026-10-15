"""Export the original generated cover to the conventional PZ preview size.

Requires Pillow. The full-resolution artwork is preserved in docs/media/.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
with Image.open(ROOT / 'docs/media/workshop-cover.png') as cover:
    cover.thumbnail((512, 512), Image.Resampling.LANCZOS)
    cover.convert('RGB').save(ROOT / 'preview.png', optimize=True)
print('Exported preview.png from the generated cover artwork.')
