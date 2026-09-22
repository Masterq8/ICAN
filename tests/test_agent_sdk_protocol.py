"""Check the JSON that the installed OpenAI SDK actually sends."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from ican.agent.runtime import tool_options
from ican.agent.workflow import submission_tool_schema


@pytest.mark.asyncio
async def test_named_single_tool_reaches_sdk_request_body():
    seen = []

    def reply(request):
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "neutral-protocol",
                "object": "chat.completion",
                "created": 1,
                "model": "mock-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "submit_claims",
                                        "arguments": json.dumps(
                                            {
                                                "evidence_ids": ["chunk-neutral"],
                                                "claims": [
                                                    {
                                                        "statement": "neutral",
                                                        "kind": "inference",
                                                        "evidence_ids": [
                                                            "chunk-neutral"
                                                        ],
                                                    }
                                                ],
                                            }
                                        ),
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 3,
                    "total_tokens": 5,
                },
            },
        )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "submit_claims",
                "description": "Submit a neutral typed claim",
                "parameters": submission_tool_schema(),
            },
        }
    ]
    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(reply)) as http_client,
        AsyncOpenAI(
            api_key="mock-only",
            base_url="https://mock.invalid",
            http_client=http_client,
        ) as client,
    ):
        response = await client.chat.completions.create(
            model="mock-model",
            messages=[{"role": "user", "content": "neutral protocol"}],
            max_tokens=64,
            extra_body={"thinking": {"type": "disabled"}},
            **tool_options(tools),
        )
    assert len(seen) == 1
    assert seen[0]["tool_choice"] == {
        "type": "function",
        "function": {"name": "submit_claims"},
    }
    assert seen[0]["tools"] == tools
    assert seen[0]["thinking"] == {"type": "disabled"}
    assert response.choices[0].message.tool_calls[0].function.name == "submit_claims"
