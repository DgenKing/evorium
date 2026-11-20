from pathlib import Path
from fastapi.testclient import TestClient
from evorium import main


def test_world3d_page_and_local_assets():
    # No lifespan: do not start heartbeat, read a save, or instantiate a model.
    client = TestClient(main.app)
    response = client.get('/world3d')
    assert response.status_code == 200
    assert 'type="importmap"' in response.text
    assert '/static/world3d/js/main.js' in response.text
    assert 'href="/"' in response.text
    assert '>Home<' not in response.text
    root = Path(main.STATIC)
    for quality in ('low', 'high'):
        for filename in ('shuttle_street.glb', 'collision.glb', 'characters.glb', 'animations.glb'):
            assert (root / 'world3d' / 'assets' / quality / filename).stat().st_size > 100
    assert client.get('/static/vendor/three/three.module.min.js').status_code == 200
    assert client.get('/static/world3d/data/cast.json').status_code == 200
