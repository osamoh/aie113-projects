# The stocks forecast service as an image: slim, not root, with a health check, no secrets.
#
#   docker build -t stocks-service:dev .
#
# Two stages: a "builder" room where the libraries are installed, and a clean "runtime" room
# that is what we ship. Only what is copied through the door (COPY --from=builder) survives.

# ---------- Stage 1: builder (thrown away after the build) ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# A private folder of libraries that we can copy to the next stage in one piece.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Slow and rarely changing, so it goes FIRST: the exact library versions from the lock file.
# Docker reuses this layer until requirements.lock itself changes.
COPY requirements.lock .
RUN pip install -r requirements.lock

# ---------- Stage 2: runtime (what we ship) ----------
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# A normal user. If someone breaks out of this process, they are not root.
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

# From slowest-changing to fastest-changing: libraries, then the model, then the code.
COPY --from=builder /opt/venv /opt/venv
COPY models/ models/
COPY src/ src/

# Which version of the code this image holds; shown by GET /v1/health.
ARG GIT_SHA=dev
ENV STOCKS_GIT_SHA=$GIT_SHA

USER appuser
EXPOSE 8000

# Docker asks the service every 15 seconds whether it is READY (model loaded), not merely
# whether a process exists. Python's own library is used, so no extra tool is installed.
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/ready', timeout=2)"]

# The list form makes the server process number 1, so it receives the stop signal itself and
# can finish the requests it is serving before it exits.
CMD ["uvicorn", "stocks_service.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
