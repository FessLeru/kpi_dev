import os
import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def database(tmp_path):
    return tmp_path / "inquiries.sqlite3"


@pytest.fixture
def client(database):
    with TestClient(create_app(database)) as client:
        yield client


@pytest.fixture(scope="session")
def base_url():
    return os.getenv("BASE_URL", "http://127.0.0.1:8000")


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(args=["--no-sandbox"])
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    page = context.new_page()
    yield page
    context.close()
