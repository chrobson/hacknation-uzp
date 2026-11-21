# Odwołania2JSON: obraz aplikacji (bez lokalnego LLM; opcjonalny LLM przez API z .env).
#   docker compose run --rm app            -> ./input -> ./output
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY main.py ./
COPY src ./src
COPY config ./config

ENTRYPOINT ["python", "main.py"]
CMD ["--input", "/app/input", "--output", "/app/output"]
