FROM python:3.12-slim

WORKDIR /srv

# PR-001R F3: the deployable image is production-like unless told otherwise.
# Without this an image started with no ENV became "local" — self-migrating,
# with every secret check switched off. Local tooling sets ENV=local explicitly
# (ops/docker-compose.yml); tests set ENV=test.
ENV ENV=production

COPY pyproject.toml constraints.txt ./
# PR-001: the verified dependency set (constraints.txt), not whatever PyPI
# resolves on build day — an image rebuilt later must contain what was tested.
RUN pip install --no-cache-dir -c constraints.txt .

COPY app ./app
# TD-01: migrations are the schema source of truth; the image must carry them so
# ensure_schema() can apply (local) or verify (prod) the schema at startup.
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
