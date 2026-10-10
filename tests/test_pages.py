from collections import Counter
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
import pytest
from app.pages import PAGES, ROOT
from scripts.build_pages import build


@pytest.mark.parametrize("route", PAGES)
def test_pages_semantics_links_and_assets(client, route):
    response = client.get(route)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    soup = BeautifulSoup(response.text, "html.parser")
    assert soup.html["lang"] == "ru"
    assert soup.title.string == PAGES[route][2]
    assert len(soup.select("h1")) == 1
    assert soup.select_one("header") and soup.select_one("footer")
    ids = [node["id"] for node in soup.select("[id]")]
    assert len(ids) == len(set(ids))
    for anchor in soup.select("a[href]"):
        link = urlsplit(anchor["href"])
        target = client.get(link.path or route)
        assert target.status_code == 200, anchor["href"]
        if link.fragment:
            assert BeautifulSoup(target.text, "html.parser").find(id=link.fragment)
    for asset in soup.select("script[src], link[href]"):
        result = client.get(asset.get("src") or asset.get("href"))
        assert result.status_code == 200


@pytest.mark.parametrize("route", PAGES)
def test_generated_pages_are_reproducible_and_keep_every_visual_style(route):
    slug, filename, _ = PAGES[route]
    source = (ROOT / filename).read_text("utf-8")
    generated = (ROOT / f"app/templates/pages/{slug}.html").read_text("utf-8")
    assert generated == build(source), "Run python -m scripts.build_pages"
    original = BeautifulSoup(source, "html.parser")
    result = BeautifulSoup(generated, "html.parser")
    # Only placeholder text moves into native input attributes; all other export layers remain.
    placeholders = {"Имя", "Telegram, телефон или email", "Что хотите создать или улучшить?"} if route == "/" else set()
    expected = Counter((n["data-layer"], n.get("style")) for n in original.select("[data-layer]") if n["data-layer"] not in placeholders)
    actual = Counter((n["data-layer"], n.get("style")) for n in result.select("[data-layer]"))
    assert expected == actual
    # SVG geometry is untouched, except for the checkbox replaced by a native input.
    original_svgs = original.select("svg")
    actual_svgs = result.select("svg")
    assert len(original_svgs) == len(actual_svgs) + (1 if route == "/" else 0)


def test_service_links_filters_and_form(client):
    soup = BeautifulSoup(client.get("/").text, "html.parser")
    assert len(soup.select('a[href^="/services/"]')) == 4
    assert len(soup.select('[data-category]')) == 6
    assert [b.get_text(strip=True) for b in soup.select(".project-filters button")] == ["Все · 6", "Приложения · 3", "Автоматизация · 2", "AI-решения · 2"]
    for name in ["name", "contact", "message", "consent"]:
        assert soup.select_one(f'[name="{name}"][required]')
    assert client.get("/static/fonts/Manrope.ttf").content[:4] == b"\x00\x01\x00\x00"
