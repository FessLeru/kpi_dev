FROM python:3.14-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /site
COPY requirements.txt requirements.lock ./
RUN pip install -r requirements.txt -c requirements.lock
RUN useradd --uid 10001 --create-home site && mkdir /data && chown site:site /data
ENV DATABASE_PATH=/data/inquiries.sqlite3

FROM base AS test
USER root
COPY requirements-dev.txt requirements-dev.lock ./
RUN pip install -r requirements-dev.txt -c requirements-dev.lock
RUN python -m playwright install --with-deps chromium
COPY . .
CMD ["pytest", "-m", "not browser", "--cov=app", "--cov-branch", "--cov-fail-under=95"]

FROM base AS production
COPY app ./app
USER site
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
