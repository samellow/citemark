# Python only for now. The Node stage that builds the widget and admin page arrives in Phase 2.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md LICENSE NOTICE alembic.ini ./
COPY prompts ./prompts
COPY content ./content
# What reports and pages render with. The design sources and the gallery stay in the repository.
COPY static ./static
COPY design/glyphs ./design/glyphs
COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --system --no-create-home citemark
USER citemark
# Links the published image to the repository on GitHub's container registry
LABEL org.opencontainers.image.source="https://github.com/samellow/citemark" \
      org.opencontainers.image.description="Citemark: a support bot tested against its own help center" \
      org.opencontainers.image.licenses="MIT"
# Logs reach the host as they're written. In a container the app listens on every interface,
# on the PORT a host such as Render sets (8000 without one).
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 HOST=0.0.0.0
ENTRYPOINT ["citemark"]
# The web app, after migrating the database. Any other command replaces it, such as --help.
CMD ["serve"]
