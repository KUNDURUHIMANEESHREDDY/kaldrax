FROM node:24-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv git build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/kaldrax-python \
    && /opt/kaldrax-python/bin/pip install --no-cache-dir "pytest>=8.0"

ENV PATH="/opt/kaldrax-python/bin:${PATH}"
ENV PYTHONDONTWRITEBYTECODE=1
ENV npm_config_update_notifier=false

WORKDIR /opt/kaldrax-deps
COPY desktop/package.json desktop/package-lock.json ./desktop/
RUN cd desktop \
    && npm ci --cache /opt/kaldrax-npm-cache \
    && sha256sum package.json package-lock.json > /opt/kaldrax-desktop-deps.sha256

WORKDIR /workspace
