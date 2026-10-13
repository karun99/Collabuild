FROM python:3.14-slim AS builder

WORKDIR /app

COPY pyproject.toml README.md ./
COPY collabuild/ collabuild/

RUN pip install --no-cache-dir -e ".[web]"

FROM python:3.14-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/collabuild /usr/local/bin/collabuild
COPY --from=builder /app/collabuild /app/collabuild

ENV COLLABUILD_DEV_MODE=0

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/providers/status')" || exit 1

CMD ["collabuild", "web", "--host", "0.0.0.0", "--port", "8080"]
