FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /nonexistent --shell /usr/sbin/nologin app

COPY pyproject.toml README.md ./
COPY app ./app

FROM base AS development

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e '.[dev]'

COPY alembic.ini ./
COPY migrations ./migrations
COPY tests ./tests

RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS production

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

COPY alembic.ini ./
COPY migrations ./migrations

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
