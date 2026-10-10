"""Add semantics and behavior without rewriting Figma's layout/style declarations.

Run: python -m scripts.build_pages. Original exports remain the visual reference.
"""
import re
from bs4 import BeautifulSoup, Tag
from app.pages import PAGES, ROOT


def add_class(node, *names):
    node["class"] = [*node.get("class", []), *names]


def link(node, target):
    node.name = "a"
    node["href"] = target


def build(source: str) -> str:
    soup = BeautifulSoup(source, "html.parser")
    root = soup.find("div")
    add_class(root, "page")
    sections = root.find_all("div", recursive=False)
    for i, section in enumerate(sections):
        layer = section["data-layer"]
        section.name = "header" if i == 0 else "footer" if "Подвал" in layer else "section"
        for label, anchor in [("Первый экран", "content"), ("Услуги", "services"), ("Контакты", "contact"), ("/ Проекты", "projects")]:
            if label in layer:
                section["id"] = anchor
        if section.get("id") == "content":
            section["tabindex"] = "-1"
        # Semantic headings retain all of their source inline styles.
        candidates = section.find_all("div", style=re.compile(r"font-size: (?:4[2-9]|[56][0-9])px"))
        if candidates:
            candidates[0].name = "h1" if section.get("id") == "content" else "h2"

    # Links in the real page chrome. Buttons drawn inside product mockups stay illustrations.
    for node in soup.select('[data-layer="kpi_dev"]'):
        link(node, "/")
        node["aria-label"] = "kpi_dev — главная"
    for node in soup.select('[data-layer="Услуги ↓"]'):
        link(node, "/#services")
    for node in soup.select('[data-layer="Проекты"]'):
        link(node, "/#projects")
    for node in soup.select('[data-layer^="Кнопка /"]'):
        layer = node["data-layer"]
        if any(word in layer for word in ("Обсудить", "Опишите")):
            link(node, "/#contact")
        elif "Смотреть проекты" in layer:
            link(node, "/#projects")
    for node in soup.select('[data-layer^="© kpi_dev"]'):
        link(node, "/#contact")
    for node in soup.select('[data-layer^="Карточка /"]'):
        name = node["data-layer"]
        for key, route in [("Веб-сервисы", "web-apps"), ("Сайты", "websites"), ("Telegram Mini", "telegram"), ("Автоматизация", "ai")]:
            if key in name:
                link(node, f"/services/{route}")
    for node in soup.select('[data-layer="Проект / FitFuel"]'):
        link(node, "/projects/fitfuel")
        node["aria-label"] = "FitFuel — посмотреть кейс"

    filters = soup.select_one('[data-layer="Фильтры проектов"]')
    if filters:
        add_class(filters, "project-filters")
        filters["role"] = "group"
        filters["aria-label"] = "Фильтр проектов"
        for node, category in zip(filters.find_all("div", recursive=False), ["all", "apps", "automation", "ai"]):
            node.name = "button"
            node["type"] = "button"
            node["data-filter"] = category
            node["aria-pressed"] = "true" if category == "all" else "false"
        rows = soup.select('[data-layer^="Проекты / ряд"]')
        grid = soup.new_tag("div", attrs={"class": "project-grid", "style": "display: contents"})
        rows[0].insert_before(grid)
        categories = {"AI-аналитик для бизнеса": "automation ai", "FitFuel": "apps", "WoodLandToys": "automation", "SkyboxTV": "apps", "AI-консультант для бренда одежды": "ai", "WorkFlow": "apps"}
        for row in rows:
            add_class(row, "project-row")
            grid.append(row.extract())
            for card in row.find_all(recursive=False):
                if isinstance(card, Tag):
                    card["data-category"] = categories[card["data-layer"].removeprefix("Проект / ")]

    form = soup.select_one('[data-layer="Форма обращения"]')
    if form:
        form.name = "form"
        form["id"] = "inquiry-form"
        # JS owns JSON submission. Prevent accidental navigation/leaking fields in a GET URL.
        form["method"] = "post"
        form["action"] = "/api/inquiries"
        for field, name, limit, minimum in zip(form.select('[data-layer^="Поле /"]'), ["name", "contact", "message"], [120, 200, 5000], [1, 3, 5]):
            label, control = field.find_all("div", recursive=False)
            label.name = "label"
            label["for"] = f"inquiry-{name}"
            placeholder = control.get_text(strip=True)
            control.clear()
            control.name = "textarea" if name == "message" else "input"
            control.attrs.update({"id": f"inquiry-{name}", "name": name, "placeholder": placeholder, "required": "", "minlength": str(minimum), "maxlength": str(limit)})
            if name != "message":
                control["type"] = "text"
                control["autocomplete"] = "name" if name == "name" else "on"
            add_class(control, "field")
        consent = form.select_one('[data-layer="Согласие"]')
        consent.name = "label"
        add_class(consent, "consent-label")
        check = consent.select_one('[data-layer="Чекбокс"]')
        check.clear()
        check.name = "input"
        check.attrs.update({"type": "checkbox", "name": "consent", "required": "", "class": "consent-check"})
        button = form.select_one('[data-layer^="Кнопка / Отправить"]')
        button.name = "button"
        button["type"] = "submit"
        status = soup.new_tag("p", attrs={"role": "status", "class": "form-status", "aria-live": "polite"})
        form.append(status)

    # Identify fixed coordinate illustrations before annotating normal layout flow.
    for node in list(soup.select('[style]')):
        style = node["style"]
        if "position: relative" in style and node.find(style=re.compile("position: absolute")):
            if node.find_parent(class_="artwork"):
                continue
            width = re.search(r"(?:^|; )width: ([\d.]+)px", style)
            height = re.search(r"(?:^|; )height: ([\d.]+)px", style)
            if width and height:
                add_class(node, "artwork")
                node["data-width"], node["data-height"] = width[1], height[1]
                shell = soup.new_tag("div", attrs={"class": "artwork-shell", "style": f"width: {width[1]}px; height: {height[1]}px"})
                node.wrap(shell)
    for node in soup.select('[style]'):
        if node.find_parent(class_="artwork") or "artwork" in node.get("class", []):
            continue
        if "width:" in node["style"] and node.get("data-layer") != "Чекбокс":
            add_class(node, "flow")
        if "display:" in node["style"] and "flex" in node["style"] and "flex-direction: column" not in node["style"]:
            add_class(node, "row")
    for svg in soup.select("svg"):
        svg["aria-hidden"] = "true"
    return str(soup).strip() + "\n"


def main():
    output = ROOT / "app/templates/pages"
    output.mkdir(parents=True, exist_ok=True)
    for slug, filename, _ in PAGES.values():
        (output / f"{slug}.html").write_text(build((ROOT / filename).read_text("utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
