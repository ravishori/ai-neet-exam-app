FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-create the persistent-storage mount points owned by the app user
# *before* switching off root: an empty named volume first mounted at a path
# that already exists in the image inherits that path's ownership, so this
# is what keeps the non-root `app` user able to write uploaded PDFs and
# visual asset crops once infrastructure/docker/docker-compose.prod.yml
# mounts study_material_data/visual_assets_data there. Skipped for a fresh
# path, the volume would mount in owned by root and every write would fail.
RUN mkdir -p /data/studymaterial /data/visualassets \
    && useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app /data
USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
