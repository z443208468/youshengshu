from types import SimpleNamespace

from youshengshu.config import LMStudioConfig
from youshengshu.lmstudio_client import LMStudioClient


class FakeCompletions:
    def __init__(self):
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="译文")
                )
            ]
        )


def test_translate_omits_max_tokens_by_default():
    cfg = LMStudioConfig()
    client = LMStudioClient(cfg)
    client._resolved_model_id = "fake-model"

    fake_completions = FakeCompletions()
    client._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=fake_completions
        )
    )

    result = client.translate([{"role": "user", "content": "Hello"}])
    assert result == "译文"
    assert "max_tokens" not in fake_completions.last_kwargs


def test_translate_includes_max_tokens_only_when_explicit():
    cfg = LMStudioConfig()
    client = LMStudioClient(cfg)
    client._resolved_model_id = "fake-model"

    fake_completions = FakeCompletions()
    client._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=fake_completions
        )
    )

    client.translate([{"role": "user", "content": "Hello"}], max_tokens=123)
    assert fake_completions.last_kwargs["max_tokens"] == 123
