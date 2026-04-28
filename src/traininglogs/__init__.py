"""traininglogs — parse and process training session logs."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("traininglogs")
except PackageNotFoundError:
    __version__ = "unknown"
