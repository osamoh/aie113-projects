"""What can go wrong, in the words of the problem. Outer layers turn these into messages."""


class UnknownTicker(ValueError):
    """The model was asked about a share it was never trained on."""


class NotEnoughHistory(ValueError):
    """Too few trading days to build the model's inputs."""


class PriceSourceUnavailable(RuntimeError):
    """The price source sent nothing (it is down, or it refused the request)."""
