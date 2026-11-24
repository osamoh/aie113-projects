"""A safety net: if a secret value ever reaches a log line, it is replaced by *** first.

The first rule is never to log a secret at all. This filter catches the mistakes: an error
message that quotes a header, a traceback that shows a variable. It works on every handler,
so it covers our own log lines, the server's and the libraries'.
"""
import logging
from collections.abc import Iterable

MASK = "***"
_SERVER_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


class SecretMaskingFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self._secrets = [secret for secret in secrets if secret]

    def _mask(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, MASK)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        message = record.getMessage()
        if record.exc_info:  # a traceback is turned into text now, so it can be masked too
            message += "\n" + logging.Formatter().formatException(record.exc_info)
            record.exc_info, record.exc_text = None, None
        record.msg, record.args = self._mask(message), None
        return True


def install_secret_masking(secrets: Iterable[str]) -> SecretMaskingFilter:
    """Put the filter on every handler of the root logger and of the web server's loggers."""
    mask = SecretMaskingFilter(secrets)
    for name in ("", *_SERVER_LOGGERS):
        for handler in logging.getLogger(name).handlers:
            # Replace, never keep, an older filter: it may know an older key.
            for old in [f for f in handler.filters if isinstance(f, SecretMaskingFilter)]:
                handler.removeFilter(old)
            handler.addFilter(mask)
    return mask
