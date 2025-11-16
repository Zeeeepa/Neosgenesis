from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

import stage2_capability_upgrade_agent.stage2_capability_upgrade_agent as stage2_module
from model._model_response import ChatResponse, ResponseBlock
from stage2_capability_upgrade_agent.stage2_capability_upgrade_agent import (
    Stage2CapabilityUpgradeAgent,
    Stage2CapabilityUpgradeConfig,
)


class _SequentialStubModel:
    """按调用顺序返回预设文本的桩模型。"""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._index = 0
        self.model_name = "stage2-upgrade-stub"

    async def __call__(  # noqa: D401 - 保持与真实模型一致的签名
        self,
        *,
        messages,
        structured_model=None,
        payload_contract=None,
        **kwargs,
    ) -> ChatResponse:
        if self._index >= len(self._responses):
            raise AssertionError("Stub model was called more times than expected.")

        text = self._responses[self._index]
        self._index += 1
        return ChatResponse(
            content=(ResponseBlock(type="text", text=text),),
            payload=None,
        )


@pytest.mark.asyncio
async def test_stage2_upgrade_agent_applies_fusion_strategy_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 Stage2 能力升级代理仅对新增融合策略落盘，忽略纯改进建议。"""

    strategy_file = tmp_path / "strategy.md"
    strategy_file.write_text(
        textwrap.dedent(
            """
            ## 策略库使用说明

            ### I. 信息管理策略

            #### `contextual_snapshot` (I2)
            - **适配场景**：跨多文档、多轮对话汇总信息，需保持上下文一致性。
            - **策略步骤**：
              1. 对当前任务相关的文档、对话做一页摘要，包含关键事实与未决问题。
              2. 定义标准化字段（如时间、责任人、状态）以便快速对照。
              3. 每次上下文更新后立即刷新快照，防止信息漂移。
            - **典型示例**：在多团队协作项目中，各方输入被整合为统一状态快照。
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(stage2_module, "STRATEGY_LIBRARY_FILE", strategy_file)
    monkeypatch.setattr(stage2_module, "STRATEGY_LIBRARY_DIR", strategy_file.parent)

    expected_patch = textwrap.dedent(
        """
        ### 索引更新
        | I3 | `evidence_snapshot_verification` | 证据快照验证 | 跨源事实核对与快照对齐 |

        ### I. 信息管理策略
        #### `evidence_snapshot_verification` (I3)
        - **适配场景**：当任务需要同时保证事实准确性与上下文一致，需融合证据检索与快照管理。
        - **策略步骤**：
          1. 优先检索权威原始来源获取关键事实。
          2. 至少使用两个独立渠道交叉验证数据并记录可信度。
          3. 将验证结果整理为结构化快照，标注差异点与时间戳。
          4. 对比快照内容，输出逻辑一致的结论与引用依据。
        - **典型示例**：核对公共人物背景信息时，结合官方档案与主流媒体快照完成一致性验证。
        - **注意事项**：若发现来源矛盾，需提示进一步验证路径并避免依赖单一数据。
        """
    ).strip()

    fusion_response = "[Reasoning]\n需要新增融合策略。\n\n" + expected_patch
    refinement_response = "[Reasoning]\n仅建议优化现有策略描述，无需新增策略。"

    agent = Stage2CapabilityUpgradeAgent(
        config=Stage2CapabilityUpgradeConfig(
            api_key="stub-key",
            attach_envelope=False,
            backup_before_write=False,
            auto_apply_patch=True,
            library_file=str(strategy_file),
        )
    )
    agent._model = _SequentialStubModel([fusion_response, refinement_response])  # type: ignore[attr-defined]

    fusion_report = "Stage 2 Output: refined_strategy -> I1-I2 融合策略"
    await agent.evaluate_text(metacognitive_report=fusion_report)

    updated_after_fusion = strategy_file.read_text(encoding="utf-8")
    assert expected_patch in updated_after_fusion
    assert agent.last_patch_markdown == expected_patch
    assert agent.last_applied_path == strategy_file

    refinement_report = "Stage 2 Output: refined_strategy -> I2 调整补充信息"
    await agent.evaluate_text(metacognitive_report=refinement_report)

    updated_after_refinement = strategy_file.read_text(encoding="utf-8")
    assert updated_after_refinement == updated_after_fusion
    assert agent.last_patch_markdown is None

    assert agent._model._index == 2  # type: ignore[attr-defined]





