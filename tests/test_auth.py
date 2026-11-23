import base64
import pytest
from fastapi.testclient import TestClient
from evorium import main

@pytest.mark.parametrize('path',['/game','/timeline-page','/static/index.html','/agents','/player','/usage','/timeline','/events','/docs','/openapi.json'])
def test_password_required_on_every_route(monkeypatch,path):
    monkeypatch.setattr(main,'DASHBOARD_PASSWORD','test-only-password')
    client=TestClient(main.app)
    response=client.get(path)
    assert response.status_code==401
    assert response.headers['www-authenticate'].startswith('Basic')
    assert client.get(path,auth=('any','wrong')).status_code==401


def test_password_and_local_mode(monkeypatch):
    client=TestClient(main.app)
    monkeypatch.setattr(main,'DASHBOARD_PASSWORD','pássword')
    auth='Basic '+base64.b64encode('any:pássword'.encode()).decode()
    assert client.get('/game',headers={'Authorization':auth}).status_code==200
    for value in ['Basic invalid','Bearer value','Basic '+base64.b64encode(b'nocolon').decode()]:
        assert client.get('/game',headers={'Authorization':value}).status_code==401
    monkeypatch.setattr(main,'DASHBOARD_PASSWORD','')
    assert client.get('/game').status_code==200
    assert client.get('/static/index.html').status_code==200
    assert client.get('/timeline-page').status_code==200


def test_website_is_public_and_the_game_is_not(monkeypatch):
    monkeypatch.setattr(main,'DASHBOARD_PASSWORD','test-only-password')
    client=TestClient(main.app)
    home=client.get('/')
    assert home.status_code==200 and 'href="/game"' in home.text and 'Shuttle Street' in home.text
    assert client.get('/styles.css').status_code==200
    assert client.get('/images/hero.webp').status_code==200
    assert client.get('/images/../../config.py').status_code in (401,404)
    for path in ['/game','/world3d','/guide','/agents','/static/index.html']:
        assert client.get(path).status_code==401
    assert client.get('/game',auth=('any','test-only-password')).status_code==200
