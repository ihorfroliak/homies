FROM python:3.12-slim

WORKDIR /srv

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY app ./app
# TD-01: migrations are the schema source of truth; the image must carry them so
# ensure_schema() can apply (local) or verify (prod) the schema at startup.
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
