"""Offline test setup: a fake typesafe_sdk so tests never call Jev or need a key."""
import os, sys, types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

fake = types.ModuleType("typesafe_sdk")
for name in ("Choice", "Noul", "Score"):
    setattr(fake, name, lambda **kw: kw)


class FakeClient:
    """Returns whatever answers the current test sets on FakeClient.answers."""
    answers = None
    raise_error = None

    def __init__(self, **kw):
        pass

    def system_one(self, state, questions):
        if FakeClient.raise_error:
            raise FakeClient.raise_error
        a = FakeClient.answers
        ns = types.SimpleNamespace
        return ns(
            choices={"action_class": ns(choice=a["action_class"], confidence=a.get("action_confidence", 0.95))},
            scores={"severity": ns(score=a["severity"] * 3)},   # Jev returns a 0-3 level
            nouls={"matches_ticket": ns(noul=a["matches_ticket"]), "injection": ns(noul=a["injection"])},
        )


fake.TypeSafeClient = FakeClient
sys.modules["typesafe_sdk"] = fake
os.environ.setdefault("FLEETGUARD_DB", ":memory:")
