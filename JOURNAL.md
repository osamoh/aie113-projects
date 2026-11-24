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

## Stage 3: Container · الحاوية

**Status: DRAFT by the agent.**

**What we asked the agent · ما طلبناه من الوكيل**
- "Next." The agent explained the idea and asked me to decide two things. I chose its
  recommendations: the model lives inside the image, and when the price source is down the
  service gives a clear error instead of old prices.

**What it built · ما بناه**
- `requirements.lock`: 79 lines, every library pinned to one exact version, resolved for Linux
  and Python 3.12. No test or lint tools are in it.
- `Dockerfile`: two stages from `python:3.12-slim`. The builder installs the libraries; the
  runtime gets them in one copy, then the model, then the code. It creates the user `appuser`,
  defines a health check that calls `/v1/ready`, and starts the server in list form.
- `.dockerignore`: refuses everything, then lets in only `requirements.lock`, `models/` and
  `src/`.
- `docker-compose.yml`: one command to build and start, port 8000, a 512 MB memory limit.
- `models/model.joblib` and `models/model_meta.json`: the trained model (1.6 KB) and its facts
  (1 KB), now in git. `config.py` points to them.
- `adapters/ridge_model.py`: refuses a model file written by another scikit-learn version.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
All of this was run by the agent in its own workspace (Linux, 2 CPU cores, amd64). That
workspace reaches the internet through a proxy, so the agent built from a test copy of the
Dockerfile with certificate lines added. The committed `Dockerfile` has not been built as-is.
- Image size: 870 MB. The libraries are 537 MB of it; the largest are scipy (139 MB), pandas
  (81 MB), scikit-learn (49 MB), numpy (43 MB) and curl_cffi (41 MB). The model is 20 KB on
  disk and the code 115 KB.
- Build time from nothing: 61 s (30 s installing libraries). Rebuild after a one-line change
  to `routes.py`: 0.4 s, every layer `CACHED` except the code.
- The container runs as `appuser` (user number 10001), on Python 3.12.16. It cannot write to
  `/app/src` or `/app/models`: "Permission denied".
- Secrets: a `.env` and a `leaked.env` holding a fake key were put in the project folder before
  the build. A search of the whole image found no `.env` file and no trace of the key.
- `docker compose up`: "(healthy)" after 5 seconds. Through the container: readiness 200, a
  forecast in 0.69 s (26.315 SAR against a naive 26.30), `1120.SR` refused with 404, `/docs` 200.
- Process number 1 is the server itself. `docker compose stop` took 0.6 s and the log shows
  "shutdown complete". Memory: 145 MiB of the 512 MiB limit.
- With no network at all: the container stayed healthy, and a forecast returned 503
  `PRICE_SOURCE_UNAVAILABLE` with `Retry-After: 60` after 10 seconds (one retry).
- The golden check, run inside the image on its Python 3.12 and locked libraries: 5/5 days
  match. The committed model gives the notebook's 25.895 SAR for 29 October 2026.
- Broken on purpose: the line that copies the model was removed from the `Dockerfile`. The
  image still built, but the container stopped at once ("Exited (3)") with "No trained model
  at models/model_meta.json". After undoing it: healthy again.
- Mine to do: `docker compose up --build -d` on my Mac; note the size, the build time and what
  `docker compose ps` shows. My Mac builds an arm64 image; most servers are amd64.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
- The fake `.env` broke a check: the settings refused the unknown line `FAKE_API_KEY` and the
  error message printed the key's value. An unrelated line in `.env` could stop the service
  and put a secret in a log. The agent changed the settings to ignore lines they do not know;
  secret values we do use will need protecting in Stage 6.
- The image is 870 MB for a model of 1.6 KB. Almost all of it is libraries the model's
  libraries bring with them.
- Start-up failed fast and clearly without a model, which is what we want: a container that
  cannot serve should not look alive.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
(Agent's draft, to rewrite in my own words.) The image is the service packed with everything
it needs: Python, the exact library versions from the lock file, the model and the code. It is
built in two rooms; only the installed libraries pass from the building room to the one we
ship. The order of the steps is from slowest-changing to fastest-changing, so changing code
rebuilds in under a second. The container runs as a normal user, tells Docker whether the
model is loaded, and contains no secret, because only three named things are allowed into the
build. The model lives inside the image, so the image is complete on its own.

**Open questions · أسئلة ما زالت مفتوحة**
- Could the image be smaller? `fastapi[standard]` brings extras we do not use, and the price
  library brings a 41 MB download tool. What would we give up?
- The base image is named by a tag (`python:3.12-slim`) that can move. Should we fix it by its
  digest?
- The service runs one worker process. More workers would each keep their own price memory.
- Should the container's own file system be read-only?

---

## Stage 4: Tests · الاختبارات

**Status: DRAFT by the agent.**

**What we asked the agent · ما طلبناه من الوكيل**
- "Next." Before writing any test the agent listed the planned tests in plain sentences,
  grouped by level, and asked me to decide two things. I chose its recommendations: a quality
  bar (a retrained model may be at most 5% worse than the naive guess), and one change to the
  service (it drops any day after the day asked for, whatever the price source sends).

**What it built · ما بناه**
- `tests/conftest.py`: made-up prices that are the same on every run, a stand-in model, a
  stand-in price source, and a way to start the API with those put in from outside.
- `tests/unit/` (76 tests): each of the eight inputs against a hand calculation; each input
  looks at exactly the days it should; too little history is refused; the naive guess equals
  today's close; reasons add up; today counts from 16:00 Riyadh, not 15:59; the price memory;
  the Yahoo adapter drops no-trading days and retries once; the settings.
- `tests/integration/` (32 tests): a good request has the promised shape; eleven kinds of bad
  request get the same 422; no error repeats the values the caller sent; unknown ticker 404;
  price source down 503; a crash gives 500 and leaks nothing; no model file, no start.
- `tests/behaviour/` (13 tests, the real model): a forecast does not change when later days
  change; it stays within 3% of today's close over 200 invented price series and a crash;
  doubling every price doubles it; a flat price gives a forecast within 2 halalas.
- `tests/golden/` (7 fast, 2 slow): the committed model, given the notebook's saved inputs for
  the five days, gives the notebook's saved forecasts and reasons; the facts file reports the
  notebook's numbers. Slow: download, retrain and compare; and the 5% quality bar.
- `tests/data/` (2 slow): the real prices have no problems and are fresh.
- `tests/smoke/` (4): against a running container.
- `domain/data_checks.py`: names what looks wrong in a price history (a day from the future, a
  Friday, a jump above 15%, prices older than 14 days).
- `service/forecasting.py`: the guard against days from the future.
- `pyproject.toml`: plain `pytest` runs everything that needs no internet and no container.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
All of this was run by the agent in its own workspace.
- `pytest`: 128 passed in about 1 second. By level: unit 0.2 s, integration 0.5 s, behaviour
  0.4 s, golden 0.1 s.
- `pytest -m network`: 4 passed in 5 seconds (two downloads and two retrainings).
- `pytest -m smoke` against the container: 4 passed.
- Coverage of the fast tests: 93%. The part no fast test runs is most of `cli.py` (37%
  covered): the `train` and `forecast` commands. `train` worries me most, because it rewrites
  the model files that ship inside the image. A test for it would run `train` with a stand-in
  price source into a temporary folder and check that both files appear and that the facts
  include the naive baseline.
- Broken on purpose, three times:
  1. "Move two days ago" made to read three days ago: caught by two unit tests in under a
     second (after the tests were strengthened, see below).
  2. The "only the share we trained on" rule switched off: caught by three tests, one at each
     of the unit, integration and behaviour levels.
  3. The model quietly replaced by one trained differently: caught by six of the seven fast
     golden tests. Nothing else noticed.
- Mine to do: run `pytest` on my Mac, then break one rule myself and watch a test fail.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
- The first deliberate break passed all 118 tests that existed then. The hand-made example
  had two equal moves in a row, so reading the wrong day gave the right number by luck. The
  agent changed the example and added a test that nudges one earlier day's price at a time
  and checks that each input changes only for the days it is meant to read. A test that has
  never been seen to fail proves little.
- A test found a real fault: after an unexpected crash, the response carried a trace id in
  its body but not in its header. The agent fixed the service, not the test.
- Writing the tests for the error measures exposed two cases that would have crashed: a test
  period with no days, and one where the price never moved. Both are now handled.
- The replaced model in break 3 passed every behaviour test and was 3.3% worse than naive,
  inside the 5% bar. Only the golden tests can tell that a model has changed.
- Two failures were the agent's workspace, not the service: Docker had stopped (the smoke
  tests could not connect), and the workspace's proxy address had changed, so the container
  could not reach the price source. In that state the smoke test still passed, through its
  "clear 503" branch; with the setup fixed it passed with a real forecast.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
(Agent's draft, to rewrite in my own words.) We test at six levels. Many small tests check
one rule each in milliseconds, with invented prices and a stand-in model, so they never
depend on the internet. A few tests use the real model to check promises about its behaviour,
and golden tests compare its answers with the ones we saved from the notebook. Slow tests go
to the real price source, and a smoke test checks the container. We broke the code on purpose
three times to see that a test fails each time, and the first attempt showed that one of our
tests was too weak.

**Open questions · أسئلة ما زالت مفتوحة**
- The `train` command has no test (see coverage above).
- The smoke test accepts our own "price source unavailable" answer, so a container that can
  never reach prices still passes. Is that acceptable for the pipeline?
- Error messages repeat the names of the fields a caller sent (for example "tiker"), though
  never the values. Should names be limited too?
- The 5% quality bar is a choice, not a measurement. What should it be?

---

## Stage 5: GitHub Actions · GitHub Actions

**Status: DRAFT by the agent.** I asked the agent to do Stages 5 and 6 in one go and then tell
me which decisions it made, so this stage was not explained and agreed step by step before it
was built. The decisions are listed below so I can check each one.

**What we asked the agent · ما طلبناه من الوكيل**
- "Continue all stages all at once and, once you have finished, tell me in summary what
  decisions you made."

**What it built · ما بناه**
- `.github/workflows/ci.yml`, on every pull request and every push to `main`:
  `lint` (ruff, import rules), `test` (fast tests, 80% coverage gate, the coverage report kept
  as evidence), `secret-scan` (gitleaks over the whole history), `image-smoke` (build the
  image, wait for healthy, check the user is `appuser`, run the smoke tests with a throw-away
  key, check the key is not in the log), and `publish` (only on `main`: push the image to
  `ghcr.io/osamoh/aie113-projects` tagged with the commit and `main`).
- `.github/workflows/nightly.yml`: the slow tests against the real price source, every night
  at 04:17 Riyadh time, and on demand.
- `.github/dependabot.yml`: a weekly pull request when an Action we use has a newer version.

**Decisions the agent made · قرارات اتخذها الوكيل**
- The default permission for every job is "read the code". Only `publish` may write packages.
- The slow tests run nightly, not on every pull request: the price source can be slow or refuse
  us, which would make pull requests fail for reasons that are not the change.
- The image is tagged with the commit it was built from, plus a moving `main` tag. No `latest`.
- Action versions are the ones the course's Lab 5 uses (`checkout@v6`, `build-push-action@v7`
  and so on), named by version tag, not by commit fingerprint.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
- `actionlint` (a checker for workflow files): no problems in either file.
- The agent ran each job's commands in its own workspace: lint passed; 128 tests passed with 93%
  coverage; the image built, reported healthy, ran as `appuser`, and the 4 smoke tests passed.
- **Not yet seen running on GitHub.** GitHub switches Actions off on a fork until the owner
  switches them on, and the agent cannot change repository settings.
- Mine to do on GitHub (see "Steps only I can do" at the end of Stage 6).

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
- In the agent's workspace the container could not reach Yahoo, so the smoke test passed through
  its "price source unavailable" branch. On GitHub's machines it should get a real forecast.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
(Agent's draft, to rewrite in my own words.) The pipeline is a checklist GitHub runs on every
change: style and layer rules first because they are fastest, then the tests, then a scan for
secrets, then it builds the real image and tests the running container. Only a change that has
reached `main` publishes the image, and only that one step may write to the registry. With branch
protection on, nothing reaches `main` without passing all four checks.

**Open questions · أسئلة ما زالت مفتوحة**
- Should the Actions be named by commit fingerprint instead of version tag, so a moved tag cannot
  change what runs?
- A red nightly run needs someone to notice it. Who, and how?

---

## Stage 6: Secrets · الأسرار

**Status: DRAFT by the agent.** Built in the same "all at once" request as Stage 5.

**What we asked the agent · ما طلبناه من الوكيل**
- The same request as Stage 5.

**What it built · ما بناه**
- The practice secret: an **API key for our own forecast address**. `POST /v1/forecast` needs
  the header `X-API-Key` when the service has a key; health, readiness and model-info stay open.
- `config.py`: the key is a `SecretStr`, read from `/run/secrets/stocks_api_key` or from
  `STOCKS_API_KEY`; at least 24 characters; a refused value is never repeated in the error.
- `api/routes.py`: the key check (constant-time comparison, 401 in our error shape, checked
  before the request body is read).
- `api/log_masking.py`: a safety net that replaces the key with `***` in every log line,
  tracebacks included.
- `docker-compose.yml`: the key reaches the container as a secret file; Compose refuses to
  start without it.
- `scripts/secrets_init.sh`: makes my age key pair, `.sops.yaml` and the encrypted
  `configs/secrets.enc.env`. `scripts/with_secrets.sh`: runs one command with the key.
- `.gitleaks.toml`, `.pre-commit-config.yaml`, the `secret-scan` job: secret scanning before
  each commit and in the pipeline.
- `tests/unit/test_secrets.py`, `tests/integration/test_api_key.py`,
  `tests/unit/test_repository_hygiene.py`: 25 new tests.
- `SECURITY.md`: the path the key takes, and the incident plan.

**Decisions the agent made · قرارات اتخذها الوكيل**
- The secret is a key for our own API, not a paid data feed: we have no paid feed, and our own
  key can be tested end to end. A data-feed key would follow the same path.
- Without a key the service still starts with the forecast open (a warning in the log), so
  local development and tests stay simple. The container path refuses to start without one.
- The container gets the key as a file, not an environment variable, so `docker inspect` does
  not show it.
- The pipeline needs no stored secret: each run makes a fresh random key for the smoke test.
- No OIDC and no cloud: the project deploys nowhere. `SECURITY.md` says what to do when it does.
- The encrypted file is **not** in the repository yet: it must be encrypted for **my** public
  key, which only exists once I run `scripts/secrets_init.sh` on my own computer.
- gitleaks skips `configs/secrets.enc.env` because it is encrypted; a test checks that every
  value in it really is `ENC[...]`. Two written-out fake values are also allowed.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
All of this was run by the agent in its own workspace.
- Tests: 152 passed, 1 skipped (the encrypted file does not exist yet).
- Container through Compose: without `STOCKS_API_KEY`, Compose refused to start. With a fresh
  random key: healthy; a forecast without the key got 401 `UNAUTHORIZED`; with it, 200; the 5
  smoke tests passed. The key was found **0 times** in `docker inspect`, the container's log,
  the container's environment and the saved image.
- A key shorter than 24 characters stops start-up with "api_key must be at least 24 characters
  long", without printing the value.
- Broken on purpose: a plain `configs/oops.env` was staged in git; the hygiene test failed
  naming the file. Undone.
- **Not run by the agent:** `sops`, `age` and `gitleaks` themselves. Downloading them into the
  agent's workspace was not allowed, so the set-up script was tested only with stand-in
  commands (base64 in place of encryption). That test showed the script's flow: a private key
  file only I can read, a plain value that never touches the disk, no overwrite on a second run,
  and the key reaching only the command it is given to.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
- The settings library printed a refused value in its error, the same problem as in Stage 3.
  Found by a test; fixed with one setting (`hide_input_in_errors`).
- A forecast request arriving during start-up crashed the key check (500) instead of getting
  "not ready" (503). Found by an existing test; fixed so the check refuses.
- A masking test passed alone but failed with the others: a second start-up in the same process
  kept the first start-up's filter, which knew a different key. Fixed by replacing old filters.

**Steps only I can do · خطوات لا يقوم بها إلا أنا**
1. Actions tab → enable workflows on the fork.
2. Settings → Code security → turn on secret scanning and push protection.
3. Settings → Branches → a rule for `main`: require a pull request, and require the checks
   `lint`, `test`, `secret-scan` and `image-smoke` to pass.
4. On my Mac: `brew install sops age`, `scripts/secrets_init.sh`, commit `.sops.yaml` and
   `configs/secrets.enc.env` through a pull request, `pre-commit install`.
5. The drills: open a pull request with a failing test and see merging blocked; commit a fake
   key on a local branch and see gitleaks stop it (never push it).

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
(Agent's draft, to rewrite in my own words.) Our one secret is the API key for the forecast. In
git it exists only encrypted, so the repository can be public; only my private key, which never
leaves my computer, can open it. When the service runs, the key arrives as a file, is held in a
setting that prints as stars, and a log filter hides it if it ever slips into a message. The
pipeline does not need it at all: it makes a throw-away key for each test run. If the key
leaks, we make it useless first by replacing it, and only then clean up.

**Open questions · أسئلة ما زالت مفتوحة**
- With only one person holding a private key, losing my laptop means losing access to the
  secrets file. Who else should hold a key, or where is a backup kept?
- Should the forecast address refuse to start without a key everywhere, not only in the
  container?

---

Stages: 0 Track and model · 1 Clean architecture · 2 FastAPI endpoint · 3 Container ·
4 Tests · 5 GitHub Actions · 6 Secrets · Extension: React front end (optional)

المراحل: 0 المسار والنموذج · 1 المعمارية النظيفة · 2 نقطة نهاية FastAPI · 3 الحاوية ·
4 الاختبارات · 5 GitHub Actions · 6 الأسرار · إضافة اختيارية: واجهة React
