def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_frontend_se_sirve(client):
    assert client.get("/").status_code == 200
    assert client.get("/informes").status_code == 200
