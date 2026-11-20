"""Reject blank screenshots using Pillow, already installed on the build machine."""
from pathlib import Path
from PIL import Image
for path in Path('tools/web3d/raw/screens').glob('*.png'):
    image=Image.open(path).convert('RGB').resize((128,72))
    colors=image.quantize(colors=32).getcolors()
    largest=max(count for count,_ in colors)/(128*72)
    assert largest<.92, f'{path}: {largest:.1%} single colour (blank canvas)'
    print(path.name, f'largest colour {largest:.1%}')
