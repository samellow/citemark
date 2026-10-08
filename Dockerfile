# Python only for now. The Node stage that builds the widget and admin page arrives in Phase 2.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md LICENSE NOTICE alembic.ini ./
COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --system --no-create-home citemark
USER citemark
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["citemark"]
CMD ["--help"]
