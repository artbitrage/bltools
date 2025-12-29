# Justfile for bltools

set shell := ["powershell", "-c"]

default: help

# List available recipes
help:
    @just --list

# Install dependencies using uv
setup:
    uv sync --all-extras --dev

# Run all tests
test:
    uv run pytest

# Run tests with coverage
test-cov:
    uv run pytest --cov=bltools --cov-report=term-missing --cov-fail-under=90

# Security audit
audit:
    uv run bandit -r src/

# Lint and format code
lint:
    uv run ruff check --fix .
    uv run ruff format .
    uv run mypy .

# Build documentation
docs-build:
    uv run mkdocs build --strict

# Serve documentation locally
docs-serve:
    uv run mkdocs serve

# Build Docker image
docker-build:
    docker build -t bltools .

# Run CLI via Docker
docker-run args:
    docker run -v ${PWD}:/data bltools {{args}}
