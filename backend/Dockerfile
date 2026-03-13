FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps first (lightweight; add build-essential only if needed)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install published routing/BlueFolder packages. Override via build args if needed.
ARG BLUEFOLDER_API_REF=main
ARG OPT_ROUTING_REF=main
RUN pip install --no-cache-dir "git+https://github.com/ARCofMe/bluefolder-api.git@${BLUEFOLDER_API_REF}" && \
    pip install --no-cache-dir "git+https://github.com/ARCofMe/optimized-routing-extension.git@${OPT_ROUTING_REF}"

# App source
COPY backend /app

EXPOSE 5000

# Waitress keeps things simple/cross-platform; use gunicorn if desired.
CMD ["waitress-serve", "--listen=0.0.0.0:5000", "app:app"]
