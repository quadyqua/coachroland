# Cloud scout service. Only ships the modules the API needs, so the image
# stays small and free of the desktop-only deps (mss, openai, flask, tkinter).
FROM python:3.12-slim

WORKDIR /app

# Install deps first so this layer caches unless requirements change.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Only the package code — .dockerignore keeps .venv/.cache/.env out.
COPY tftwatch/ ./tftwatch/

EXPOSE 8000

# 0.0.0.0 so the port is reachable from outside the container.
CMD ["uvicorn", "tftwatch.api:app", "--host", "0.0.0.0", "--port", "8000"]
