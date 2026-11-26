"""Gemini model selection with a fallback for retired models.

Google retires model IDs over time (gemini-2.5-flash began returning
404 "no longer available"). The configured GEMINI_MODEL is always tried
first; only when Gemini answers 404 for a model do we try the next one, so a
retired model in an old .env or Render setting does not break AI features.
Other errors (quota, overload, bad request) are raised unchanged.
"""
import logging
import os

from google.genai import errors

logger = logging.getLogger(__name__)

# Current stable models, cheapest first. Override with GEMINI_FALLBACK_MODELS
# (comma separated) when these are retired in turn.
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_FALLBACKS = ("gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash")


# configured model -> model that answered after it returned 404 (process-local),
# so later calls skip the known-retired model instead of paying a 404 each time.
_working = {}


class ModelConfigError(ValueError):
    """GEMINI_MODEL / GEMINI_FALLBACK_MODELS contains an invalid name."""


def _valid(name):
    return bool(name) and len(name) <= 80 and all(ch.isalnum() or ch in "-_." for ch in name)


def candidate_models():
    primary = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if not _valid(primary):
        raise ModelConfigError(primary)
    extra = os.getenv("GEMINI_FALLBACK_MODELS")
    fallbacks = [m.strip() for m in extra.split(",") if m.strip()] if extra is not None else list(DEFAULT_FALLBACKS)
    out = []
    for name in [primary, *fallbacks]:
        if not _valid(name):
            raise ModelConfigError(name)
        if name not in out:
            out.append(name)
    return out


def generate_content(client, **kwargs):
    """client.models.generate_content with retired-model fallback (404 only)."""
    models = candidate_models()
    known = _working.get(models[0])
    if known in models:
        models = [known] + [m for m in models if m != known]
    for i, name in enumerate(models):
        try:
            response = client.models.generate_content(model=name, **kwargs)
            if i > 0:
                _working[candidate_models()[0]] = name
            return response
        except errors.APIError as exc:
            if getattr(exc, "code", None) == 404 and i + 1 < len(models):
                logger.warning("Gemini model %s unavailable (404); trying %s", name, models[i + 1])
                continue
            raise
