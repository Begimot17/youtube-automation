def test_health_is_open_even_with_token(server, monkeypatch):
    monkeypatch.setattr(server.Config, "API_TOKEN", "tok")
    c = server.app.test_client()
    assert c.get("/health").status_code == 200
    assert c.get("/status").status_code == 401
    assert c.get("/status", headers={"X-API-Token": "tok"}).status_code == 200
    assert c.get("/status", headers={"Authorization": "Bearer tok"}).status_code == 200
    assert c.get("/status", headers={"X-API-Token": "bad"}).status_code == 401


def test_open_without_token(server):
    assert server.app.test_client().get("/status").status_code == 200


def test_channel_crud_roundtrip(server):
    c = server.app.test_client()
    r = c.post("/channel", json={"account_name": "a", "channel_name": "b",
                                 "password": "secret"})
    assert r.status_code == 201
    assert c.post("/channel", json={"account_name": "a", "channel_name": "b"}).status_code == 409
    got = c.get("/channel?account_name=a&channel_name=b").get_json()
    assert got["password"] == "******"
    assert got["schedule"] == ["08:00-20:00"]
    assert c.get("/channels").get_json() == [{"account_name": "a", "channel_name": "b"}]
    assert c.delete("/channel?account_name=a&channel_name=b").status_code == 200
    assert c.get("/channel?account_name=a&channel_name=b").status_code == 404


def test_bad_json_bodies_are_400(server):
    c = server.app.test_client()
    assert c.post("/channel", data="not json", content_type="application/json").status_code == 400
    assert c.post("/channel", data="x").status_code == 400
    assert c.post("/notify", data="x").status_code == 400
    assert c.post("/render/custom", data="x").status_code == 400
    assert c.post("/config", data="x").status_code == 400


def test_config_post_sets_and_validates_schedule(server):
    c = server.app.test_client()
    r = c.post("/config", json=[{"account_name": "a", "channel_name": "b",
                                 "schedule": ["22:00-02:00"]}])
    assert r.status_code == 200
    got = c.get("/config").get_json()
    assert got[0]["schedule"] == ["22:00-02:00"]
    r = c.post("/config", json=[{"account_name": "a", "channel_name": "b",
                                 "schedule": ["nonsense"]}])
    assert r.status_code == 400
    assert c.get("/config").get_json()[0]["schedule"] == ["22:00-02:00"]


def test_logs_tail(server, tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "app.log").write_text(
        "".join(f"l{i}\n" for i in range(250)), encoding="utf-8"
    )
    lines = server.app.test_client().get("/logs").get_json()
    assert len(lines) == 100 and lines[-1] == "l249\n" and lines[0] == "l150\n"
