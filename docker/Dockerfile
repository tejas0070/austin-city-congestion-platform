FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hosts inject the port via $PORT (HF Spaces and most PaaS hosts); default 8000.
ENV PORT=8000
EXPOSE 8000

# Shell form so $PORT expands at runtime.
# --proxy-headers + --forwarded-allow-ips="*" make uvicorn resolve the real client
# IP from X-Forwarded-For (the container is only reachable via the HF Space proxy).
# Without this, request.client.host is the proxy IP, so the per-IP rate limiter
# would bucket every visitor into one shared window.
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips="*"
