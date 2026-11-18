FROM node:24-bookworm-slim AS node24

FROM python:3.13-bookworm

COPY --from=node24 /usr/local/bin/node /usr/local/bin/node
COPY --from=node24 /usr/local/bin/npm /usr/local/bin/npm
COPY --from=node24 /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.11 python3.11-venv git build-essential libatomic1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/kaldrax-python313 \
    && /opt/kaldrax-python313/bin/pip install --no-cache-dir "pytest>=8.0" \
    && python3.11 -m venv /opt/kaldrax-python311 \
    && /opt/kaldrax-python311/bin/pip install --no-cache-dir "pytest>=8.0" \
    && ln -s /opt/kaldrax-python311/bin/python /usr/local/bin/python311

ENV PATH="/opt/kaldrax-python313/bin:/opt/kaldrax-python311/bin:${PATH}"
ENV PYTHONDONTWRITEBYTECODE=1
ENV npm_config_update_notifier=false

WORKDIR /opt/kaldrax-deps
COPY desktop/package.json desktop/package-lock.json ./desktop/
RUN cd desktop \
    && npm ci --cache /opt/kaldrax-npm-cache \
    && sha256sum package.json package-lock.json > /opt/kaldrax-desktop-deps.sha256

WORKDIR /workspace
