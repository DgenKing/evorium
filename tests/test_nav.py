"""Every page loads the shared burger menu."""
from fastapi.testclient import TestClient
from evorium import main


def test_every_page_has_the_burger_menu():
    client = TestClient(main.app)
    for path in ("/", "/timeline-page", "/world3d"):
        assert '/static/nav.js' in client.get(path).text, path
    script = client.get("/static/nav.js")
    assert script.status_code == 200 and "Timeline" in script.text
