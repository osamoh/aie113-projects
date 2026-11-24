"""The secret: how it is read, that it is never printed, and that logs hide it."""
import io
import logging

import pytest

from stocks_service.api.log_masking import MASK, SecretMaskingFilter, install_secret_masking
from stocks_service.config import Settings

pytestmark = pytest.mark.unit

# A fake key made for these tests. Real keys never appear in code.
FAKE_KEY = "practice-only-0123456789abcdefgh"


def test_no_key_configured_means_none():
    assert Settings(_env_file=None, _secrets_dir=None).api_key is None


def test_the_key_is_read_from_a_secret_file(tmp_path):
    (tmp_path / "stocks_api_key").write_text(FAKE_KEY + "\n", encoding="utf-8")

    settings = Settings(_env_file=None, _secrets_dir=tmp_path)

    assert settings.api_key.get_secret_value() == FAKE_KEY  # the line break is dropped


def test_the_key_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("STOCKS_API_KEY", FAKE_KEY)
    assert Settings(_env_file=None).api_key.get_secret_value() == FAKE_KEY


def test_printing_the_settings_never_shows_the_key(monkeypatch):
    monkeypatch.setenv("STOCKS_API_KEY", FAKE_KEY)
    settings = Settings(_env_file=None)

    for text in (str(settings), repr(settings), str(settings.model_dump()),
                 settings.model_dump_json()):
        assert FAKE_KEY not in text
        assert "**********" in text


def test_an_empty_key_counts_as_no_key(monkeypatch):
    monkeypatch.setenv("STOCKS_API_KEY", "   ")
    assert Settings(_env_file=None).api_key is None


def test_a_short_key_is_refused_without_repeating_it(monkeypatch):
    monkeypatch.setenv("STOCKS_API_KEY", "short-key-1")

    with pytest.raises(ValueError, match="at least 24 characters") as refused:
        Settings(_env_file=None)

    assert "short-key-1" not in str(refused.value)


# ---------- the log safety net ----------

@pytest.fixture
def masked_logger():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SecretMaskingFilter([FAKE_KEY]))
    logger = logging.getLogger("test-masking")
    logger.addHandler(handler)
    logger.propagate = False
    yield logger, stream
    logger.removeHandler(handler)


def test_a_key_in_a_log_message_is_replaced(masked_logger):
    logger, stream = masked_logger

    logger.warning("caller sent %s in a header", FAKE_KEY)

    assert FAKE_KEY not in stream.getvalue()
    assert f"caller sent {MASK} in a header" in stream.getvalue()


def test_a_key_inside_a_traceback_is_replaced(masked_logger):
    logger, stream = masked_logger

    try:
        raise RuntimeError(f"could not connect with key={FAKE_KEY}")
    except RuntimeError:
        logger.exception("request failed")

    text = stream.getvalue()
    assert FAKE_KEY not in text
    assert "RuntimeError" in text and f"key={MASK}" in text


def test_messages_without_a_secret_are_left_alone(masked_logger):
    logger, stream = masked_logger
    logger.warning("price source unavailable for %s", "2222.SR")
    assert stream.getvalue().strip() == "price source unavailable for 2222.SR"


def test_a_new_start_up_replaces_the_old_filter_and_its_old_key():
    """Found by the integration tests: a second start-up kept the first one's filter."""
    stream = io.StringIO()
    root = logging.getLogger()
    handler = logging.StreamHandler(stream)
    root.addHandler(handler)
    try:
        install_secret_masking(["an-old-key-0123456789abcdef"])
        install_secret_masking([FAKE_KEY])
        filters = [f for f in handler.filters if isinstance(f, SecretMaskingFilter)]
        assert len(filters) == 1

        root.warning("leaked %s", FAKE_KEY)
        assert FAKE_KEY not in stream.getvalue()
    finally:
        root.removeHandler(handler)
