from __future__ import annotations

import pytest

from context.envelope import build_agent_envelope, envelope_to_dict
from contracts.domain_contracts import AgentPayload
from model._model_response import ChatResponse, ResponseBlock
from workflow.agent_workflow import (
    CandidateSelectionAgentProtocol,
    StageOneAgentProtocol,
    StageTwoAgentProtocol,
    StrategySelectionWorkflow,
)


class StubStageOneAgent(StageOneAgentProtocol):
    agent_name = "MetacognitiveAnalysisAgent"
    agent_stage = "stage1"
    agent_function = "metacognitive_analysis"

    def __init__(self, payload: AgentPayload) -> None:
        self._payload = payload
        self.calls: list[dict[str, object]] = []

    async def analyze(self, **kwargs: object) -> ChatResponse:
        self.calls.append(dict(kwargs))
        envelope = build_agent_envelope(
            self._payload,
            agent_name=self.agent_name,
            stage=self.agent_stage,
            function=self.agent_function,
            model_name="stub-stage1-model",
        )
        metadata = {"_agent_envelope": envelope_to_dict(envelope, exclude_none=True)}
        return ChatResponse(
            content=(ResponseBlock(type="text", text=self._payload.message),),
            payload=self._payload,
            metadata=metadata,
        )


class StubStageTwoAgent(StageTwoAgentProtocol):
    agent_name = "StrategySelectionAgent"
    agent_stage = "stage2"
    agent_function = "strategy_selection"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def analyze(self, **kwargs: object) -> ChatResponse:
        self.calls.append(dict(kwargs))
        payload = AgentPayload(message="策略评估完成。", data={"received": kwargs})
        envelope = build_agent_envelope(
            payload,
            agent_name=self.agent_name,
            stage=self.agent_stage,
            function=self.agent_function,
            model_name="stub-stage2-model",
        )
        metadata = {"_agent_envelope": envelope_to_dict(envelope, exclude_none=True)}
        return ChatResponse(
            content=(ResponseBlock(type="text", text="OK"),),
            payload=payload,
            metadata=metadata,
        )


class StubCandidateAgent(CandidateSelectionAgentProtocol):
    agent_name = "StrategyCandidateSelectionAgent"
    agent_stage = "stage2_candidates"
    agent_function = "candidate_selection"

    def __init__(self, candidates: list[dict[str, object]]) -> None:
        self._candidates = candidates
        self.calls: list[dict[str, object]] = []

    async def analyze(self, **kwargs: object) -> ChatResponse:
        self.calls.append(dict(kwargs))
        payload = AgentPayload(message="候选策略已生成。", data={"candidates": self._candidates})
        envelope = build_agent_envelope(
            payload,
            agent_name=self.agent_name,
            stage=self.agent_stage,
            function=self.agent_function,
            model_name="stub-candidate-model",
        )
        metadata = {"_agent_envelope": envelope_to_dict(envelope, exclude_none=True)}
        return ChatResponse(
            content=(ResponseBlock(type="text", text="DONE"),),
            payload=payload,
            metadata=metadata,
        )


@pytest.mark.asyncio
async def test_workflow_selects_candidates_and_forwards_payload() -> None:
    payload = AgentPayload(
        message="Stage1 元分析完成。",
        data={
            "problem_type": {"label": "research_question", "reasoning": "需要深入检索并整合信息。"},
            "required_capabilities": [
                {"name": "knowledge_retrieval", "role": "聚合事实证据。"},
                {"name": "research", "role": "结构化文献调研。"},
                {"name": "planning", "role": "设计行动路线。"},
            ],
            "content_quality": {
                "completeness": 0.7,
                "accuracy": 0.65,
                "timeliness": 0.5,
                "gaps": ["缺乏最新外部信息"],
            },
        },
        metadata={"agent": "stage1_metacognitive"},
    )
    stage_one_agent = StubStageOneAgent(payload)
    stage_two_agent = StubStageTwoAgent()
    candidates = [
        {
            "strategy_id": "I1",
            "strategy_name": "evidence_first_research",
            "summary": "证据先行收集事实",
        },
        {
            "strategy_id": "X1",
            "strategy_name": "exploratory_insight_cycle",
            "summary": "探索迭代检视未知领域",
        },
        {
            "strategy_id": "I2",
            "strategy_name": "contextual_snapshot",
            "summary": "背景快照汇总上下文",
        },
    ]
    candidate_agent = StubCandidateAgent(candidates)

    workflow = StrategySelectionWorkflow(
        stage_one_agent=stage_one_agent,
        stage_two_agent=stage_two_agent,
        candidate_agent=candidate_agent,
    )

    result = await workflow.run(objective="评估新领域研究路径")

    assert stage_one_agent.calls, "Stage 1 agent should be invoked."
    assert stage_two_agent.calls, "Stage 2 agent should be invoked."

    assert candidate_agent.calls, "Candidate selection agent should be invoked."

    stage_two_call = stage_two_agent.calls[-1]
    candidates = stage_two_call["candidate_strategies"]
    assert isinstance(candidates, list) and len(candidates) == 3
    candidate_ids = [item["strategy_id"] for item in candidates]
    assert candidate_ids == ["I1", "X1", "I2"]

    assert stage_two_call["meta_analysis"].startswith("{")
    quality = stage_two_call["content_quality"]
    assert quality["completeness"] == 0.7
    assert "缺乏最新外部信息" in quality["gaps"]

    assert result.meta_analysis_block == stage_two_call["meta_analysis"]
    assert result.candidate_strategies == candidates
    assert result.candidate_response is not None
    assert result.candidate_envelope is not None

