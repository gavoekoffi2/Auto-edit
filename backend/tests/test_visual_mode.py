"""Visual-mode decision + image-error classification + fallback metadata.

Pure-Python: proves credit_saver NEVER attempts a paid image call, and that
auto_fallback / ai_broll degrade cleanly (never blocking the render).
"""
import pytest

from app.autoedit_engine import genimg
from app.autoedit_engine.pipeline import plan_visual_mode
from app.processing.pipeline_v2 import resolve_visual_mode


# --------------------------------------------------------------------------- #
# plan_visual_mode — the gate that decides if the paid API may run
# --------------------------------------------------------------------------- #
def test_credit_saver_never_attempts_even_with_key():
    attempt, reason = plan_visual_mode(
        "credit_saver", do_broll=True, have_key=True, disable_paid_images=False)
    assert attempt is False
    assert reason is None  # explicit choice, not a fallback


def test_ai_broll_attempts_when_possible():
    attempt, reason = plan_visual_mode(
        "ai_broll", do_broll=True, have_key=True, disable_paid_images=False)
    assert attempt is True
    assert reason is None


def test_auto_fallback_attempts_when_possible():
    attempt, reason = plan_visual_mode(
        "auto_fallback", do_broll=True, have_key=True, disable_paid_images=False)
    assert attempt is True


def test_missing_key_falls_back_without_attempt():
    attempt, reason = plan_visual_mode(
        "auto_fallback", do_broll=True, have_key=False, disable_paid_images=False)
    assert attempt is False
    assert reason == "missing_api_key"


def test_disable_flag_blocks_all_paid_generation():
    for mode in ("ai_broll", "auto_fallback"):
        attempt, reason = plan_visual_mode(
            mode, do_broll=True, have_key=True, disable_paid_images=True)
        assert attempt is False
        assert reason == "disabled"


def test_broll_toggle_off_falls_back():
    attempt, reason = plan_visual_mode(
        "ai_broll", do_broll=False, have_key=True, disable_paid_images=False)
    assert attempt is False
    assert reason == "broll_disabled"


# --------------------------------------------------------------------------- #
# classify_image_error — maps provider failures to canonical reasons
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("message,expected", [
    ("OPENROUTER_API_KEY is required for image generation", "missing_api_key"),
    ("OpenRouter 402: insufficient credits, add funds", "insufficient_credits"),
    ("HTTP 402 Payment Required", "payment_required"),
    ("OpenRouter 429: rate limit exceeded", "rate_limited"),
    ("too many requests, slow down", "rate_limited"),
    ("monthly quota exceeded for your account", "quota_exceeded"),
    ("request timed out after 180s", "timeout"),
    ("OpenRouter 503: provider unavailable", "provider_unavailable"),
    ("could not connect to host", "provider_unavailable"),
    ("some unknown teapot error", "image_generation_failed"),
])
def test_classify_image_error(message, expected):
    assert genimg.classify_image_error(message) == expected
    assert genimg.classify_image_error(RuntimeError(message)) == expected


def test_all_classified_reasons_are_canonical():
    for msg in ["insufficient credits", "402", "429", "quota", "timeout",
                "unavailable", "missing key", "weird"]:
        assert genimg.classify_image_error(msg) in genimg.FALLBACK_REASONS


# --------------------------------------------------------------------------- #
# resolve_visual_mode — old jobs are NOT forced to the new mode
# --------------------------------------------------------------------------- #
def test_explicit_option_wins():
    assert resolve_visual_mode({"visual_mode": "ai_broll"}, "credit_saver") == "ai_broll"


def test_old_job_without_visual_mode_uses_default_not_forced():
    # A historical job (no visual_mode stored) keeps the configured default,
    # it is NOT silently forced into credit_saver.
    assert resolve_visual_mode({}, "auto_fallback") == "auto_fallback"
    assert resolve_visual_mode({"ai_broll": True}, "ai_broll") == "ai_broll"


def test_invalid_value_falls_back_to_default():
    assert resolve_visual_mode({"visual_mode": "nope"}, "auto_fallback") == "auto_fallback"
