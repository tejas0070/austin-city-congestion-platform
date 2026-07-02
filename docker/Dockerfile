FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hosts inject the port via $PORT (Render, Fly, HF Spaces, Cloud Run); default 8000.
ENV PORT=8000
EXPOSE 8000

# Shell form so $PORT expands at runtime.
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
