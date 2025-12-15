import pytest
import router


class DummyProvider:
    def __init__(self, should_fail: bool):
        self.should_fail = should_fail

    def chat(self, messages):
        if self.should_fail:
            raise RuntimeError("fail")
        return "ok"


def test_fallback_success(monkeypatch):
    monkeypatch.setattr(
        router,
        "PROVIDERS",
        {
            "bad": DummyProvider(True),
            "good": DummyProvider(False),
        },
    )
    monkeypatch.setattr(
        router,
        "SPEC_RULES",
        {"spec": {"outline": ["bad", "good"]}},
    )

    assert router.run("spec", "outline", "x") == "ok"


def test_all_fail(monkeypatch):
    monkeypatch.setattr(
        router,
        "PROVIDERS",
        {"bad": DummyProvider(True)},
    )
    monkeypatch.setattr(
        router,
        "SPEC_RULES",
        {"spec": {"outline": ["bad"]}},
    )

    with pytest.raises(RuntimeError):
        router.run("spec", "outline", "x")
