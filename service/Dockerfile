# LunarSim service v2: one image, two commands (API and worker).
#
#   docker build -f service/Dockerfile -t lunarsim-service .
#   docker run --rm -p 8800:8800 -v lunarsim-data:/var/lib/lunarsim -e LUNARSIM_DATA_DIR=/var/lib/lunarsim \
#              lunarsim-service                                     # API on :8800
#   docker run --rm -v lunarsim-data:/var/lib/lunarsim -e LUNARSIM_DATA_DIR=/var/lib/lunarsim \
#              lunarsim-service python -m service worker            # the executor, same volume
#
# Build from the repository root (the engine reads data/ and experiments/ relative to it).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    LUNARSIM_DATA_DIR=/var/lib/lunarsim LUNARSIM_REPO_ROOT=/app

# git: the worker records the commit sha / dirty flag of the tree it runs from
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE CITATION.cff ./
COPY lunarsim ./lunarsim
COPY service ./service
COPY experiments ./experiments
COPY data/policies ./data/policies
COPY data/driving ./data/driving
COPY data/terrain ./data/terrain
COPY data/scenarios ./data/scenarios
COPY .git ./.git

RUN pip install -e ".[service]" && mkdir -p /var/lib/lunarsim && useradd -r -u 10001 lunarsim \
    && chown -R lunarsim:lunarsim /var/lib/lunarsim /app
USER lunarsim
VOLUME ["/var/lib/lunarsim"]
EXPOSE 8800

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8800/v2/health', timeout=4).status == 200 else 1)"

CMD ["python", "-m", "service", "serve", "--host", "0.0.0.0", "--port", "8800"]
