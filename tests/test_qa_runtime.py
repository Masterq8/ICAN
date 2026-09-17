import json

import httpx
import pytest

from ican.qa.runtime import ModelUnavailable, OpenAICompatibleModel
from ican.qa.schema import QAConfig


@pytest.mark.parametrize("status", [200, 429, 500])
@pytest.mark.asyncio
async def test_sdk_dispatch_has_one_attempt_and_bounded_non_thinking_output(
    monkeypatch, tmp_path, status
):
    import openai
    from aviary.core import Message

    for name, value in {
        "ICAN_LLM_PROVIDER": "openai",
        "ICAN_LLM_MODEL": "deepseek-flash",
        "ICAN_LLM_BASE_URL": "https://api.deepseek.com",
        "ICAN_LLM_API_KEY": "test-only",
    }.items():
        monkeypatch.setenv(name, value)
    requests = []

    def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        assert body["max_tokens"] == 1536
        assert body["thinking"] == {"type": "disabled"}
        if status != 200:
            return httpx.Response(
                status, json={"error": {"message": "secret-provider-detail"}}
            )
        return httpx.Response(
            200,
            json={
                "id": "fake",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-flash",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "fact",
                            "reasoning_content": "PRIVATE",
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "total_tokens": 30,
                },
            },
        )

    original = openai.AsyncOpenAI

    def client(**kwargs):
        assert kwargs["max_retries"] == 0
        return original(
            **kwargs,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

    monkeypatch.setattr(openai, "AsyncOpenAI", client)
    model = OpenAICompatibleModel(tmp_path, QAConfig())
    if status == 200:
        result = await model.call_single(
            messages=[Message(role="user", content="q")], name="answer"
        )
        assert result.text == "fact"
        assert result.reasoning_content is None
    else:
        with pytest.raises(ModelUnavailable, match="Generation service is unavailable"):
            await model.call_single(
                messages=[Message(role="user", content="q")], name="answer"
            )
    assert model.calls == len(requests) == 1
