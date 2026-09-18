from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from jsonschema import ValidationError, validate

from ican.qa.runtime import ModelTimeout, ModelUnavailable
from ican.retrieval.service import IndexUnavailable

from .corpus import AgentCorpus
from .journal import PaidJournal
from .prompts import PLANNER_SYSTEM, WORKFLOW_PLANNER_SYSTEM
from .runtime import DeepSeekRuntime
from .schema import (
    AgentConfig,
    AgentResponse,
    AgentUsage,
    BudgetExhausted,
    ToolInputError,
)
from .workflow import INVESTIGATION_TOOLS, draft_messages, submission_tool_schema


class AgentService:
    def __init__(
        self,
        root: Path,
        index_config,
        evidence_service,
        config=None,
        corpus_factory=None,
        runtime_factory=None,
        journal=None,
        research_service=None,
    ):
        self.root, self.index_config, self.evidence_service = (
            Path(root),
            index_config,
            evidence_service,
        )
        config_path = self.root / "configs/agent/v2.json"
        if not config_path.exists():
            config_path = self.root / "configs/agent/v1.json"
        self.config = config or AgentConfig.model_validate_json(
            config_path.read_text(encoding="utf-8")
        )
        self.corpus_factory = corpus_factory or AgentCorpus
        self.runtime_factory = runtime_factory or DeepSeekRuntime
        self.task_directory = (
            self.root
            / "data/processed/agent"
            / ("p4-v3" if self.config.workflow_mode == "verified" else "p4-v1")
        )
        self.journal = journal or PaidJournal(
            self.task_directory / "paid-journal.jsonl",
            32 if self.config.workflow_mode == "verified" else 40,
        )
        if research_service is None:
            from ican.research.service import ResearchService

            research_service = ResearchService(
                self.root, self.index_config, self.evidence_service
            )
        self.research_service = research_service

    async def run(self, request):
        from aviary.core import ToolCall, ToolRequestMessage

        from .environment import DomainEnvironment

        if "strategy" not in request.model_fields_set and request.collection.startswith(
            "qasper_"
        ):
            request = request.model_copy(update={"strategy": "dense"})

        task_id = uuid4().hex
        response = AgentResponse(
            task_id=task_id,
            status="failed",
            stop_reason="not_started",
            planner_model=self.config.planner_model,
            answer_model=self.config.answer_model,
            workflow_mode=self.config.workflow_mode,
        )
        runtime, env = None, None
        try:
            async with asyncio.timeout(self.config.task_timeout_seconds):
                corpus = await asyncio.to_thread(
                    self.corpus_factory,
                    self.root,
                    self.index_config,
                    self.evidence_service,
                    request,
                )
                response.index_fingerprint = corpus.fingerprint
                runtime = self.runtime_factory(
                    self.root, self.config, self.journal, task_id
                )
                env = DomainEnvironment(
                    corpus, request, runtime, self.config, self.research_service
                )
                await env.reset()
                tools = [
                    t.model_dump(by_alias=True, exclude_none=True) for t in env.tools
                ]
                verified = self.config.workflow_mode == "verified"
                if verified:
                    tools = [
                        t for t in tools if t["function"]["name"] in INVESTIGATION_TOOLS
                    ]
                for tool in tools:
                    if tool["function"]["name"] == "submit_claims":
                        tool["function"]["parameters"] = submission_tool_schema()
                    tool["function"]["parameters"]["additionalProperties"] = False
                schemas = {
                    t["function"]["name"]: t["function"]["parameters"] for t in tools
                }
                messages = [
                    {
                        "role": "system",
                        "content": WORKFLOW_PLANNER_SYSTEM
                        if verified
                        else PLANNER_SYSTEM,
                    },
                    {
                        "role": "user",
                        "content": request.query
                        + "\n范围："
                        + json.dumps(
                            {
                                "collection": request.collection,
                                "family": corpus.family,
                                "filters": request.filters.model_dump(),
                                "recommended_strategy": request.strategy,
                                "user_overrides": request.user_overrides.model_dump(),
                                "planner_steps": self.config.max_planner_calls,
                                "tool_budget": self.config.max_tool_calls,
                                "required_claim_kinds": request.required_claim_kinds,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ]
                cache, tool_calls, repeats = {}, 0, 0
                for turn in range(self.config.max_planner_calls):
                    finalization = turn + 1 == self.config.max_planner_calls and (
                        verified or bool(env.evidence_pool)
                    )
                    final_tool = "submit_claims" if verified else "gen_answer"
                    available_tools = (
                        [t for t in tools if t["function"]["name"] == final_tool]
                        if finalization
                        else tools
                    )
                    if finalization:
                        messages.append(
                            {
                                "role": "system",
                                "content": (
                                    "This is the reserved submission turn. Only submit_claims is available: select retained evidence and typed claims, including required_claim_kinds. The program verifies them before one answer. No further investigation or retry is allowed."
                                    if verified
                                    else "This is the reserved finalization turn within the existing budget. Only gen_answer is available: choose existing evidence IDs and report any missing support. No further investigation or automatic answer will follow."
                                ),
                            }
                        )
                    available_names = {t["function"]["name"] for t in available_tools}
                    planning_messages = (
                        draft_messages(request, env.evidence_pool, env.artifacts)
                        if verified and finalization
                        else messages
                    )
                    action = await runtime.plan(planning_messages, available_tools)
                    if (
                        not isinstance(action, dict)
                        or action.get("role") != "assistant"
                    ):
                        raise ToolInputError("Planner returned an invalid action")
                    calls = action.get("tool_calls", [])
                    if not isinstance(calls, list) or any(
                        not isinstance(call, dict)
                        or not isinstance(call.get("id"), str)
                        or not 1 <= len(call["id"]) <= 128
                        or call.get("type") != "function"
                        or not isinstance(call.get("function"), dict)
                        or not isinstance(call["function"].get("name"), str)
                        or not 1 <= len(call["function"]["name"]) <= 64
                        or not isinstance(call["function"].get("arguments"), str)
                        or len(call["function"]["arguments"]) > 16000
                        for call in calls
                    ):
                        raise ToolInputError("Planner returned a malformed tool call")
                    if not 1 <= len(calls) <= 3 or len(
                        {c.get("id") for c in calls}
                    ) != len(calls):
                        raise ToolInputError("Planner returned an invalid tool batch")
                    messages.append(
                        {
                            k: action[k]
                            for k in ["role", "content", "tool_calls"]
                            if k in action
                        }
                    )
                    response.trajectory.append(
                        {"event": "planner", "turn": turn + 1, "action": action}
                    )
                    for call in calls:
                        if tool_calls >= self.config.max_tool_calls:
                            raise BudgetExhausted("Task tool-call limit reached")
                        tool_calls += 1
                        name = call["function"]["name"]
                        try:
                            arguments = json.loads(call["function"]["arguments"])
                            if name not in available_names:
                                raise ToolInputError("Unknown tool name")
                            validate(arguments, schemas[name])
                            key = (
                                name
                                + ":"
                                + json.dumps(
                                    arguments, sort_keys=True, ensure_ascii=False
                                )
                            )
                            if key in cache:
                                result = cache[key]
                                repeats += 1
                                cached = True
                            else:
                                native = ToolCall.from_name(
                                    name, id=call["id"], **arguments
                                )
                                output, _, _, _ = await env.step(
                                    ToolRequestMessage(tool_calls=[native])
                                )
                                result = output[0].content
                                cache[key] = result
                                repeats = 0
                                cached = False
                        except (
                            json.JSONDecodeError,
                            ValidationError,
                            ToolInputError,
                            TypeError,
                        ):
                            result = json.dumps(
                                {"error": "Invalid tool name, JSON or arguments"}
                            )
                            cached = False
                            repeats += 1
                        response.trajectory.append(
                            {
                                "event": "tool",
                                "name": name,
                                "tool_call_id": call["id"],
                                "result": result,
                                "cached": cached,
                            }
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call["id"],
                                "content": result,
                            }
                        )
                        if env.fatal_error:
                            raise ToolInputError(env.fatal_error)
                        if getattr(runtime, "budget_exhausted", False):
                            raise BudgetExhausted("Cumulative paid-call limit reached")
                        if env.answer_error:
                            raise env.answer_error
                        if env.answer_response is not None:
                            response.answer = env.answer_response
                            if response.answer.status == "insufficient_evidence":
                                response.status = "insufficient_evidence"
                            elif response.answer.status == "citation_invalid":
                                response.status = "failed"
                            elif (
                                verified and response.answer.status == "review_required"
                            ):
                                response.status = "review_required"
                            else:
                                response.status = "completed"
                            response.stop_reason = "final_answer_generated"
                            await env.complete(
                                response.answer.status == "answered", env.state
                            )
                            break
                        if env.answer_attempted:
                            response.status, response.stop_reason = (
                                "failed",
                                "answer_attempt_failed_no_retry",
                            )
                            break
                        if repeats >= 2:
                            response.status, response.stop_reason = (
                                "no_progress",
                                "repeated_or_invalid_actions",
                            )
                            break
                    if response.stop_reason != "not_started":
                        break
                    messages.append(
                        {
                            "role": "system",
                            "content": json.dumps(
                                {
                                    "remaining_planner_calls": self.config.max_planner_calls
                                    - turn
                                    - 1,
                                    "remaining_tool_calls": self.config.max_tool_calls
                                    - tool_calls,
                                    "instruction": (
                                        f"The next turn is the last planner call. Use {final_tool} with retained evidence and explicitly state missing information."
                                        if turn + 2 == self.config.max_planner_calls
                                        else f"Reserve one tool call for {final_tool}; stop investigating once necessary evidence is available."
                                    ),
                                }
                            ),
                        }
                    )
                else:
                    response.status, response.stop_reason = (
                        "budget_exhausted",
                        "planner_step_limit_no_automatic_answer",
                    )
        except BudgetExhausted:
            response.status, response.stop_reason = (
                "budget_exhausted",
                "paid_or_tool_budget_exhausted",
            )
        except (TimeoutError, ModelTimeout):
            response.status, response.stop_reason = (
                "timed_out",
                "task_or_model_timeout_no_retry",
            )
        except (ModelUnavailable, IndexUnavailable, ToolInputError):
            response.status, response.stop_reason = (
                "failed",
                "model_index_or_tool_validation_failed",
            )
        finally:
            if env is not None:
                response.artifacts = env.artifacts
                response.workflow_stages = env.workflow_stages
            if runtime is not None:
                records = runtime.records
                response.usage = AgentUsage(
                    paid_calls=len(records),
                    planner_calls=sum(r["role"] == "planner" for r in records),
                    answer_calls=sum(r["role"] == "answer" for r in records),
                    prompt_tokens=sum(
                        (r["usage"] or {}).get("prompt_tokens", 0) for r in records
                    ),
                    completion_tokens=sum(
                        (r["usage"] or {}).get("completion_tokens", 0) for r in records
                    ),
                    usage_missing_calls=sum(r["usage"] is None for r in records),
                )
            directory = self.task_directory / "tasks"
            directory.mkdir(parents=True, exist_ok=True)
            record = {
                "request": request.model_dump(),
                "response": response.model_dump(),
                "raw_answer": env.raw_answer if env else None,
                "model_calls": runtime.records if runtime else [],
                "paperqa_tool_history": env.state.session.tool_history
                if env and hasattr(env, "state")
                else [],
                "agent_config": self.config.model_dump(),
                "source_sha256": {
                    p.relative_to(self.root).as_posix(): hashlib.sha256(
                        p.read_bytes()
                    ).hexdigest()
                    for p in [
                        *sorted((self.root / "ican/agent").glob("*.py")),
                        *sorted((self.root / "ican/qa").glob("*.py")),
                        *sorted((self.root / "ican/research").glob("*.py")),
                    ]
                },
            }
            (directory / f"{task_id}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return response
