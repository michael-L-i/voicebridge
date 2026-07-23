#!/usr/bin/env python3
"""Check that a built wheel and sdist carry coherent package metadata."""

from __future__ import annotations

import argparse
import email
import tarfile
import tomllib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    raise SystemExit(f"[fail] {message}")


def package_metadata() -> tuple[str, str, str]:
    with (ROOT / "pyproject.toml").open("rb") as file:
        project = tomllib.load(file)["project"]
    return project["name"], project["version"], project["requires-python"]


def python_specifiers(value: str) -> frozenset[str]:
    return frozenset(specifier.strip() for specifier in value.split(","))


def verify_wheel(wheel: Path, name: str, version: str, requires_python: str) -> None:
    with zipfile.ZipFile(wheel) as archive:
        bad_file = archive.testzip()
        if bad_file:
            fail(f"wheel contains a corrupt file: {bad_file}")
        names = set(archive.namelist())
        metadata_paths = [path for path in names if path.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            fail("wheel must contain exactly one METADATA file")
        metadata = email.message_from_bytes(archive.read(metadata_paths[0]))
        if metadata["Name"] != name or metadata["Version"] != version:
            fail("wheel metadata does not match pyproject.toml")
        if python_specifiers(metadata["Requires-Python"]) != python_specifiers(
            requires_python
        ):
            fail("wheel Requires-Python does not match pyproject.toml")
        if not any(path.startswith("cadence_code/") and path.endswith(".py") for path in names):
            fail("wheel does not contain the cadence_code package")


def verify_sdist(sdist: Path, name: str, version: str) -> None:
    expected_root = f"{name}-{version}/"
    required_files = {
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "cadence_code/config.py",
        "cadence_code/mcp/server.py",
    }
    with tarfile.open(sdist, "r:gz") as archive:
        members = {member.name for member in archive.getmembers() if member.isfile()}
    missing = {expected_root + path for path in required_files} - members
    if missing:
        fail("sdist is missing required files: " + ", ".join(sorted(missing)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_dir", type=Path)
    args = parser.parse_args()

    name, version, requires_python = package_metadata()
    wheels = sorted(args.artifact_dir.glob("*.whl"))
    sdists = sorted(args.artifact_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        fail("expected exactly one wheel and one source distribution")

    verify_wheel(wheels[0], name, version, requires_python)
    verify_sdist(sdists[0], name, version)
    print(f"[ok] verified {wheels[0].name} and {sdists[0].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
