import json

import httpx
import pytest

from ican.agent.journal import PaidJournal
from ican.agent.runtime import DeepSeekRuntime
from ican.agent.schema import AgentConfig
from ican.qa.runtime import ModelOutputTruncated


@pytest.mark.asyncio
async def test_tool_submission_uses_expanded_budget_and_classifies_truncation(
    monkeypatch, tmp_path
):
    import openai

    monkeypatch.setenv("ICAN_LLM_API_KEY", "test-only")
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200,
            json={
                "id": "truncated-tool-call",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-flash",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "length",
                        "message": {"role": "assistant", "content": None},
                    }
                ],
                "usage": {
                    "prompt_tokens": 2529,
                    "completion_tokens": 4096,
                    "total_tokens": 6625,
                },
            },
        )

    original = openai.AsyncOpenAI

    def client(**kwargs):
        return original(
            **kwargs,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

    monkeypatch.setattr(openai, "AsyncOpenAI", client)
    runtime = DeepSeekRuntime(
        tmp_path,
        AgentConfig(planner_max_tokens=4096),
        PaidJournal(tmp_path / "paid.jsonl"),
        "task-1",
    )
    tool = {
        "type": "function",
        "function": {
            "name": "submit_card",
            "description": "Submit one card",
            "parameters": {"type": "object", "properties": {}},
        },
    }

    with pytest.raises(ModelOutputTruncated):
        await runtime.request("answer", [{"role": "user", "content": "q"}], [tool])

    assert len(requests) == 1
    assert requests[0]["max_tokens"] == 4096
    assert runtime.records[0]["finish_reason"] == "length"
