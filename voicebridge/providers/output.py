import sys
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout


@contextmanager
def model_output_to_stderr() -> Iterator[None]:
    """Keep third-party model output off the MCP stdout transport."""
    with redirect_stdout(sys.stderr):
        yield
