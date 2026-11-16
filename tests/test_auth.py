import base64
import pytest
from fastapi.testclient import TestClient
from evorium import main

@pytest.mark.parametrize('path',['/','/timeline-page','/static/index.html','/agents','/player','/usage','/timeline','/events','/docs','/openapi.json'])
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
    assert client.get('/',headers={'Authorization':auth}).status_code==200
    for value in ['Basic invalid','Bearer value','Basic '+base64.b64encode(b'nocolon').decode()]:
        assert client.get('/',headers={'Authorization':value}).status_code==401
    monkeypatch.setattr(main,'DASHBOARD_PASSWORD','')
    assert client.get('/').status_code==200
    assert client.get('/static/index.html').status_code==200
    assert client.get('/timeline-page').status_code==200
