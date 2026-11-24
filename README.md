# Stocks forecast service

The final project of **SDA-AIE-113 · Software Engineering Practices for AI Systems** (SDAIA
Academy), stocks track. It takes the course's starter notebook and turns it, stage by stage,
into a production-style service, built with an AI coding agent.

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
python -m stocks_service.cli train          # once: the service needs a trained model
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

Every error has one shape, `{"error": {"code", "message", "trace_id"}}`, and never repeats what
was sent. Only finished trading days count: today's price is used from 4:00 pm Riyadh time.

`train` writes `artifacts/model.joblib` and `artifacts/model_meta.json`. They are not stored
in git: each run creates them again. Price data is never stored in the repository either; it
is downloaded from Yahoo Finance when a command runs.

## Stages

0 Meet the model · **1 Clean architecture (done)** · **2 FastAPI endpoint (done)** · 3 Container ·
4 Tests · 5 GitHub Actions · 6 Secrets
