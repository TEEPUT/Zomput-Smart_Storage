"""Package only public mod assets; no recursive workspace copies or local settings."""
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
PACKAGE = DIST / 'Zomput-Smart_Storage'


def main():
    DIST.mkdir(exist_ok=True)
    if PACKAGE.exists():
        # Fixed, resolved descendant only; never accept a user-supplied deletion target.
        assert PACKAGE.resolve().parent == DIST.resolve()
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir()
    source = ROOT / 'Contents/mods/ZomputSmartStorage'
    target = PACKAGE / 'Contents/mods/ZomputSmartStorage'
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('.keep', '*.log', '__pycache__'))
    for name in ('workshop.txt', 'preview.png'):
        shutil.copy2(ROOT / name, PACKAGE / name)
    with zipfile.ZipFile(DIST / 'Zomput-Smart_Storage.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(target.rglob('*')):
            archive.write(path, path.relative_to(PACKAGE / 'Contents/mods'))
    print('Packaged mod and Workshop staging folder in dist/.')


if __name__ == '__main__':
    main()
