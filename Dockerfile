# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Copy the project definition
COPY pyproject.toml .
COPY bl.conf .

# Install dependencies (only)
RUN uv sync --frozen --no-install-project --no-dev

# Copy source
COPY src/ src/
COPY README.md .

# Install the project
RUN uv sync --frozen --no-dev

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Default command
ENTRYPOINT ["bltools"]
CMD ["--help"]
