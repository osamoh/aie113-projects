# Stocks forecast service

The final project of **SDA-AIE-113 · Software Engineering Practices for AI Systems**
([SDAIA Academy](https://github.com/SDAIAAcademy)), stocks track. It takes the course's starter
notebook and turns it, stage by stage, into a production-style service, built with an AI coding
agent.

## Contributors

1. Osamah Alghamdi
2. Sultan Alrasheedi
3. Mohammed Aldayel

> **A teaching example, not investment advice.** The model forecasts the next trading day's
> closing price of Saudi Aramco (`2222.SR`) and is always shown next to the naive guess
> "tomorrow = today". On its test year it is 1.2% **worse** than that guess.

- The model in plain words: [tracks/stocks/README.md](tracks/stocks/README.md)
- The course's stage guide: [GUIDE.md](GUIDE.md)
- What was asked, built and checked at each stage: [JOURNAL.md](JOURNAL.md)

## Where things live

```
src/stocks_service/
  domain/     the words and rules of the problem: prices, the eight inputs, a forecast
  service/    the steps of the two jobs (train, forecast) and the shapes of the tools they need
  adapters/   the tools: Yahoo Finance prices, the scikit-learn model and its files
  api/        the web door: request and response shapes, the addresses, one error shape
  config.py   every setting in one place
  cli.py      the commands that start a job
scripts/      save and check the notebook's "golden" answers
tests/golden/ the notebook's answers for five fixed days
models/       the trained model and its facts file
Dockerfile, .dockerignore, docker-compose.yml, requirements.lock   the container
tracks/stocks/  the original notebook and its README
```

Imports point inward only: `api and cli → adapters → service → domain`. The domain and the service
import no model, data or web library; `lint-imports` checks this.

## Run it

Python 3.12 or newer.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python -m stocks_service.cli train                        # download, train, test, save
python -m stocks_service.cli forecast --as-of 2026-10-29  # the notebook's example day
python -m stocks_service.cli forecast                     # from the latest prices
python scripts/check_golden.py                            # same answers as the notebook?
ruff check src scripts && lint-imports
```

## The API

```bash
uvicorn stocks_service.api.app:create_app --factory
```

Then open http://localhost:8000/docs, or in a second terminal:

```bash
curl -s localhost:8000/v1/forecast -H "content-type: application/json" -d '{"ticker": "2222.SR"}'
curl -s localhost:8000/v1/forecast -H "content-type: application/json" -d '{"ticker": "1120.SR"}'
curl -s localhost:8000/v1/ready
curl -s localhost:8000/v1/model-info
```

| Address | What it answers |
|---|---|
| `POST /v1/forecast` | The forecast for the next trading day, the naive guess next to it, the top reasons |
| `GET /v1/health` | Is the process alive? |
| `GET /v1/ready` | Is the model loaded? |
| `GET /v1/model-info` | The model's facts: version, inputs, training dates, test numbers |

Started this way, without a key, the forecast address is open (the log says so). With
`STOCKS_API_KEY` set, or the file `/run/secrets/stocks_api_key` present, every forecast request
needs the header `X-API-Key`; `/docs` then shows an "Authorize" button for it.

Every error has one shape, `{"error": {"code", "message", "trace_id"}}`, and never repeats what
was sent. Only finished trading days count: today's price is used from 4:00 pm Riyadh time.

## The container

The container always needs the API key (see [SECURITY.md](SECURITY.md)). Once, on your machine:

```bash
brew install sops age              # macOS
scripts/secrets_init.sh            # your age key, .sops.yaml, the encrypted key file
```

Then:

```bash
scripts/with_secrets.sh docker compose up --build -d     # build and start, with the key
docker compose ps                                        # wait for "(healthy)"
scripts/with_secrets.sh sh -c 'curl -s localhost:8000/v1/forecast -H "X-API-Key: $STOCKS_API_KEY" -H "content-type: application/json" -d "{\"ticker\": \"2222.SR\"}"'
docker compose down
```

The image is built in two stages from `python:3.12-slim`, installs the exact versions in
`requirements.lock`, runs as the normal user `appuser`, and reports its own readiness. Only
`requirements.lock`, `models/` and `src/` may enter the build (see `.dockerignore`).

## Tests

```bash
pytest                                    # the fast tests, about a second, no internet
pytest --cov --cov-report=term-missing    # the same, plus which lines no test runs
pytest -m network                         # 4 slow tests against the real price source
pytest -m smoke                           # against a running container (SMOKE_API_KEY=its key)
```

| Level | What it protects | Where |
|---|---|---|
| Unit | One small rule at a time: the eight inputs, the naive guess, the market clock, the price memory, the settings | `tests/unit/` |
| Integration | The API's contract, from outside, with a stand-in model and stand-in prices | `tests/integration/` |
| Model behaviour | Promises about the real model on made-up prices: only the past counts, the forecast stays near today's price | `tests/behaviour/` |
| Golden | The committed model still gives the notebook's saved answers | `tests/golden/` |
| Data checks | The real prices are in order, on trading days, fresh and without impossible jumps | `tests/data/` |
| Smoke | The container starts and answers like our service | `tests/smoke/` |

## The pipeline

Every pull request and every push to `main` runs [.github/workflows/ci.yml](.github/workflows/ci.yml):

| Job | What it checks | Runs after |
|---|---|---|
| `lint` | ruff, and the import rules between layers | |
| `test` | the 128+ fast tests, with at least 80% of the code covered | |
| `secret-scan` | gitleaks over the whole history | |
| `image-smoke` | builds the image, waits for healthy, checks it is not root, runs the smoke tests with a throw-away key | the three above |
| `publish` | pushes the image to `ghcr.io/osamoh/aie113-projects`, tagged with the commit | `image-smoke`, and only on `main` |

[.github/workflows/nightly.yml](.github/workflows/nightly.yml) runs the slow tests against the
real price source every night at 04:17 Riyadh time. Branch protection on `main` makes the four
checks required before a pull request can be merged.

## Where the model and the prices live

The trained model is two small files in `models/` (about 3 KB together). They are stored in
git and copied into the image, so the image is complete on its own. `train` rewrites them;
review the change like any code change. Price data is never stored in the repository: it is
downloaded from Yahoo Finance when a command or a request needs it.

After changing a library in `pyproject.toml`, refresh the lock file:

```bash
pip install uv
uv pip compile pyproject.toml --python-version 3.12 --python-platform linux \
    --no-annotate --no-header -o requirements.lock
```

## Stages

0 Meet the model · **1 Clean architecture (done)** · **2 FastAPI endpoint (done)** · **3 Container (done)** ·
**4 Tests (done)** · **5 GitHub Actions (done)** · **6 Secrets (done)**
