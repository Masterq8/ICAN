from __future__ import annotations

import os

from dotenv import load_dotenv

from ican.qa.runtime import ModelTimeout, ModelUnavailable

from .schema import BudgetExhausted


def tool_options(tools):
    if not tools:
        return {}
    choice = (
        {"type": "function", "function": {"name": tools[0]["function"]["name"]}}
        if len(tools) == 1
        else "required"
    )
    return {"tools": tools, "tool_choice": choice}


class DeepSeekRuntime:
    def __init__(self, root, config, journal, task_id):
        load_dotenv(root / ".env", override=False)
        self._key = os.environ.get("ICAN_LLM_API_KEY", "").strip()
        if not self._key:
            raise ModelUnavailable("Agent generation configuration is unavailable")
        self.config, self.journal, self.task_id = config, journal, task_id
        self.records = []
        self.budget_exhausted = False

    async def request(self, role, messages, tools=None):
        import httpx
        from openai import APIError, APITimeoutError, AsyncOpenAI

        model = (
            self.config.planner_model if role == "planner" else self.config.answer_model
        )
        try:
            call_id = self.journal.reserve(self.task_id, role, model)
        except BudgetExhausted:
            self.budget_exhausted = True
            raise
        record = {
            "role": role,
            "requested_model": model,
            "call_id": call_id,
            "usage": None,
            "status": "started",
        }
        self.records.append(record)
        options = tool_options(tools)
        try:
            async with AsyncOpenAI(
                api_key=self._key,
                base_url="https://api.deepseek.com",
                timeout=self.config.model_timeout_seconds,
                max_retries=0,
            ) as client:
                result = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=self.config.planner_max_tokens if tools else 1536,
                    extra_body={"thinking": {"type": "disabled"}},
                    **options,
                )
            record["response_model"] = result.model
            record["usage"] = result.usage.model_dump() if result.usage else None
            if not result.choices or result.choices[0].finish_reason not in {
                "stop",
                "tool_calls",
            }:
                raise ModelUnavailable("Agent model returned an incomplete response")
            message = result.choices[0].message
            if (tools and not message.tool_calls) or (
                not tools and not message.content
            ):
                raise ModelUnavailable(
                    "Agent model did not return the expected response type"
                )
            record["status"] = "completed"
            return {
                k: v
                for k, v in message.model_dump(exclude_none=True).items()
                if k in {"role", "content", "tool_calls"}
            }
        except APITimeoutError:
            record["status"] = "error"
            raise ModelTimeout("Agent model request timed out") from None
        except (APIError, httpx.HTTPError, ValueError):
            record["status"] = "error"
            raise ModelUnavailable("Agent model service is unavailable") from None
        except BaseException:
            record["status"] = "error"
            raise
        finally:
            self.journal.finish(
                call_id,
                status=record["status"],
                response_model=record.get("response_model"),
                usage=record["usage"],
            )

    async def plan(self, messages, tools):
        return await self.request("planner", messages, tools)


class AgentAnswerModel:
    def __init__(self, runtime):
        self.runtime = runtime
        self.name = runtime.config.answer_model

    async def call_single(self, *, messages, name=None, **kwargs):
        from lmi import LLMResult

        if name != "answer":
            raise ModelUnavailable("Only explicit Agent answer calls are supported")
        message = await self.runtime.request(
            "answer", [{"role": m.role, "content": m.content} for m in messages]
        )
        usage = self.runtime.records[-1]["usage"] or {}
        return LLMResult(
            text=message["content"],
            model=self.name,
            prompt_count=usage.get("prompt_tokens", 0),
            completion_count=usage.get("completion_tokens", 0),
            finish_reason="stop",
        )
