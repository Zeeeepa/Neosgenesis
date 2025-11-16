from __future__ import annotations

import pytest

from context.envelope import build_agent_envelope, envelope_to_dict
from contracts.domain_contracts import AgentPayload
from model._model_response import ChatResponse, ResponseBlock
from workflow.capability_upgrade_workflow import CapabilityUpgradeWorkflow


class StubStageOneAgent:
    agent_name = "MetacognitiveAnalysisAgent"
    agent_stage = "stage1"
    agent_function = "metacognitive_analysis"

    def __init__(self, message: str) -> None:
        self._message = message
        self.analyze_calls: list[dict[str, object]] = []

    async def analyze(self, **kwargs: object) -> ChatResponse:
        self.analyze_calls.append(dict(kwargs))
        payload = AgentPayload(message=self._message, data={"reasoning": "stub"})
        envelope = build_agent_envelope(
            payload,
            agent_name=self.agent_name,
            stage=self.agent_stage,
            function=self.agent_function,
            model_name="stub-metacog-model",
            tags={"metacognitive": "true"},
        )
        metadata = {"_agent_envelope": envelope_to_dict(envelope, exclude_none=True)}
        return ChatResponse(
            content=(ResponseBlock(type="text", text=self._message),),
            payload=payload,
            metadata=metadata,
        )


class StubCapabilityUpgradeAgent:
    agent_name = "CapabilityUpgradeAgent"
    agent_stage = "library"
    agent_function = "capability_upgrade"

    def __init__(self) -> None:
        self.evaluate_calls: list[dict[str, object]] = []

    async def evaluate(self, **kwargs: object) -> ChatResponse:
        self.evaluate_calls.append(dict(kwargs))
        text = f"Capabilities refreshed using: {kwargs.get('metacognitive_report')}"
        return ChatResponse(content=(ResponseBlock(type="text", text=text),))


@pytest.mark.asyncio
async def test_workflow_ingests_stage_one_envelope() -> None:
    stage_one_agent = StubStageOneAgent("阶段一分析结果：请更新知识库。")
    capability_agent = StubCapabilityUpgradeAgent()

    workflow = CapabilityUpgradeWorkflow(
        stage_one_agent=stage_one_agent,
        capability_agent=capability_agent,
    )

    result = await workflow.run(
        analyze_kwargs={"objective": "能力库更新需求评估"},
        capability_kwargs={"suspected_new_capabilities": ["capability_x"]},
    )

    assert result.context_package.items, "期望从 orchestrator 中选出至少一条上下文"
    assert capability_agent.evaluate_calls, "能力升级 Agent 应该被调用"

    call_kwargs = capability_agent.evaluate_calls[-1]
    report = call_kwargs["metacognitive_report"]
    assert "阶段一分析结果" in report
    assert "请更新知识库" in report

