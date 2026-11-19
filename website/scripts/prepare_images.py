#!/usr/bin/env python3
"""Export generated PNG masters with ImageMagick; no Python packages required.

Run from anywhere: python3 website/scripts/prepare_images.py
The website itself has no runtime/build dependency on this script.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / 'images'


def run(*args):
    subprocess.run(['magick', *map(str, args)], check=True, capture_output=True)


def export(source, output, width, height, limit, webp):
    quality = 84 if webp else 80
    while True:
        run(source, '-auto-orient', '-resize', f'{width}x{height}^', '-gravity', 'center',
            '-extent', f'{width}x{height}', '-strip', '-colorspace', 'sRGB',
            '-define', 'webp:method=6', '-quality', quality, output)
        if output.stat().st_size <= limit or quality <= 42:
            break
        quality -= 5
    if output.stat().st_size > limit:
        raise RuntimeError(f'{output.name} exceeds {limit} bytes')
    return {'file': output.name, 'width': width, 'height': height, 'bytes': output.stat().st_size, 'quality': quality}


def main():
    assets = json.loads((IMAGES / 'manifest.json').read_text())
    exports = []
    missing = []
    for item in assets:
        name = Path(item['file']).stem
        source = IMAGES / 'src' / f'{name}.png'
        if not source.exists():
            missing.append(name)
            continue
        width, height = item['width'], item['height']
        if name == 'grain':
            run(source, '-resize', '200x200!', '-strip', IMAGES / 'grain.png')
            exports.append({'file': 'grain.png', 'width': 200, 'height': 200, 'bytes': (IMAGES / 'grain.png').stat().st_size})
        elif name == 'og-image':
            exports.append(export(source, IMAGES / 'og-image.jpg', width, height, 300_000, False))
        else:
            limit = 400_000 if name == 'hero' else 230_000
            for suffix, scale in (('', 1), ('-small', .5)) if not name.startswith('char-') else (('', 1),):
                w, h = round(width * scale), round(height * scale)
                for ext in ('webp', 'jpg'):
                    exports.append(export(source, IMAGES / f'{name}{suffix}.{ext}', w, h, limit, ext == 'webp'))
        item['status'] = 'generated'
    (IMAGES / 'manifest.json').write_text(json.dumps(assets, indent=2, ensure_ascii=False) + '\n')
    (IMAGES / 'exports.json').write_text(json.dumps(exports, indent=2) + '\n')
    print(json.dumps({'exported_files': len(exports), 'missing_masters': missing,
                      'webp_bytes': sum(r['bytes'] for r in exports if r['file'].endswith('.webp'))}))


if __name__ == '__main__':
    main()
