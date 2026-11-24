FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" --no-deps 2>/dev/null; \
    pip install --no-cache-dir \
    fastapi uvicorn[standard] "pydantic[email]" pydantic-settings "sqlalchemy[asyncio]" alembic \
    asyncpg aiosqlite httpx "pwdlib[argon2]" "pyjwt[crypto]" webauthn pyotp cryptography \
    redis rq qdrant-client pymupdf python-docx lxml python-magic \
    prometheus-fastapi-instrumentator python-multipart

COPY . .
ENV PYTHONPATH=/app/src

EXPOSE 8080
CMD ["uvicorn", "sonavault.main:app", "--host", "0.0.0.0", "--port", "8080"]
