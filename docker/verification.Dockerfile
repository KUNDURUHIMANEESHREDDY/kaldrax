# Build once, then use this pre-pulled image for --verify-module full.
# The sandbox itself runs with networking disabled.
FROM python:3.13-slim

RUN python -m pip install --no-cache-dir "pytest>=8.0"

WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1
