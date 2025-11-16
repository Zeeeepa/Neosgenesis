"""Orchestrated workflow for feeding metacognitive context into capability upgrades."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Mapping, Protocol

from context.Context_Orchestrator import (
    ContextOrchestrator,
    ContextPackage,
    ContextRequest,
    StageDependency,
)
from context.envelope import AgentEnvelope, coerce_envelope, extract_payload_summary
from model._model_response import ChatResponse


class StageOneAgent(Protocol):
    """Protocol describing the minimal interface required from the stage-1 agent."""

    agent_name: str
    agent_stage: str
    agent_function: str

    async def analyze(self, **kwargs: Any) -> ChatResponse:  # pragma: no cover - interface definition
        ...


class CapabilityUpgradeAgentProtocol(Protocol):
    """Protocol describing the minimal interface required from the capability agent."""

    agent_name: str
    agent_stage: str
    agent_function: str

    async def evaluate(self, **kwargs: Any) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        ...  # pragma: no cover - interface definition


@dataclass(slots=True)
class CapabilityUpgradeWorkflowResult:
    """Container describing the outcome of a capability upgrade workflow run."""

    stage_one_response: ChatResponse
    context_package: ContextPackage
    capability_response: ChatResponse | AsyncGenerator[ChatResponse, None]


class CapabilityUpgradeWorkflow:
    """High-level workflow that routes stage-1 outputs into the capability upgrade agent.

    The workflow performs three steps:

    1. 调用阶段一 Agent (`MetacognitiveAnalysisAgent`) 并接收其信封化上下文；
    2. 将信封写入 `ContextOrchestrator`，根据依赖声明进行筛选；
    3. 从 Orchestrator 中提取文本上下文，填充至能力升级 Agent 的 `metacognitive_report`
       输入并触发评估。
    """

    def __init__(
        self,
        *,
        stage_one_agent: StageOneAgent,
        capability_agent: CapabilityUpgradeAgentProtocol,
        orchestrator: ContextOrchestrator | None = None,
        context_request_factory: ContextRequest | None = None,
    ) -> None:
        self._stage_one_agent = stage_one_agent
        self._capability_agent = capability_agent
        self._orchestrator = orchestrator or ContextOrchestrator()
        self._request_template = context_request_factory

    @property
    def orchestrator(self) -> ContextOrchestrator:
        """Expose the underlying orchestrator for inspection or manual ingest."""

        return self._orchestrator

    async def run(
        self,
        *,
        analyze_kwargs: Mapping[str, Any],
        capability_kwargs: Mapping[str, Any] | None = None,
        context_request: ContextRequest | None = None,
    ) -> CapabilityUpgradeWorkflowResult:
        """Execute the full metacognition → capability upgrade workflow."""

        stage_one_response = await self._stage_one_agent.analyze(**dict(analyze_kwargs))
        if inspect.isasyncgen(stage_one_response):
            raise ValueError("Stage-one agent returned a streaming generator; disable streaming for orchestration.")

        envelope = self._extract_envelope(stage_one_response)
        if envelope is None:
            raise ValueError("Stage-one agent response did not contain an AgentEnvelope.")

        record_id = self._orchestrator.ingest(envelope)
        package = self._dispatch_context(
            envelope=envelope,
            record_id=record_id,
            request_override=context_request,
            analyze_kwargs=analyze_kwargs,
        )

        metacognitive_report = self._compose_report(package)
        if not metacognitive_report:
            raise ValueError("Failed to compose metacognitive report from orchestrated context.")

        capability_inputs = dict(capability_kwargs or {})
        capability_inputs.setdefault("metacognitive_report", metacognitive_report)

        capability_response = await self._capability_agent.evaluate(**capability_inputs)

        return CapabilityUpgradeWorkflowResult(
            stage_one_response=stage_one_response,
            context_package=package,
            capability_response=capability_response,
        )

    def _extract_envelope(self, response: ChatResponse) -> AgentEnvelope | None:
        metadata = response.metadata or {}
        envelope_payload = metadata.get("_agent_envelope")
        if not envelope_payload:
            return None

        try:
            return coerce_envelope(envelope_payload)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError("Failed to parse AgentEnvelope from stage-one metadata.") from exc

    def _dispatch_context(
        self,
        *,
        envelope: AgentEnvelope,
        record_id: str,
        request_override: ContextRequest | None,
        analyze_kwargs: Mapping[str, Any],
    ) -> ContextPackage:
        if request_override is not None:
            request = request_override
        elif self._request_template is not None:
            request = self._request_template
        else:
            intent = str(analyze_kwargs.get("objective") or "").strip() or "metacognitive_analysis"
            request = ContextRequest(
                intent=intent,
                target_agent=self._capability_agent.agent_name,
                target_stage=self._capability_agent.agent_stage,
                dependencies=(
                    StageDependency(
                        stage=envelope.agent.stage,
                        required=True,
                        note="Metacognitive analysis output used for capability upgrade.",
                    ),
                ),
                max_items=5,
                max_units=10_000,
                priority_tags=("metacognitive",),
            )

        package = self._orchestrator.dispatch(request)

        if not any(item.record_id == record_id for item in package.items):
            # 如果本次信封被过滤掉，补充记录以便后续调试。
            raise ValueError("Newly ingested metacognitive record was not selected by the orchestrator.")

        return package

    def _compose_report(self, package: ContextPackage) -> str:
        if not package.items:
            return ""

        sections: list[str] = []
        for item in package.items:
            summary = extract_payload_summary(item.payload)
            if summary:
                sections.append(summary.strip())
                continue

            if isinstance(item.payload, str):
                sections.append(item.payload.strip())
            else:
                sections.append(str(item.payload))

        return "\n\n".join(section for section in sections if section)

