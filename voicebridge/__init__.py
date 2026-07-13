"""Local voice tools for Claude Code."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("voicebridge")
except PackageNotFoundError:
    __version__ = "development"
