FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TERM=xterm-256color \
    XDG_DATA_HOME=/data \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN useradd --create-home --home-dir /home/ticktask --shell /usr/sbin/nologin ticktask \
    && mkdir -p /data \
    && chown -R ticktask:ticktask /data

COPY README.md pyproject.toml uv.lock ./
COPY src ./src

RUN uv sync --frozen --no-dev

USER ticktask

VOLUME ["/data"]

ENTRYPOINT [ "ticktask" ]
CMD [ "--no-tray" ]
