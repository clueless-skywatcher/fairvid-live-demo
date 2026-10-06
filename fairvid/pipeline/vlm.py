"""Vision-LLM frame/image description via Ollama (Gemma-3), with offline fallback.

This is the real version of the "Get Video Frame Description by Ollama" notebook
stage. It calls a locally running Ollama server with a Gemma-3 vision model using
the same prompt the notebook uses. If Ollama is not installed or not running
(e.g. during a presentation on a laptop without a GPU), it falls back to a short
offline description so the pipeline and the web app keep working.

Run Ollama once before the demo:
    curl -fsSL https://ollama.com/install.sh | sh
    ollama serve &
    ollama pull gemma3:4b        # 4b is fast enough for a live demo; 12b is sharper
"""

import os
from pathlib import Path

PROMPT = ("Describe a given image clearly and in detail so that a person who "
          "cannot see it can understand it.")


def _model_names(listed) -> list[str]:
    models = listed.get("models", []) if isinstance(listed, dict) else getattr(listed, "models", [])
    names = []
    for item in models:
        if isinstance(item, dict):
            names.append(item.get("model") or item.get("name") or "")
        else:
            names.append(getattr(item, "model", "") or getattr(item, "name", "") or "")
    return [name for name in names if name]


def ollama_available(model: str | None = None) -> bool:
    """True if the Ollama server is reachable and, when asked, has ``model``."""
    try:
        import ollama
        names = _model_names(ollama.list())
    except Exception:
        return False
    if model is None:
        return bool(names)
    return any(name == model or name.split(":")[0] == model for name in names)


def _offline_description(image_path: Path) -> str:
    """A safe canned description used when Ollama is unavailable."""
    name = Path(image_path).name.lower()
    if "diploma" in name:
        return ("A scanned diploma document on a plain background, with a centred "
                "institution name, a graduation heading, the candidate's name and "
                "the awarded degree.")
    if "transcript" in name:
        return ("A scanned academic transcript: a header with the institution and "
                "the candidate's name, followed by a table of subjects and grades.")
    return "A scanned document image containing printed text on a light background."


def _response_text(response) -> str:
    if isinstance(response, dict):
        text = response.get("response") or ""
    else:
        text = getattr(response, "response", None) or ""
    return str(text).strip()


def _generate(model: str, prompt: str, images: list | None = None):
    import ollama
    kwargs = {"model": model, "prompt": prompt, "options": {"temperature": 0}}
    if images:
        kwargs["images"] = images
    try:
        return ollama.generate(**kwargs)
    except Exception as exc:
        if "cuda" not in str(exc).lower() and "out of memory" not in str(exc).lower():
            raise
        kwargs["options"] = {"temperature": 0, "num_gpu": 0}
        return ollama.generate(**kwargs)


def describe_image(image_path, model: str | None = None, prompt: str = PROMPT) -> dict:
    """Describe an image. Returns {backend, model, text, ok}.

    Tries Ollama first; on any failure returns the offline description so the
    caller never breaks.
    """
    model = model or os.environ.get("FAIRVID_VLM_MODEL") or "moondream"
    image_path = str(image_path)
    try:
        text = _response_text(_generate(model, prompt, images=[image_path]))
        if text.startswith("!!!IMAGE!!!"):
            text = text[len("!!!IMAGE!!!"):].strip()
        if text:
            return {"backend": "ollama", "model": model, "text": text, "ok": True}
        raise RuntimeError(f"{model} returned an empty description")
    except Exception as e:
        return {"backend": "offline", "model": "stub", "ok": False,
                "error": str(e), "text": _offline_description(Path(image_path))}
