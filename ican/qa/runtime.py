from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from ican.qa.schema import QAConfig


class ModelUnavailable(Exception):
    """The generation service is missing or failed; no sensitive details escape."""


class ModelTimeout(Exception):
    """The single generation attempt exceeded its time budget."""


class OpenAICompatibleModel:
    """PaperQA2 call_single bridge with explicit SDK retries=0 and one call.

    Uses fhlmi's public LLMResult contract, without LiteLLM routing or cost guesses.
    The instance is created per QA request and never shared across requests.
    """

    def __init__(self, root: Path, config: QAConfig):
        load_dotenv(root / ".env", override=False)
        self.name = os.environ.get("ICAN_LLM_MODEL", "").strip()
        self.base_url = os.environ.get("ICAN_LLM_BASE_URL", "").strip()
        provider = os.environ.get("ICAN_LLM_PROVIDER", "").strip()
        self._key = os.environ.get("ICAN_LLM_API_KEY", "").strip()
        if (
            provider != "openai"
            or not self.name
            or not self._key
            or urlparse(self.base_url).scheme != "https"
            or not urlparse(self.base_url).hostname
            or urlparse(self.base_url).username
            or urlparse(self.base_url).query
        ):
            raise ModelUnavailable("Generation configuration is unavailable")
        self.config = config
        self.calls = 0

    async def call_single(self, *, messages, callbacks=None, name=None, **kwargs):
        import httpx
        from lmi import LLMResult
        from openai import APIError, APITimeoutError, AsyncOpenAI

        if self.calls or name != "answer":
            raise ModelUnavailable("Only one answer generation call is allowed")
        self.calls += 1
        extra = {}
        if urlparse(self.base_url).hostname == "api.deepseek.com":
            extra = {"thinking": {"type": "disabled"}}
        try:
            async with AsyncOpenAI(
                api_key=self._key,
                base_url=self.base_url,
                timeout=self.config.timeout_seconds,
                max_retries=0,
            ) as client:
                response = await client.chat.completions.create(
                    model=self.name,
                    messages=[{"role": m.role, "content": m.content} for m in messages],
                    max_tokens=self.config.max_output_tokens,
                    extra_body=extra,
                )
        except APITimeoutError:
            raise ModelTimeout("Generation timed out") from None
        except (APIError, httpx.HTTPError, ValueError):
            raise ModelUnavailable("Generation service is unavailable") from None
        if (
            not response.choices
            or not response.choices[0].message.content
            or response.choices[0].finish_reason != "stop"
        ):
            raise ModelUnavailable("Generation did not return a complete text answer")
        usage = response.usage
        return LLMResult(
            text=response.choices[0].message.content,
            model=self.name,
            prompt_count=usage.prompt_tokens if usage else 0,
            completion_count=usage.completion_tokens if usage else 0,
            finish_reason=response.choices[0].finish_reason,
        )
