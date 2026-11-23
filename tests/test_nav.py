"""Every page loads the shared burger menu."""
from fastapi.testclient import TestClient
from evorium import main


def test_every_page_has_the_burger_menu():
    client = TestClient(main.app)
    for path in ("/game", "/timeline-page", "/world3d", "/guide"):
        assert '/static/nav.js' in client.get(path).text, path
    script = client.get("/static/nav.js")
    assert script.status_code == 200 and "Timeline" in script.text


def test_guide_warns_about_the_clock_and_has_no_secrets():
    from fastapi.testclient import TestClient
    text = TestClient(main.app).get("/guide").text
    assert "1× real time" in text and "Restart server" in text and "god view" in text
    assert "password" not in text.lower().replace("your own name and password", "")   # no credentials in the page
