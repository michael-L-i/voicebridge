import re

from mlx_lm import generate, load

from voicebridge.config import SummarizerConfig

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_ALREADY_SHORT_MAX_SENTENCES = 2
_ALREADY_SHORT_MAX_CHARS = 160

NARRATION_SYSTEM_PROMPT = (
    "You narrate what a coding AI just did, out loud, to a busy engineer who wasn't watching. "
    "Talk like you would to a coworker walking by your desk -- not a status report. "
    "Exactly one sentence, sometimes two if there is a decision the engineer needs to make. "
    'Never say "the assistant" or "the changes were committed" -- just say what happened, '
    'plainly, the way a person would. Skip filler like "no issues were found" unless there '
    "genuinely is a problem to flag.\n\n"
    "Examples:\n"
    '- "Fixed the null token bug in auth and tests are green."\n'
    '- "Refactored the retry logic in the API client -- should be a lot less flaky now."\n'
    '- "Couldn\'t get the tests passing, looks like a real bug in the rate limiter -- want me to keep digging?"'
)


class Summarizer:
    def __init__(self, config: SummarizerConfig):
        self.config = config
        self._model = None
        self._tokenizer = None

    def load(self) -> "Summarizer":
        if self._model is None:
            self._model, self._tokenizer = load(self.config.model)
        return self

    def summarize(self, delta_text: str, prior_summaries: list[str] | None = None) -> str:
        self.load()
        prior = ""
        if prior_summaries:
            prior = "Earlier in this session you said: " + " / ".join(prior_summaries) + "\n\n"
        messages = [
            {"role": "system", "content": NARRATION_SYSTEM_PROMPT},
            {"role": "user", "content": f"{prior}Here's what just happened:\n\n{delta_text}"},
        ]
        prompt = self._tokenizer.apply_chat_template(messages, add_generation_prompt=True)
        text = generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=self.config.max_tokens,
            verbose=False,
        )
        return text.strip()


def is_already_short(text: str) -> bool:
    """Heuristic for voice_speak: skip the compression LLM call entirely when
    the caller already handed us something spoken-sized, to save latency on
    text that doesn't need help."""
    text = text.strip()
    if not text:
        return True
    if len(text) > _ALREADY_SHORT_MAX_CHARS:
        return False
    sentence_count = len([s for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()])
    return sentence_count <= _ALREADY_SHORT_MAX_SENTENCES
