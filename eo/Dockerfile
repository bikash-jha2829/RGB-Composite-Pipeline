# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 1) Install your Python dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-root

# 2) Copy the rest of your code
COPY . .

# Default entrypoint is irrelevant for building an image
