"""Upstream compatibility shims.

mlx-lm and mlx-audio have mutually exclusive dependency floors as of the
versions pinned in pyproject.toml: mlx-audio requires huggingface_hub>=1.0
(which pulls transformers>=5), but importing mlx_lm under transformers>=5
crashes -- its tokenizer_utils.py registers a bare string as a tokenizer
config_class (`AutoTokenizer.register("NewlineTokenizer", ...)`), which
transformers>=5's registry now rejects while inspecting `key.__module__`.

No version combination satisfies both packages at once, so this patches the
one broken call instead of pinning either package down. Losing that
registration only removes an optional "NewlineTokenizer" alias in mlx_lm --
it has no effect on loading standard instruct models (Qwen2.5-3B-Instruct,
Llama-3.2-3B-Instruct, etc).
"""


def patch_mlx_lm_transformers_compat() -> None:
    try:
        from transformers.models.auto.tokenization_auto import AutoTokenizer
    except ImportError:
        return

    original_register = AutoTokenizer.register

    def tolerant_register(config_class, slow_tokenizer_class=None, fast_tokenizer_class=None, exist_ok=False):
        try:
            return original_register(
                config_class,
                slow_tokenizer_class=slow_tokenizer_class,
                fast_tokenizer_class=fast_tokenizer_class,
                exist_ok=exist_ok,
            )
        except AttributeError:
            return None

    AutoTokenizer.register = tolerant_register
