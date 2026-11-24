# Project journal · سجل المشروع

**Group · المجموعة:** Osama Alghamdi, working alone. AI coding agent: Claude (Anthropic), a
cloud session in the Claude app, model Claude Fable 5.2.
**Track · المسار:** stocks
**Repository · المستودع:** https://github.com/osamoh/aie113-projects

Each entry is drafted by the agent and stays marked **DRAFT** until I have checked it, run the
checks myself and rewritten the explanation in my own words. Lines starting with "Mine to do"
are things only I can do.

---

## Stage 0: Track and model · المسار والنموذج

**Status: DRAFT by the agent.**

**What we asked the agent · ما طلبناه من الوكيل**
- "Read the project page carefully and choose the stocks track."
- The agent read `AGENTS.md`, `GUIDE.md`, `tracks/stocks/README.md` and every cell of the
  notebook, then explained the model and proposed a plan for Stage 1 before changing anything.

**What it built · ما بناه**
Nothing in this stage. Later, with my OK, it removed `tracks/fraud` and `tracks/vision` so the
repository holds only my track.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
- The agent ran a scratch copy of the notebook in its own workspace (not in this repository).
  It finished in about 9 seconds and gave the README's numbers exactly: 1,246 rows downloaded,
  1,215 kept, 950 training days, 245 test days, chosen strength (alpha) 1000.
- The key number: on the test year the model's average error is 0.1732 SAR and the naive guess
  "tomorrow = today" has 0.1712 SAR. The model is 1.17% worse. It gets the direction right on
  51.3% of the days that moved; a coin flip gets about 50%.
- The notebook's example: after the 25.92 SAR close of Thursday 29 October 2026 it forecasts
  25.895 SAR, 2.53 halalas lower. The biggest push down is the move two days earlier.
- Mine to do: run the notebook myself in Colab (Runtime → Run all) and note what I saw.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
- The model does not beat the simplest possible guess, and the README says so openly.
- Yahoo answered the agent's first request with "Crumb fetch rate-limited (HTTP 429)" and
  still sent the prices. The price source can refuse us at any time.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
(Agent's draft, to rewrite in my own words.) The model looks at the last few weeks of Saudi
Aramco's closing prices and guesses the next trading day's close. It is a ridge regression: a
weighted sum of eight simple numbers about the recent past, held back from large weights. We
judge it only against the baseline "tomorrow = today", on a year it never saw while learning.
It loses to that baseline by about 1%, so its honest value is as a teaching example. It knows
nothing about news, oil prices or dividend dates and must never be used as investment advice.

**Open questions · أسئلة ما زالت مفتوحة**
- Mine to do: one sentence on why I chose the stocks track.

---

## Stage 1: Clean architecture · المعمارية النظيفة

**Status: DRAFT by the agent.**

**What we asked the agent · ما طلبناه من الوكيل**
- I approved the agent's Stage 1 plan: keep only the stocks track, save the notebook's answers
  first, then move the code into layers and prove the answers are unchanged.

**What it built · ما بناه**
```
src/stocks_service/
  domain/     the words and rules of the problem, standard library only
    prices.py     a closing price on a day; a price history; "as it was known on day X"
    features.py   the model's eight inputs, written once, using only the past
    forecast.py   a forecast with its naive guess, reasons and disclaimer; the error measures
    errors.py     unknown ticker, not enough history, price source down
  service/    the steps of each job, and the shapes of the tools they need
    interfaces.py  what we need from a price source, a model, a trainer and a model store
    forecasting.py the "forecast the next day" job
    training.py    the "train, then test against the naive guess" job
  adapters/   the tools
    yahoo_prices.py  the only file that knows Yahoo Finance
    ridge_model.py   the only file that knows scikit-learn, pandas and joblib
  config.py   every setting (ticker, dates, file paths) in one place
  cli.py      the commands `train` and `forecast`; the one place the pieces are joined
scripts/save_golden.py    runs the notebook's own cells and saves its answers
scripts/check_golden.py   compares the new code with those answers
tests/golden/notebook_answers.json   the saved answers for five fixed days
pyproject.toml            pinned libraries, lint settings and the import rules
```
Import directions: `cli → adapters → service → domain`. Replacing the model changes
`adapters/ridge_model.py`; replacing the data source changes `adapters/yahoo_prices.py`.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
All of this was run by the agent in its own workspace (Linux, Python 3.13).
- `python scripts/save_golden.py`, before any code moved: saved the notebook's answers for
  2024-05-21, 2025-11-02, 2026-03-15, 2026-08-03 and 2026-10-29.
- `python scripts/check_golden.py`: "5/5 days match the notebook's answers" and "Test-period
  numbers match the notebook's" (model MAE 0.1732 SAR, naive 0.1712 SAR).
- `python -m stocks_service.cli train`: 950 training days, 245 test days, alpha 1000, model
  −1.17% against the naive guess, direction right 51.3%.
- `python -m stocks_service.cli forecast --as-of 2026-10-29`: 25.895 SAR against a naive 25.92,
  with the same eight reasons as the notebook.
- `python -m stocks_service.cli forecast --ticker 1120.SR`: refused with "this model only
  knows 2222.SR".
- `ruff check src scripts`: passed. `lint-imports`: 2 contracts kept, 0 broken. The domain and
  service files import only the standard library and each other.
- Broken on purpose: in `features.py`, "move two days ago" was changed to read three days ago.
  The code still ran and the forecasts still looked sensible, but the golden check reported
  "0/5 days match" and 60 different numbers. After undoing it, 5/5 again.
- Mine to do: run `check_golden.py` and the two commands on my Mac and note the output.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
- The notebook writes the input-building code twice (step 5 for training, step 10 for one
  forecast). Two copies can drift apart silently, so the new code has one.
- With the deliberate bug in place, `forecast` moved by only 0.13 halalas (−2.40 instead of
  −2.53), because it still used the model saved earlier. Nobody would notice that by eye. The
  golden check retrains, so it caught every number.
- The first lint run found four style problems (one unsorted import, three strings joined
  without brackets). The agent fixed the code; no rule was switched off.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
(Agent's draft, to rewrite in my own words.) A notebook mixes downloading, rules, the model
and file paths in one long file. We gave each its own place: the domain holds the rules of the
problem and uses no tools; the service holds the steps of each job; the adapters hold the
tools, Yahoo Finance and scikit-learn. Inner parts never import outer parts, so changing the
data provider or the model touches one adapter file. Before moving anything we saved the
notebook's answers for five days, and afterwards we proved the new code gives the same ones.

**Open questions · أسئلة ما زالت مفتوحة**
- Yahoo can correct old prices. If it does, the golden check will fail although our code did
  not change. Should later tests use saved or made-up prices instead of a live download?
- Run before the market closes, `forecast` would use a part-day price as "today's close". The
  service needs a rule for this. (Answered in Stage 2: `domain/market.py`.)
- The golden file holds five days of closing prices, while the track asks that price data stay
  out of the repository. Is that small amount acceptable?

---

## Stage 2: FastAPI endpoint · نقطة نهاية FastAPI

**Status: DRAFT by the agent.**

**What we asked the agent · ما طلبناه من الوكيل**
- "Go to the next stage." Before writing code the agent explained the idea, showed the request
  and the response as examples, listed the errors, and proposed two rules: only finished
  trading days count, and downloaded prices are remembered for 15 minutes. I approved the plan.

**What it built · ما بناه**
- `api/schemas.py`: the exact shape of a request (`{"ticker": "..."}`, nothing else allowed)
  and of a response.
- `api/routes.py`: four addresses: `POST /v1/forecast`, `GET /v1/health`, `GET /v1/ready`,
  `GET /v1/model-info`.
- `api/app.py`: loads the model once at start-up, gives every request a trace id, and turns
  every failure into one error shape, `{"error": {"code", "message", "trace_id"}}`.
- `domain/market.py`: the rule "today's price counts only from 4:00 pm Riyadh time", after the
  exchange's closing auction. Before that the latest price is the previous trading day's.
- `adapters/cached_prices.py`: a 15-minute memory in front of the price source.
- Small changes: new settings in `config.py`; FastAPI in `pyproject.toml`, and the import
  rules now cover `api`; the command line uses the same "finished days" rule.
- `service/forecasting.py` did not need to change.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
All of this was run by the agent in its own workspace, on Tuesday 24 November 2026 after the
market had closed.
- Good request, `{"ticker": "2222.SR"}`: HTTP 200 with `as_of` 2026-11-24, last close 26.30 SAR,
  model forecast 26.315 SAR (+1.52 halalas), naive guess 26.30 SAR, three reasons (the biggest:
  today's move of +0.61% pushed +1.23 halalas), `model_vs_naive_pct` −1.17 and the disclaimer.
- Bad request, `{"tiker": "2222.SR"}`: HTTP 422 `INVALID_REQUEST` naming two problems, "ticker:
  Field required" and "tiker: Extra inputs are not permitted", without repeating what was sent.
- Also rejected with 422: an empty body, a number instead of text, a 26-character "ticker" with
  SQL in it, an extra field `is_admin`, and a body that is not JSON.
- `{"ticker": "1120.SR"}`: HTTP 404 `UNKNOWN_TICKER`, "This model only knows 2222.SR".
- A wrong address: 404 `NOT_FOUND`. `GET` on the forecast address: 405. Both in the same shape.
- Readiness looks at one thing: is the model loaded. It does not call the price source, so a
  failing third party cannot make the whole service look dead. Started with no model file,
  the service refuses to start and prints "No trained model at ... Run: python -m
  stocks_service.cli train".
- With a fake clock: Tuesday 10:00 and 15:59 Riyadh gave `as_of` 2026-11-23 (close 26.14);
  16:00 gave 2026-11-24 (close 26.30); Saturday noon gave Thursday 2026-11-19.
- With a fake price source that fails: HTTP 503 `PRICE_SOURCE_UNAVAILABLE` with
  `Retry-After: 60`. The source's own error text appeared only in the server log.
- With a fake source that crashes with "database password is hunter2": the caller saw only
  `INTERNAL_ERROR` and a trace id; the message and stack trace were only in the server log.
- The first forecast took 647 ms (one download); the same request again took 4 ms.
- `/docs` and `/openapi.json` answered 200. Golden check still 5/5. `ruff` and `lint-imports`
  passed.
- Broken on purpose: the rule "only the share we trained on" was switched off. The service
  then answered HTTP 200 for `1120.SR` with a confident forecast of 61.086 SAR, made by a model
  that has only ever seen Aramco. After undoing it, 404 again.
- Mine to do: start the service on my Mac, open http://localhost:8000/docs, send one good and
  three bad requests, and note what I saw.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
- A wrong answer can look completely healthy: with the ticker rule off, nothing failed and
  the response had the right shape. Only a rule (and later a test) protects against that.
- The first "not JSON" error named the field "1", which means nothing to a caller. The agent
  changed it to say "The body is not valid JSON".
- One of the agent's own check scripts first reported HTTP 500 for "too few days". The server's
  traceback showed the fault was in the check script (FastAPI tried to copy the fake price
  source), not in the service. After fixing the script the service answered 503
  `NOT_ENOUGH_PRICES` as designed.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
(Agent's draft, to rewrite in my own words.) The API is the only door to the model. Its
contract says a request is one field, the ticker, and FastAPI rejects anything else before our
code runs. A good answer always carries the naive guess, the reasons and the "not investment
advice" note, so nobody can show the forecast without its context. Every failure has the same
shape and tells the caller what was wrong without repeating their input or our internals; the
details go to the log under a trace id. The model is loaded once at start-up, and readiness
means exactly that: the model is loaded.

**Open questions · أسئلة ما زالت مفتوحة**
- The service does not know public holidays, so it says "next trading day" without a date.
- If the price source publishes today's close later than 4:00 pm, we would serve yesterday's
  close as the latest for a while. `as_of` in the response makes this visible.
- The 15-minute memory lives inside one process. With several worker processes each has its
  own, so the price source is asked more often than the setting suggests.
- Anyone who can reach the address can call it. An access key is a topic for Stage 6.

---

Stages: 0 Track and model · 1 Clean architecture · 2 FastAPI endpoint · 3 Container ·
4 Tests · 5 GitHub Actions · 6 Secrets · Extension: React front end (optional)

المراحل: 0 المسار والنموذج · 1 المعمارية النظيفة · 2 نقطة نهاية FastAPI · 3 الحاوية ·
4 الاختبارات · 5 GitHub Actions · 6 الأسرار · إضافة اختيارية: واجهة React
