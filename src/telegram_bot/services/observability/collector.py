import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from telegram_bot.core.database import AsyncSessionLocal
from telegram_bot.models.agents_trace import AgentTrace
from telegram_bot.models.llm_event import LLMEvent
from telegram_bot.services.observability.cost_service import estimate_cost_usd

logger = logging.getLogger(__name__)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def safe_error(exc:BaseException) -> tuple[str, str]:
    return type(exc).__name__[:100], "Execution failed"

def extract_usage(response:Any) -> tuple[int | None, int | None]:
    '''
    read toke counts from common Langchain/OpenAI response shapes.
    
    '''

    candidates = []
    # getattr ??
    usage_metadata = getattr(response, "usage_metadata", None)

    if isinstance(usage_metadata, dict):
        candidates.append(usage_metadata)

    response_metadata = getattr(response, "response_metadata", None)
    if isinstance(response_metadata, dict):
        candidates.append(response_metadata.get("token_usage", {}))
        candidates.append(
            response_metadata.get("usage", {})
        )

    for usage in candidates:
        if not isinstance(usage, dict):
            continue
        
        input_tokens = usage.get(
            "input_tokens",
            usage.get("prompt_tokens"),
        )

        output_tokens = usage.get(
            "output_tokens",
            usage.get("completion_tokens"),
        )

        if input_tokens is not None or output_tokens is not None:
            return (
                int(input_tokens) if input_tokens is not None else None,
                int(output_tokens) if output_tokens is not None else None,
            )

    return None, None

class ObservabilityCollector(AsyncCallbackHandler):
    '''
    Collects events for one agent execution.

    Events are held in memory during the run and persisted together after execution.The callback never 
    stores raw prompts or outputs
    
    
    '''

    def __init__(self, user_id:int) -> None:
        self.user_id = user_id
        self.trace_id = str(uuid4())
        self.started_at = utc_now()
        self._started_clock = time.perf_counter()
        self.events: list[dict[str, Any]] = []
        self._run_started: dict[str, float] = {}
        self._run_event_index: dict[str, int] = {}
        self._llm_usage: dict[str, tuple[int | None, int | None]] = {}
        self.status = "running"
        self.error_type: str | None = None
        self.error_message: str | None = None

    def _start_event(
        self, 
        run_id:Any,
        event_type:str,
        name:str,
        provider:str | None = None,
        model_name:str | None = None
    ) -> None:
        run_key = str(run_id)
        self._run_started[run_key] = time.perf_counter()

        event = {
            "id": str(uuid4()),
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "event_type": event_type,
            "name": name[:200],
            "provider": provider,
            "model_name": model_name,
            "status": "running",
            "started_at": utc_now(),
            "finished_at": None,
            "latency_ms": None,
            "input_tokens": None,
            "output_tokens": None,
            "estimated_cost_usd": None,
            "error_type": None,
            "error_message": None,
            "metadata_json": {},
        }

        self._run_event_index[run_key] = len(self.events)
        self.events.append(event)

    def _finish_event(
        self, 
        run_id:Any,
        status:str,
        error:BaseException | None = None
    )-> None:

        run_key = str(run_id)
        index = self._run_event_index.get(run_key)
        if index is None:
            return

        event = self.events[index]
        started = self._run_started.get(run_key)

        event["status"] = status
        event["finished_at"] = utc_now()

        if started is not None:
            event["latency_ms"] = int(
                (time.perf_counter() - started) * 1000
            )

        if error is not None:
            event["error_type"], event["error_message"] = (
                safe_error(error)
            )
        
    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        name = serialized.get("name", "llm")
        kwargs_metadata = kwargs.get("metadata") or {}
        model_name = (
            kwargs_metadata.get("ls_model_name")
            or kwargs_metadata.get("model_name")
            or name
        )

        self._start_event(
            run_id,
            event_type="llm",
            name=str(name),
            provider="openai",
            model_name=str(model_name) if model_name else None,
        )

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        kwargs_metadata = kwargs.get("metadata") or {}
        invocation_params = kwargs.get("invocation_params") or {}

        model_name = (
            invocation_params.get("model")
            or invocation_params.get("model_name")
            or kwargs_metadata.get("ls_model_name")
            or "unknown"
        )

        self._start_event(
            run_id,
            event_type="llm",
            name="chat_model",
            provider="openai",
            model_name=str(model_name),
        )

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        input_tokens, output_tokens = extract_usage(response)

        self._finish_event(run_id, "success")

        index = self._run_event_index.get(str(run_id))
        if index is not None:
            event = self.events[index]
            event["input_tokens"] = input_tokens
            event["output_tokens"] = output_tokens
            event["estimated_cost_usd"] = estimate_cost_usd(
                event["model_name"],
                input_tokens,
                output_tokens,
            )

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        self._finish_event(run_id, "failed", error)

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        self._start_event(
            run_id,
            event_type="tool",
            name=str(serialized.get("name", "tool")),
        )

    async def on_tool_end(
        self,
        output: Any,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        self._finish_event(run_id, "success")

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        self._finish_event(run_id, "failed", error)

    async def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        # This hook may fire for an inner chain as well as the root
        # agent. Record it as a trace failure only when the caller
        # marks the root invocation as failed.
        pass

    def mark_failed(self, exc: BaseException) -> None:
        self.status = "failed"
        self.error_type, self.error_message = safe_error(exc)

    def mark_success(self) -> None:
        self.status = "success"

    async def persist(self) -> None:
        finished_at = utc_now()
        latency_ms = int(
            (time.perf_counter() - self._started_clock) * 1000
        )

        try:
            async with AsyncSessionLocal() as db:
                trace = AgentTrace(
                    id=self.trace_id,
                    user_id=self.user_id,
                    status=self.status,
                    started_at=self.started_at,
                    finished_at=finished_at,
                    latency_ms=latency_ms,
                    event_count=len(self.events),
                    error_type=self.error_type,
                    error_message=self.error_message,
                )
                db.add(trace)

                for item in self.events:
                    # Avoid persisting callback objects, prompts,
                    # tool inputs, or model outputs.
                    db.add(LLMEvent(**item))

                await db.commit()

        except Exception:
            # Observability must not replace the agent's actual
            # response or hide its original exception.
            logger.exception(
                "Could not persist observability trace %s",
                self.trace_id,
            )

