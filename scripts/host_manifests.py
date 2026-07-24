#!/usr/bin/env python3
"""Single source of truth for every per-host plugin and MCP manifest.

Cadence Code ships the same stdio MCP server and the same four workflows to
Claude Code, Codex, Cursor, and Antigravity. Only the manifest *shape* differs
per host, so every shape is derived here and written out by
``scripts/generate_manifests.py``. Nothing else in the repository hand-maintains
a manifest field, and ``scripts/validate_plugin.py`` fails if a generated file
drifts from what this module produces.

Adding host number five means adding one ``host_*`` function below plus its
entry in ``manifests()`` -- not five hand-edited JSON files.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

NAME = "cadence-code"
DISPLAY_NAME = "Cadence Code"
MARKETPLACE_NAME = "cadence-code-marketplace"
AUTHOR = "Michael Li"
AUTHOR_URL = "https://github.com/michael-L-i"
REPOSITORY = "https://github.com/michael-L-i/cadence-code"
LICENSE = "MIT"
BOOTSTRAP = "bin/cadence-code-mcp-bootstrap"

# Host-neutral keywords. Each host appends its own identifier.
KEYWORDS = [
    "apple-silicon",
    "mlx",
    "speech-to-text",
    "text-to-speech",
    "voice-assistant",
]


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)["project"]["version"]


def bootstrap_args(host: str, roots: list[str]) -> list[str]:
    """Build ``bash`` arguments for a program that locates the bootstrap.

    ``roots`` is an ordered list of candidate plugin roots. The first entry is
    normally the host's own plugin-root placeholder, written with braces so the
    host can substitute it. Cursor's ``${CURSOR_PLUGIN_ROOT}`` and Antigravity's
    ``${extensionPath}`` are both *undocumented* for MCP manifests, so this
    deliberately degrades instead of trusting them: a host that leaves the
    placeholder unsubstituted hands bash an unset variable, which expands to an
    empty string, and the remaining candidates still resolve. Later candidates
    use ``$PWD``/``$HOME`` without braces so a host that substitutes every
    ``${...}`` token cannot blank them out.

    ``CADENCE_CODE_HOST`` is exported inside the program rather than relying
    only on the manifest's ``env`` object, because AGY 1.1.6 accepts but does
    not pass the documented stdio ``env``. Manifests still declare ``env`` for
    hosts that honour it; the export makes host identity correct either way.

    Every diagnostic goes to stderr: stdout is the live MCP JSON-RPC channel.
    """
    candidates = " ".join(f'"{root}"' for root in roots)
    program = "; ".join(
        [
            f"export CADENCE_CODE_HOST={host}",
            f"for root in {candidates}",
            f'do bootstrap="$root/{BOOTSTRAP}"',
            'if [ -x "$bootstrap" ]',
            'then exec bash "$bootstrap"',
            "fi",
            "done",
            f'echo "[{NAME}] ERROR: could not locate {BOOTSTRAP}." >&2',
            "exit 1",
        ]
    )
    return ["-c", program]


def host_claude_code(version: str) -> dict[str, dict]:
    """Claude Code expands ``${CLAUDE_PLUGIN_ROOT}`` in its own manifest."""
    description = (
        "Configurable local speech and transcription for natural Claude Code "
        "conversations on Apple Silicon."
    )
    return {
        ".claude-plugin/plugin.json": {
            "name": NAME,
            "version": version,
            "description": description,
            "author": {"name": AUTHOR},
            "license": LICENSE,
            "mcpServers": {
                NAME: {
                    "command": "${CLAUDE_PLUGIN_ROOT}/" + BOOTSTRAP,
                    "env": {
                        "CADENCE_CODE_DATA_DIR": "${CLAUDE_PLUGIN_DATA}",
                        "CADENCE_CODE_HOST": "claude-code",
                    },
                }
            },
        },
        ".claude-plugin/marketplace.json": {
            "name": MARKETPLACE_NAME,
            "owner": {"name": AUTHOR},
            "description": (
                "Marketplace for Cadence Code, local speech input and output "
                "for Claude Code on Apple Silicon."
            ),
            "plugins": [
                {"name": NAME, "source": "./", "description": description}
            ],
        },
    }


def host_codex(version: str) -> dict[str, dict]:
    """Codex bundles its MCP server inside the plugin manifest itself."""
    return {
        ".codex-plugin/plugin.json": {
            "name": NAME,
            "version": version,
            "description": (
                "Fully local voice conversations for Codex and Claude Code on "
                "Apple Silicon."
            ),
            "author": {"name": AUTHOR, "url": AUTHOR_URL},
            "homepage": REPOSITORY,
            "repository": REPOSITORY,
            "license": LICENSE,
            "keywords": sorted([*KEYWORDS, "codex"]),
            "skills": "./skills/",
            "mcpServers": {
                NAME: {
                    "type": "stdio",
                    "command": "bash",
                    "args": [f"./{BOOTSTRAP}"],
                    "cwd": ".",
                    "env": {"CADENCE_CODE_HOST": "codex"},
                    # Covers first-run venv construction, not model loading:
                    # voice_start returns immediately and is polled.
                    "startup_timeout_sec": 900,
                    "tool_timeout_sec": 1800,
                    "default_tools_approval_mode": "approve",
                }
            },
            "interface": {
                "displayName": DISPLAY_NAME,
                "shortDescription": "Local voice conversations for Codex",
                "longDescription": (
                    "Talk naturally with Codex using selectable local speech "
                    "and transcription models on Apple Silicon."
                ),
                "developerName": AUTHOR,
                "category": "Productivity",
                "capabilities": ["Interactive"],
                "websiteURL": REPOSITORY,
                "privacyPolicyURL": f"{REPOSITORY}/blob/main/PRIVACY.md",
                "defaultPrompt": [
                    "Start a local voice coding conversation.",
                    "Choose Cadence Code speech and transcription models.",
                ],
            },
        },
        ".agents/plugins/marketplace.json": {
            "name": MARKETPLACE_NAME,
            "interface": {"displayName": DISPLAY_NAME},
            "plugins": [
                {
                    "name": NAME,
                    "source": {"source": "local", "path": "./"},
                    "policy": {
                        "installation": "AVAILABLE",
                        "authentication": "ON_INSTALL",
                    },
                    "category": "Productivity",
                }
            ],
        },
    }


def host_cursor(version: str) -> dict[str, dict]:
    """Cursor reads skills and a sibling ``mcp.json`` from the plugin root.

    The installed manifest declares no ``cwd``. An unsubstituted
    ``${CURSOR_PLUGIN_ROOT}`` there would be a literal directory name and would
    fail the launch outright, and the bootstrap already resolves its own plugin
    root from ``BASH_SOURCE``, so a working directory buys nothing.
    """
    description = "Fully local voice conversations for Cursor on Apple Silicon."
    return {
        ".cursor-plugin/plugin.json": {
            "name": NAME,
            "displayName": DISPLAY_NAME,
            "version": version,
            "description": description,
            "author": {"name": AUTHOR},
            "homepage": REPOSITORY,
            "repository": REPOSITORY,
            "license": LICENSE,
            "keywords": sorted([*KEYWORDS, "cursor"]),
            "category": "developer-tools",
            "skills": "./skills/",
            # Empty rather than absent: the repository root also carries
            # Claude Code's commands/, which Cursor would otherwise discover.
            "commands": [],
            "mcpServers": "./mcp.json",
        },
        ".cursor-plugin/marketplace.json": {
            "name": MARKETPLACE_NAME,
            "owner": {"name": AUTHOR},
            "metadata": {
                "description": (
                    "Marketplace for fully local Cadence Code voice "
                    "conversations."
                )
            },
            "plugins": [
                {"name": NAME, "source": "./", "description": description}
            ],
        },
        "mcp.json": {
            "mcpServers": {
                NAME: {
                    "command": "bash",
                    "args": bootstrap_args(
                        "cursor",
                        [
                            "${CURSOR_PLUGIN_ROOT}",
                            "$PWD",
                            f"$HOME/.cursor/plugins/{NAME}",
                        ],
                    ),
                    "env": {"CADENCE_CODE_HOST": "cursor"},
                }
            }
        },
        # Loaded by `./dev cursor`, which opens the checkout as the workspace.
        # ${workspaceFolder} is documented and expanded by Cursor, so the
        # direct path is safe here.
        ".cursor/mcp.json": {
            "mcpServers": {
                NAME: {
                    "command": "bash",
                    "args": ["${workspaceFolder}/" + BOOTSTRAP],
                    "cwd": "${workspaceFolder}",
                    "env": {"CADENCE_CODE_HOST": "cursor"},
                }
            }
        },
    }


def host_antigravity(_version: str) -> dict[str, dict]:
    """Antigravity keeps its manifest minimal and its MCP config beside it.

    ``timeoutSeconds`` is not in Antigravity's documented ``mcp_config.json``
    field list, so it is declared as a best-effort hint for first-run venv
    construction only. Model loading no longer depends on it: ``voice_start``
    returns immediately and the host polls ``voice_status``.
    """
    return {
        "plugin.json": {
            "$schema": "https://antigravity.google/schemas/v1/plugin.json",
            "name": NAME,
            "description": (
                "Fully local voice conversations for Antigravity on Apple "
                "Silicon."
            ),
        },
        "mcp_config.json": {
            "mcpServers": {
                NAME: {
                    "command": "bash",
                    "args": bootstrap_args(
                        "antigravity",
                        [
                            "${extensionPath}",
                            "$PWD",
                            f"$HOME/.gemini/antigravity-cli/plugins/{NAME}",
                        ],
                    ),
                    "env": {"CADENCE_CODE_HOST": "antigravity"},
                    "timeoutSeconds": 1800,
                }
            }
        },
        # Loaded by `./dev agy`, which runs from the checkout root.
        ".agents/mcp_config.json": {
            "mcpServers": {
                NAME: {
                    "command": "bash",
                    "args": bootstrap_args("antigravity", ["$PWD"]),
                    "cwd": ".",
                    "env": {"CADENCE_CODE_HOST": "antigravity"},
                    "timeoutSeconds": 1800,
                }
            }
        },
    }


HOSTS = (host_claude_code, host_codex, host_cursor, host_antigravity)


def manifests() -> dict[str, dict]:
    """Every generated manifest, keyed by repository-relative path."""
    version = project_version()
    generated: dict[str, dict] = {}
    for host in HOSTS:
        for path, manifest in host(version).items():
            if path in generated:
                raise RuntimeError(f"two hosts generate the same file: {path}")
            generated[path] = manifest
    return generated


def render(manifest: dict) -> str:
    return json.dumps(manifest, indent=2) + "\n"
