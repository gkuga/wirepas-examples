FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# The D-Bus policy grants the sink names to the wirepas user only, and the bus
# matches clients by UID, so this must be the same uid as everywhere else.
RUN useradd --uid 1000 --create-home wirepas

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY sink_mock.py ./

USER wirepas
ENV PYTHONUNBUFFERED=1
CMD ["uv", "run", "--no-sync", "sink_mock.py"]
