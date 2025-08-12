import logging
from typing import Optional


def configure_logging(level: int = logging.INFO, fmt: Optional[str] = None) -> None:
    if fmt is None:
        fmt = '%(levelname)s:%(name)s:%(message)s'
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt))
        root.addHandler(handler)
    root.setLevel(level)


