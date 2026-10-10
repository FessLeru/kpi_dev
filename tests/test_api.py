import sqlite3
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

VALID = {"name": "Анна", "contact": "@anna", "message": "Нужен сайт компании", "consent": True}


def test_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_inquiry_is_persisted_and_survives_restart(client, database):
    response = client.post("/api/inquiries", json=VALID)
    assert response.status_code == 201
    UUID(response.json()["id"])
    with TestClient(create_app(database)) as restarted:
        assert restarted.get("/healthz").status_code == 200
    with closing(sqlite3.connect(database)) as connection:
        row = connection.execute("SELECT name,contact,message,consent,created_at FROM inquiries").fetchone()
    assert row[:4] == ("Анна", "@anna", "Нужен сайт компании", 1)
    assert row[4].endswith("+00:00")


@pytest.mark.parametrize("field,value", [
    ("name", ""), ("name", "   "), ("name", "n" * 121),
    ("contact", ""), ("contact", "xx"), ("contact", "x" * 201),
    ("message", ""), ("message", "xxxx"), ("message", "x" * 5001),
    ("consent", False), ("consent", "true"), ("consent", 1), ("consent", None),
])
def test_validation_does_not_store_invalid_requests(client, database, field, value):
    assert client.post("/api/inquiries", json={**VALID, field: value}).status_code == 422
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT count(*) FROM inquiries").fetchone()[0] == 0


@pytest.mark.parametrize("field", list(VALID))
def test_required_fields(client, field):
    data = VALID.copy()
    del data[field]
    assert client.post("/api/inquiries", json=data).status_code == 422


def test_invalid_json_extra_fields_and_wrong_content_type(client):
    assert client.post("/api/inquiries", content="{", headers={"Content-Type": "application/json"}).status_code == 422
    assert client.post("/api/inquiries", json={**VALID, "admin": True}).status_code == 422
    assert client.post("/api/inquiries", content="hello", headers={"Content-Type": "text/plain"}).status_code == 422


def test_text_is_trimmed_and_sql_is_data(client, database):
    attack = "'); DROP TABLE inquiries; --"
    assert client.post("/api/inquiries", json={**VALID, "name": "  Анна  ", "message": attack}).status_code == 201
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT name,message FROM inquiries").fetchone() == ("Анна", attack)


def test_concurrent_submissions(client, database):
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: client.post("/api/inquiries", json=VALID), range(12)))
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 12


def test_storage_failure_is_not_false_success(client, database):
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("DROP TABLE inquiries")
    assert client.get("/healthz").status_code == 503
    response = client.post("/api/inquiries", json=VALID)
    assert response.status_code == 503
    assert "sqlite" not in response.text


@pytest.mark.parametrize("path", ["/api/inquiries", "/data/inquiries.sqlite3", "/.env", "/not-found", "/static/../main.py"])
def test_no_public_access_to_submissions_or_private_files(client, path):
    assert client.get(path).status_code in (404, 405)
