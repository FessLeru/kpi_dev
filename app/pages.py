"""Explicit mapping of the six supplied Figma exports to public URLs."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = {
    "/": ("home", "Desktop · 1440 · итерация 1.5 · проверено", "kpi_dev — приложения, сайты и автоматизация"),
    "/services/websites": ("websites", "Услуга · Разработка сайтов на заказ · desktop", "Разработка сайтов на заказ — kpi_dev"),
    "/services/web-apps": ("web-apps", "Услуга · Веб-сервисы и личные кабинеты · desktop", "Веб-сервисы и личные кабинеты — kpi_dev"),
    "/services/telegram": ("telegram", "Услуга · Telegram Mini Apps и боты · desktop", "Telegram Mini Apps и боты — kpi_dev"),
    "/services/ai": ("ai", "Услуга · Автоматизация с помощью AI · desktop", "Автоматизация с помощью AI — kpi_dev"),
    "/projects/fitfuel": ("fitfuel", "Кейс · FitFuel·desktop", "FitFuel — кейс kpi_dev"),
}
