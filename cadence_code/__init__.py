"""Local voice tools for Codex and Claude Code."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cadence-code")
except PackageNotFoundError:
    __version__ = "development"
