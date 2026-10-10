"""Full-page comparisons against the unmodified export, not self-approved snapshots."""
from io import BytesIO
from base64 import b64encode
import json
from PIL import Image, ImageChops
import pytest
from playwright.sync_api import expect
from app.pages import PAGES, ROOT

pytestmark = pytest.mark.browser
ARTIFACTS = ROOT / "artifacts"


@pytest.mark.parametrize("route", PAGES)
def test_desktop_matches_original_export(page, base_url, route):
    slug, filename, _ = PAGES[route]
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    response = page.goto(base_url + route)
    assert response.status == 200
    page.evaluate("document.fonts.ready")
    assert page.evaluate("document.fonts.check('500 54px Manrope')")
    ARTIFACTS.mkdir(exist_ok=True)
    actual = page.screenshot(full_page=True, animations="disabled", path=str(ARTIFACTS / f"{slug}.png"))
    # Independent reference: raw Figma fragment + necessary browser reset + same font file.
    # An intercepted document has no network address-space metadata in Chromium.
    # Embed the same font bytes so the independent reference also works on Docker DNS.
    font = b64encode((ROOT / "app/static/fonts/Manrope.ttf").read_bytes()).decode("ascii")
    html = f'''<!doctype html><html lang="ru"><meta charset="utf-8"><style>
    @font-face {{font-family:Manrope;src:url('data:font/ttf;base64,{font}');font-weight:200 800;}}
    * {{box-sizing:border-box;}} body {{margin:0;background:#111313;font-family:Manrope,sans-serif;}}
    </style><body>{(ROOT / filename).read_text('utf-8')}</body></html>'''
    page.route("**/__reference", lambda route: route.fulfill(body=html, content_type="text/html"))
    page.goto(base_url + "/__reference")
    page.evaluate("document.fonts.ready")
    assert page.evaluate("document.fonts.check('500 54px Manrope')")
    reference = page.screenshot(full_page=True, animations="disabled", path=str(ARTIFACTS / f"{slug}-reference.png"))
    a, b = Image.open(BytesIO(actual)).convert("RGB"), Image.open(BytesIO(reference)).convert("RGB")
    assert a.size == b.size, f"Page dimensions changed: {a.size} vs {b.size}"
    diff = ImageChops.difference(a, b)
    # Native form widgets replace painted placeholders. Their own visuals get separate tests.
    if route == "/":
        from PIL import ImageDraw
        draw = ImageDraw.Draw(diff)
        for box in page.locator('[data-layer^="Ввод /"], [data-layer="Чекбокс"]').all():
            rect = box.bounding_box()
            draw.rectangle((rect["x"], rect["y"], rect["x"] + rect["width"], rect["y"] + rect["height"]), fill=(0, 0, 0))
    diff.save(ARTIFACTS / f"{slug}-diff.png")
    changed = sum(1 for pixel in diff.get_flattened_data() if max(pixel) > 8)
    ratio = changed / (a.width * a.height)
    (ARTIFACTS / f"{slug}-comparison.json").write_text(json.dumps({"changed_pixel_ratio": ratio, "width": a.width, "height": a.height}), encoding="utf-8")
    assert ratio < 0.0001, f"Visual difference {ratio:.4%}; see artifacts/{slug}-diff.png"
    assert not errors


@pytest.mark.parametrize("route", PAGES)
@pytest.mark.parametrize("width", [390, 768, 1280])
def test_smaller_viewports(page, base_url, route, width):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(base_url + route)
    page.evaluate("document.fonts.ready")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    expect(page.locator("h1")).to_be_visible()
    expect(page.locator("header a").first).to_be_visible()
    for button in page.locator('header [data-layer^="Кнопка /"]').all():
        assert button.bounding_box()["height"] >= 44
    if width == 390:
        ARTIFACTS.mkdir(exist_ok=True)
        page.screenshot(path=str(ARTIFACTS / f"{PAGES[route][0]}-mobile.png"), full_page=True)


def test_navigation_and_all_project_filters(page, base_url):
    page.goto(base_url)
    page.get_by_role("link", name="Услуги ↓", exact=True).click()
    expect(page).to_have_url(base_url + "/#services")
    for category, count in [("Приложения · 3", 3), ("Автоматизация · 2", 2), ("AI-решения · 2", 2), ("Все · 6", 6)]:
        button = page.get_by_role("button", name=category, exact=True)
        button.click()
        expect(button).to_have_attribute("aria-pressed", "true")
        expect(page.locator("[data-category]:visible")).to_have_count(count)
    page.get_by_role("link", name="FitFuel — посмотреть кейс").click()
    expect(page).to_have_url(base_url + "/projects/fitfuel")
    page.get_by_role("link", name="Обсудить проект →", exact=True).first.click()
    expect(page).to_have_url(base_url + "/#contact")


def fill_form(page):
    page.get_by_label("Как к вам обращаться", exact=True).fill("Браузерный тест")
    page.get_by_label("Как с вами связаться", exact=True).fill("test@example.invalid")
    page.get_by_label("О задаче", exact=True).fill("Проверка работы формы через браузер")
    page.locator('[name="consent"]').check()


@pytest.mark.parametrize("width", [390, 1440])
def test_form_validation_success_and_double_click(page, base_url, width):
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(base_url + "/#contact")
    requests = []
    page.on("request", lambda request: requests.append(request) if request.url.endswith("/api/inquiries") else None)
    page.get_by_role("button", name="Отправить заявку →").click()
    assert not requests
    fill_form(page)
    with page.expect_response("**/api/inquiries") as response:
        page.get_by_role("button", name="Отправить заявку →").dblclick()
    assert response.value.status == 201
    expect(page.get_by_role("status")).to_have_text("Заявка сохранена. Спасибо!")
    expect(page.locator('[name="name"]')).to_have_value("")
    assert len(requests) == 1


def test_keyboard_navigation_and_no_external_resources(page, base_url):
    external = []
    page.on("request", lambda request: external.append(request.url) if not request.url.startswith(base_url + "/") else None)
    page.goto(base_url)
    page.keyboard.press("Tab")
    expect(page.get_by_role("link", name="Перейти к содержимому")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#content")).to_be_focused()
    assert not external


def test_failed_submission_preserves_fields_and_can_retry(page, base_url):
    page.goto(base_url + "/#contact")
    fill_form(page)
    page.route("**/api/inquiries", lambda route: route.fulfill(status=503, body="{}", content_type="application/json"))
    page.get_by_role("button", name="Отправить заявку →").click()
    expect(page.get_by_role("status")).to_contain_text("Не удалось отправить")
    expect(page.locator('[name="name"]')).to_have_value("Браузерный тест")
    expect(page.get_by_role("button", name="Отправить заявку →")).to_be_enabled()
    page.unroute("**/api/inquiries")
    page.get_by_role("button", name="Отправить заявку →").click()
    expect(page.get_by_role("status")).to_have_text("Заявка сохранена. Спасибо!")
