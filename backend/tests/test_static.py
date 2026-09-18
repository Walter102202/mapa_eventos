def test_escape_js_se_sirve_y_las_paginas_lo_cargan(client):
    r = client.get("/static/js/escape.js")
    assert r.status_code == 200
    assert "function escapeHtml" in r.text

    assert 'src="/static/js/escape.js' in client.get("/").text
    assert 'src="/static/js/escape.js' in client.get("/informes").text
