"""Server-rendered Figma pages and persistent contact requests."""
from contextlib import asynccontextmanager, closing
from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.pages import PAGES, ROOT


class Inquiry(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    contact: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=5, max_length=5000)
    consent: StrictBool

    @field_validator("consent")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Подтвердите согласие на обработку данных")
        return value


def create_app(database: Path | None = None) -> FastAPI:
    database = database if database is not None else Path(os.getenv("DATABASE_PATH", ROOT / "data/inquiries.sqlite3"))

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("""CREATE TABLE IF NOT EXISTS inquiries (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, contact TEXT NOT NULL,
                message TEXT NOT NULL, consent INTEGER NOT NULL CHECK(consent = 1),
                created_at TEXT NOT NULL)""")
        yield

    application = FastAPI(title="kpi_dev", lifespan=lifespan, docs_url=None, redoc_url=None)
    application.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "app/templates")

    @application.get("/healthz")
    def health():
        try:
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("SELECT id FROM inquiries LIMIT 1")
        except sqlite3.Error:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ok"}

    @application.post("/api/inquiries", status_code=201)
    def submit_inquiry(inquiry: Inquiry):
        identifier = str(uuid4())
        try:
            with closing(sqlite3.connect(database, timeout=10)) as connection, connection:
                connection.execute(
                    "INSERT INTO inquiries VALUES (?, ?, ?, ?, ?, ?)",
                    (identifier, inquiry.name, inquiry.contact, inquiry.message, 1,
                     datetime.now(timezone.utc).isoformat()),
                )
        except sqlite3.Error as exc:
            raise HTTPException(503, "Не удалось сохранить заявку. Попробуйте ещё раз.") from exc
        return {"id": identifier, "message": "Заявка сохранена. Спасибо!"}

    def page_handler(slug: str, title: str):
        def render(request: Request):
            return templates.TemplateResponse(request=request, name="page.html", context={
                "slug": slug, "title": title,
            })
        return render

    for route, (slug, _, title) in PAGES.items():
        application.add_api_route(route, page_handler(slug, title), response_class=HTMLResponse,
                                  methods=["GET"], name=slug, include_in_schema=False)

    return application


app = create_app()
