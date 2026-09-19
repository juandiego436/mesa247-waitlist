"""El camino completo, por HTTP y contra una base de datos real.

Los 50 tests del dominio prueban las reglas. Estos prueban el cableado: que la
transaccion abarque los dos agregados, que los errores del dominio lleguen como
codigos de estado, y que lo publico siga siendo seguro al pasar por la API.
"""
from __future__ import annotations


def _join(client, venue, nombre="Carla Mendoza", tel="987654321", size=4):
    r = client.post(
        "/api/public/queue",
        json={
            "venue_id": venue["id"],
            "name": nombre,
            "phone": tel,
            "party_size": size,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_el_camino_del_encargo(client, venue, host_headers):
    """Un comensal se une, el anfitrion la ve y la llama. Nada mas."""
    carla = _join(client, venue)
    assert carla["position"] == 1
    assert carla["status"] == "waiting"

    board = client.get(
        f"/api/host/venues/{venue['id']}/board", headers=host_headers
    ).json()
    assert board["in_queue"] == 1
    assert board["queue"][0]["name"] == "Carla M."

    entry_id = board["queue"][0]["entry_id"]
    mesa = venue["tables"]["2"]  # 4 plazas, entra el grupo de 4
    assert client.post(
        f"/api/host/entries/{entry_id}/call",
        json={"table_id": mesa},
        headers=host_headers,
    ).status_code == 204

    mio = client.get(f"/api/public/queue/{carla['token']}").json()
    assert mio["status"] == "called"
    assert mio["table_label"] == "2"
    assert mio["hold_expires_at"] is not None

    board = client.get(
        f"/api/host/venues/{venue['id']}/board", headers=host_headers
    ).json()
    retenida = next(t for t in board["tables"] if t["label"] == "2")
    assert retenida["status"] == "held"


def test_la_misma_mesa_no_se_da_a_dos_grupos(client, venue, host_headers):
    """El invariante entre agregados, ya con transaccion y base de datos."""
    _join(client, venue, "Carla M.", "987654321", 2)
    _join(client, venue, "Jorge P.", "987654322", 2)

    board = client.get(
        f"/api/host/venues/{venue['id']}/board", headers=host_headers
    ).json()
    uno, dos = board["queue"][0]["entry_id"], board["queue"][1]["entry_id"]
    mesa = venue["tables"]["1"]

    assert client.post(
        f"/api/host/entries/{uno}/call", json={"table_id": mesa}, headers=host_headers
    ).status_code == 204

    segundo = client.post(
        f"/api/host/entries/{dos}/call", json={"table_id": mesa}, headers=host_headers
    )
    assert segundo.status_code == 409
    assert "retenida" in segundo.json()["detail"] or "held" in segundo.json()["detail"]


def test_el_doble_toque_en_la_tablet_no_rompe_nada(client, venue, host_headers):
    carla = _join(client, venue)
    board = client.get(
        f"/api/host/venues/{venue['id']}/board", headers=host_headers
    ).json()
    entry_id = board["queue"][0]["entry_id"]

    client.post(
        f"/api/host/entries/{entry_id}/call",
        json={"table_id": venue["tables"]["2"]},
        headers=host_headers,
    )
    assert client.post(
        f"/api/host/entries/{entry_id}/seat", headers=host_headers
    ).status_code == 204

    # El segundo toque, con mal wifi y la pantalla sin refrescar todavia.
    repetido = client.post(f"/api/host/entries/{entry_id}/seat", headers=host_headers)
    assert repetido.status_code == 409
    assert client.get(f"/api/public/queue/{carla['token']}").json()["status"] == "seated"


def test_no_cabe_el_grupo_salvo_que_el_anfitrion_fuerce(client, venue, host_headers):
    _join(client, venue, "Familia Rojas", "987654321", size=6)
    board = client.get(
        f"/api/host/venues/{venue['id']}/board", headers=host_headers
    ).json()
    entry_id = board["queue"][0]["entry_id"]
    mesa_pequena = venue["tables"]["2"]  # 4 plazas

    rechazo = client.post(
        f"/api/host/entries/{entry_id}/call",
        json={"table_id": mesa_pequena},
        headers=host_headers,
    )
    assert rechazo.status_code == 409

    forzado = client.post(
        f"/api/host/entries/{entry_id}/call",
        json={"table_id": mesa_pequena, "force": True},
        headers=host_headers,
    )
    assert forzado.status_code == 204


def test_cancelar_devuelve_la_mesa_a_la_cola(client, venue, host_headers):
    carla = _join(client, venue)
    board = client.get(
        f"/api/host/venues/{venue['id']}/board", headers=host_headers
    ).json()
    entry_id = board["queue"][0]["entry_id"]
    client.post(
        f"/api/host/entries/{entry_id}/call",
        json={"table_id": venue["tables"]["2"]},
        headers=host_headers,
    )

    assert client.post(
        f"/api/public/queue/{carla['token']}/cancel"
    ).status_code == 204

    board = client.get(
        f"/api/host/venues/{venue['id']}/board", headers=host_headers
    ).json()
    assert board["in_queue"] == 0
    assert next(t for t in board["tables"] if t["label"] == "2")["status"] == "available"


def test_mesa_libre_devuelve_la_mesa(client, venue, host_headers):
    """La pantalla que le falta al prototipo."""
    _join(client, venue)
    board = client.get(
        f"/api/host/venues/{venue['id']}/board", headers=host_headers
    ).json()
    entry_id = board["queue"][0]["entry_id"]
    mesa = venue["tables"]["2"]
    client.post(
        f"/api/host/entries/{entry_id}/call",
        json={"table_id": mesa},
        headers=host_headers,
    )
    client.post(f"/api/host/entries/{entry_id}/seat", headers=host_headers)

    board = client.get(
        f"/api/host/venues/{venue['id']}/board", headers=host_headers
    ).json()
    assert next(t for t in board["tables"] if t["label"] == "2")["status"] == "occupied"

    assert client.post(
        f"/api/host/tables/{mesa}/release", headers=host_headers
    ).status_code == 204
    board = client.get(
        f"/api/host/venues/{venue['id']}/board", headers=host_headers
    ).json()
    assert next(t for t in board["tables"] if t["label"] == "2")["status"] == "available"


def test_el_reporte_cuadra(client, venue, host_headers):
    sentado = _join(client, venue, "Carla M.", "987654321", 2)
    ido = _join(client, venue, "Jorge P.", "987654322", 2)
    _join(client, venue, "Lucia y Ana", "987654323", 2)

    board = client.get(
        f"/api/host/venues/{venue['id']}/board", headers=host_headers
    ).json()
    por_token = {q["name"]: q["entry_id"] for q in board["queue"]}
    client.post(
        f"/api/host/entries/{por_token['Carla M.']}/call",
        json={"table_id": venue["tables"]["1"]},
        headers=host_headers,
    )
    client.post(
        f"/api/host/entries/{por_token['Carla M.']}/seat", headers=host_headers
    )
    client.post(f"/api/public/queue/{ido['token']}/cancel")

    reporte = client.get(
        f"/api/host/venues/{venue['id']}/report", headers=host_headers
    ).json()
    assert reporte["joined"] == 3
    assert reporte["seated"] == 1
    assert reporte["left_without_seating"] == 1
    assert reporte["still_waiting"] == 1
    assert reporte["adds_up"] is True
    assert sentado["token"]


# --- lo que queda expuesto al publico ---------------------------------------


def test_la_tablet_pide_token(client, venue):
    assert client.get(f"/api/host/venues/{venue['id']}/board").status_code == 401
    assert (
        client.get(
            f"/api/host/venues/{venue['id']}/board",
            headers={"X-Host-Token": "me-lo-invento"},
        ).status_code
        == 401
    )


def test_el_endpoint_publico_no_filtra_a_los_demas(client, venue):
    carla = _join(client, venue, "Carla Mendoza", "987654321", 2)
    _join(client, venue, "Jorge Perez", "987654322", 2)

    cuerpo = client.get(f"/api/public/queue/{carla['token']}").text
    assert "Jorge" not in cuerpo
    assert "987654322" not in cuerpo
    assert "987654321" not in cuerpo  # ni siquiera el suyo propio


def test_un_token_inventado_no_devuelve_nada(client, venue):
    _join(client, venue)
    assert client.get("/api/public/queue/" + "x" * 43).status_code == 404


def test_el_mismo_movil_no_entra_dos_veces(client, venue):
    """Cinco toques nerviosos en 'Unirme' desde la puerta."""
    carla = _join(client, venue)
    repetido = client.post(
        "/api/public/queue",
        json={
            "venue_id": venue["id"],
            "name": "Carla otra vez",
            "phone": "+51 987 654 321",  # el mismo, escrito distinto
            "party_size": 4,
        },
    )
    assert repetido.status_code == 409
    # Le devolvemos su puesto, no un error a secas.
    assert repetido.json()["detail"]["token"] == carla["token"]


def test_un_telefono_que_no_sirve_para_avisar_se_rechaza(client, venue):
    r = client.post(
        "/api/public/queue",
        json={
            "venue_id": venue["id"],
            "name": "Carla",
            "phone": "012345678",
            "party_size": 2,
        },
    )
    assert r.status_code == 422


def test_health_no_toca_la_base(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health/ready").json()["status"] == "ready"
