"""Rules about what may be stored in git, checked on every run of the tests."""
import subprocess

import pytest

from conftest import REPO

pytestmark = pytest.mark.unit

SECRETS_FILE = REPO / "configs" / "secrets.enc.env"


def tracked_files() -> list[str]:
    try:
        result = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True,
                                check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not inside a git checkout")
    return result.stdout.splitlines()


def test_no_plain_secret_files_are_stored_in_git():
    forbidden = [path for path in tracked_files()
                 if path.rsplit("/", 1)[-1] in {".env", "keys.txt", "age-key.txt"}
                 or path.endswith(".agekey")
                 or (path.startswith("configs/") and path.endswith(".env")
                     and path != "configs/secrets.enc.env")]
    assert forbidden == []


def test_the_secrets_file_holds_only_encrypted_values():
    """Scanning skips this file because it is encrypted, so we check it really is."""
    if not SECRETS_FILE.exists():
        pytest.skip("no encrypted secrets file yet (made by scripts/secrets_init.sh)")
    for line in SECRETS_FILE.read_text("utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, _, value = line.partition("=")
        assert name.startswith("sops_") or value.startswith("ENC["), f"{name} is not encrypted"


def test_nothing_in_configs_can_enter_the_image():
    allowed = [line.strip() for line in (REPO / ".dockerignore").read_text("utf-8").splitlines()
               if line.startswith("!")]
    assert allowed == ["!requirements.lock", "!models/", "!src/"]
