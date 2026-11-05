# syntax=docker/dockerfile:1
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 migrations ./migrations
COPY --chown=10001:10001 alembic.ini ./
RUN groupadd --gid 10001 marketpilot && useradd --uid 10001 --gid marketpilot --no-create-home marketpilot && mkdir -p /app/data && chown -R marketpilot:marketpilot /app/data
USER marketpilot
ENV DATABASE_URL=sqlite:////app/data/marketpilot.db
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ready', timeout=3)"
CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers"]
