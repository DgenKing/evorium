import re
import struct
from pathlib import Path

from evorium.scene import PORTRAITS, first_name
from evorium.seed import CHARACTERS


def test_every_apc_has_a_portrait():
    names = [character[0] for character in CHARACTERS]
    assert len(names) == 20

    index = Path("evorium/static/index.html").read_text(encoding="utf-8")
    match = re.search(r"const portraits = \{(.*?)\n\};", index, re.S)
    assert match
    mapped = dict(re.findall(r"'([^']+)':\s*'([^']+)'", match.group(1)))
    expected = {
        name: ("mo" if name == 'Mohammed "Mo" Iqbal' else name.split()[0].lower())
        for name in names
    }
    assert mapped == expected
    assert "const portrait = portraits[name]" in index

    map_js = Path("evorium/static/map.js").read_text(encoding="utf-8")
    assert "portrait=portraits[a.name]" in map_js

    for name in names:
        filename = first_name(name).lower() + ".png"
        image = PORTRAITS / filename
        assert image.is_file(), f"Missing 3D portrait for {name}: {filename}"
        data = image.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">IIBBBBB", data[16:29]) == (256, 256, 8, 2, 0, 0, 0)
