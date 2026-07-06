import json

# Condensed, spoken-friendly descriptions of tool calls, keyed by tool name.
# This does the "what happened" compression structurally (we know exactly
# which tool ran and on what) rather than leaving an LLM to infer it from raw
# transcript prose -- cheaper and more reliable than asking the summarizer to
# figure out "3 files were edited" from scratch.
_TOOL_DESCRIBERS = {
    "Bash": lambda i: f"ran: {i.get('description') or (i.get('command', '')[:60])}",
    "Edit": lambda i: f"edited {i.get('file_path', 'a file')}",
    "Write": lambda i: f"wrote {i.get('file_path', 'a file')}",
    "Read": lambda i: f"read {i.get('file_path', 'a file')}",
    "Grep": lambda i: f"searched for {i.get('pattern', '...')}",
    "Glob": lambda i: f"searched files matching {i.get('pattern', '...')}",
    "Task": lambda i: f"ran a subagent: {i.get('description', '...')}",
    "WebSearch": lambda i: f"searched the web for {i.get('query', '...')}",
    "WebFetch": lambda i: f"fetched {i.get('url', 'a page')}",
}
# Internal bookkeeping tools that aren't worth mentioning at all.
_SILENT_TOOLS = {"TodoWrite"}

# Safety caps for pathologically large deltas (e.g. a session resuming from
# offset 0 on an already-long transcript). Normal operation keeps deltas
# small since Stop fires every turn; these just stop the summarizer from
# choking on an enormous single delta and echoing raw text back verbatim
# instead of compressing it. Most recent content is kept since it's most
# relevant to "what just happened".
_MAX_STEPS = 20
_MAX_FINAL_TEXT_CHARS = 2000


def _describe_tool_use(name: str, tool_input: dict) -> str | None:
    if name in _SILENT_TOOLS:
        return None
    describer = _TOOL_DESCRIBERS.get(name)
    if describer is None:
        return f"used {name}"
    return describer(tool_input or {})


def read_delta(transcript_path: str, since_byte_offset: int = 0) -> tuple[str, int]:
    """Read everything appended to the transcript since since_byte_offset,
    condense it into a short structured description, and return
    (delta_text, new_byte_offset) so the caller can persist the offset.

    Some subagent transcript paths reported by SubagentStop hooks don't
    resolve to a persisted file (observed in practice for at least one
    subagent type) -- treat that as "nothing to narrate" rather than raising,
    since a missing transcript isn't the caller's fault and shouldn't 500."""
    steps = []
    pending_tool_use: dict[str, str] = {}
    text_blocks = []

    try:
        f = open(transcript_path, "r")
    except FileNotFoundError:
        return "", since_byte_offset

    with f:
        f.seek(since_byte_offset)
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type")
            message = entry.get("message") or {}
            content = message.get("content")
            if not isinstance(content, list):
                continue

            if entry_type == "assistant":
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        text_blocks.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        desc = _describe_tool_use(block.get("name", ""), block.get("input"))
                        if desc:
                            pending_tool_use[block.get("id")] = desc
            elif entry_type == "user":
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        desc = pending_tool_use.pop(block.get("tool_use_id"), None)
                        if desc:
                            if block.get("is_error"):
                                desc += " (failed)"
                            steps.append(desc)

        new_offset = f.tell()

    # Tool calls with no matching result yet (e.g. the turn ended mid-call).
    steps.extend(pending_tool_use.values())
    if len(steps) > _MAX_STEPS:
        steps = steps[-_MAX_STEPS:]

    parts = []
    if steps:
        parts.append("Steps taken: " + "; ".join(steps) + ".")
    final_text = " ".join(t for t in text_blocks if t.strip())
    if len(final_text) > _MAX_FINAL_TEXT_CHARS:
        final_text = final_text[-_MAX_FINAL_TEXT_CHARS:]
    if final_text:
        parts.append("Final response: " + final_text)

    return "\n".join(parts), new_offset
