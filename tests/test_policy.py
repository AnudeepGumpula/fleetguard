import pytest
from conftest import FakeClient
import guard

SAFE = dict(action_class="single_change", severity=0.33, matches_ticket=0.95, injection=0.02)


def run(tool="reassign_device", n=1, **overrides):
    FakeClient.raise_error = None
    FakeClient.answers = {**SAFE, **overrides}
    return guard.check({"tool": tool, "args": {}, "ticket": "t", "requester_role": "teacher", "devices_affected": n})


def test_normal_reassignment_allowed():
    assert run()["decision"] == "allow"


def test_injection_blocked():
    r = run(tool="wipe_device", n=48, action_class="destructive", severity=1.0, matches_ticket=0.36, injection=0.97)
    assert r["decision"] == "block" and "inject" in r["reason"].lower()


def test_scope_overreach_asks():
    r = run(tool="reset_password", n=120, action_class="bulk_change", severity=0.96, matches_ticket=0.24)
    assert r["decision"] == "ask" and "beyond the ticket" in r["reason"]


def test_legit_single_wipe_needs_human():
    r = run(tool="wipe_device", action_class="destructive", severity=0.9, matches_ticket=0.95)
    assert r["decision"] == "ask"


def test_destructive_tool_list_overrides_jev_label():
    # Even if Jev calls it a single change, our code knows wipe_device is destructive.
    assert run(tool="wipe_device", action_class="single_change")["decision"] == "ask"


def test_bulk_without_mismatch_still_asks():
    assert run(tool="bulk_update_group", n=48, action_class="bulk_change", matches_ticket=0.9)["decision"] != "allow"


def test_low_confidence_asks():
    assert run(action_confidence=0.4)["decision"] == "ask"


def test_fail_closed_on_error():
    FakeClient.raise_error = RuntimeError("network down")
    r = guard.check({"tool": "reassign_device", "args": {}, "ticket": "t", "devices_affected": 1})
    FakeClient.raise_error = None
    assert r["decision"] == "block" and "failing closed" in r["reason"]


@pytest.mark.parametrize("key", ["injection", "matches_ticket"])
def test_thresholds_have_teeth(key, monkeypatch):
    # Raising the ask threshold for matches_ticket above 1 makes every call ask;
    # lowering the injection block threshold to 0 makes every call block.
    if key == "injection":
        monkeypatch.setitem(guard.POLICY["block"], "injection", 0.0)
        assert run()["decision"] == "block"
    else:
        monkeypatch.setitem(guard.POLICY["ask"], "matches_ticket", 1.01)
        assert run()["decision"] == "ask"
