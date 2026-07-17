"""Tests de non-régression des quotas fondateur et Enterprise."""
from types import SimpleNamespace

from app.services.plans import effective_video_duration_limit_s, rules_for, rules_for_user


def _user(**overrides):
    data = {
        "plan": "free",
        "subscription_expires_at": None,
        "is_super_admin": False,
        "video_duration_limit_s": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_enterprise_is_not_mapped_to_free_clips_limit():
    rules = rules_for("enterprise")
    assert rules.name == "enterprise"
    assert rules.clips_max_source_duration_s is None
    assert rules.max_video_duration_s is None
    assert rules.max_videos_per_month is None
    assert rules.max_concurrent_jobs is None


def test_super_admin_has_no_video_duration_limit_even_on_free_plan():
    user = _user(is_super_admin=True, video_duration_limit_s=60)
    assert effective_video_duration_limit_s(user, clips=False) is None
    assert effective_video_duration_limit_s(user, clips=True) is None
    founder_rules = rules_for_user(user)
    assert founder_rules.name == "enterprise"
    assert founder_rules.max_videos_per_month is None
    assert founder_rules.max_concurrent_jobs is None


def test_custom_account_duration_limit_overrides_plan():
    user = _user(plan="pro", video_duration_limit_s=7_200)
    assert effective_video_duration_limit_s(user, clips=False) == 7_200
    assert effective_video_duration_limit_s(user, clips=True) == 7_200


def test_zero_custom_duration_means_unlimited():
    user = _user(plan="free", video_duration_limit_s=0)
    assert effective_video_duration_limit_s(user, clips=False) is None
    assert effective_video_duration_limit_s(user, clips=True) is None


def test_account_without_custom_limit_uses_plan_defaults():
    free = _user(plan="free")
    pro = _user(plan="pro")
    assert effective_video_duration_limit_s(free, clips=False) == rules_for("free").max_video_duration_s
    assert effective_video_duration_limit_s(free, clips=True) == rules_for("free").clips_max_source_duration_s
    assert effective_video_duration_limit_s(pro, clips=False) == rules_for("pro").max_video_duration_s
