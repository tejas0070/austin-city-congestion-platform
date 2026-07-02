# Hugging Face Space (Docker SDK) — Austin Traffic Intelligence API.
# This image is built from the RUNTIME SUBSET assembled by
# .github/workflows/deploy-hf.yml (backend/ + data/models + data/geo only), so
# the heavy training CSVs never reach HF (and HF's >10MB LFS rule never trips).
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF routes external traffic to app_port (7860, declared in README.md).
ENV PORT=7860
# HF's container FS: keep the throwaway SQLite in a guaranteed-writable path.
# Only /api/traffic/historical touches the DB; everything else runs on the
# committed model artifacts, so this is just to satisfy create_all() at startup.
ENV DATABASE_URL=sqlite:////tmp/austin_traffic.db
EXPOSE 7860

# Shell form so ${PORT} expands at runtime.
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
