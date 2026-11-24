# Secrets in this project

The rule that never bends: **a secret is never in git, never in an image, never in a log.**

This project has one secret: the **API key** that callers must send in the `X-API-Key` header
to get a forecast. It is a practice secret: a random value made by a script, protecting a
teaching service. A real next step would add a second one, the key for a paid market-data
feed, and it would follow exactly the same path.

## The path the key takes

| Where | How the key gets there | What protects it |
|---|---|---|
| Created | `scripts/secrets_init.sh` makes a random 43-character value | It only passes through a pipe; never written to disk in plain text |
| In git | `configs/secrets.enc.env`, encrypted with SOPS for the age public keys in `.sops.yaml` | Only holders of a matching **private** age key can read it. Private keys live in `~/.config/sops/age/keys.txt` and are git-ignored |
| On a laptop | `scripts/with_secrets.sh <command>` decrypts it into that one command's environment | Gone when the command ends; never written to a file |
| In a container | Compose passes it as the file `/run/secrets/stocks_api_key` | Not an environment variable, so not in `docker inspect`; not in the image; Compose refuses to start without it |
| In the service | Read at start-up into a `SecretStr` setting | Printing the settings shows `**********`; a refused value is never repeated in the error; a log filter replaces it with `***` |
| In the pipeline | The smoke test makes a **new random key for each run** | No stored secret is needed at all; the key is hidden in the run's log and disappears with it |
| Publishing the image | `GITHUB_TOKEN`, made for one run, allowed only to write packages, only in the `publish` job | Expires with the run; nothing long-lived is stored |

Stored cloud keys are not needed: this project deploys nowhere yet. When it does, the deploy job
should use **OIDC** (GitHub proves to the cloud which workflow is asking, and the cloud hands out
a credential that expires in minutes) and run in a GitHub **environment** with a required
reviewer, so a person approves each deployment before it can use any secret.

## How leaks are prevented

- **Before each commit:** `pre-commit install` once; gitleaks then checks every commit.
- **In the pipeline:** the `secret-scan` job runs gitleaks over the whole history on every pull
  request and every push. The image is built only after it passes.
- **On GitHub:** secret scanning and push protection (Settings → Code security) block a push
  that contains a known key format.
- **In the tests:** `tests/unit/test_repository_hygiene.py` fails if a plain `.env`, an age
  key or a plain config file is ever tracked by git, or if the secrets file holds a value that
  is not encrypted.
- **In the image:** `.dockerignore` lets only three things into the build.

## If the key leaks: the incident plan

Order matters. Deleting the leaked copy first is the classic mistake: copies remain in git
history, forks, clones, logs and caches. **Make the leaked key useless first.**

1. **Rotate (minutes).** Make a new key and put it in place: `sops configs/secrets.enc.env`,
   replace the value, save, commit, and restart the service with the new key. From now on the
   leaked key opens nothing. Tell every caller the new key through a private channel.
2. **Check (the same hour).** Read the service's logs since the leak for calls made with the
   old key (401 answers after the rotation mean someone is still trying it).
3. **Clean up (the same day).** Remove the leaked copy from wherever it is: the commit (rewrite
   history with `git filter-repo` and force-push only after rotating), the chat, the ticket,
   the log. Ask GitHub support to purge cached views if the repository is public.
4. **Prevent (the same week).** Find out why the scanners did not stop it, and add the missing
   check. Write down what happened in the journal.
5. **If an age private key leaks:** remove its public key from `.sops.yaml`, run
   `sops updatekeys configs/secrets.enc.env`, and rotate every secret in that file: whoever
   holds the old private key can still read old copies of the file from git history.

Who does what: in this one-person project, the owner does every step. In a team, write a name
next to each step before it is needed.
