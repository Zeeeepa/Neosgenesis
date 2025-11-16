from __future__ import annotations
import textwrap
from pathlib import Path

import pytest

import capability_upgrade_agent.capability_upgrade_agent as cap_module
from capability_upgrade_agent.capability_upgrade_agent import (
    CapabilityUpgradeAgent,
    CapabilityUpgradeConfig,
)
from model._model_response import ChatResponse, ResponseBlock


class _StubModel:
    """替代 DeepSeekChatModel 的桩对象，返回固定文本。"""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.model_name = "stub-upgrade-model"

    async def __call__(  # noqa: D401 - 保持与真实模型一致的签名
        self,
        *,
        messages,
        structured_model=None,
        payload_contract=None,
        **kwargs,
    ) -> ChatResponse:
        return ChatResponse(
            content=(ResponseBlock(type="text", text=self._response_text),),
            payload=None,
        )


@pytest.mark.asyncio
async def test_auto_apply_capability_patch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 CapabilityUpgradeAgent 能自动写入新的能力定义。"""

    # 使用临时能力库目录，避免污染真实文件
    ability_dir = tmp_path / "ability_library"
    ability_dir.mkdir()
    (ability_dir / "core_capabilities.md").write_text("# 核心能力库\n", encoding="utf-8")
    monkeypatch.setattr(cap_module, "ABILITY_LIBRARY_DIR", ability_dir)

    # 创建独立的目标文件，模拟 core_capabilities.md
    library_file = tmp_path / "core_capabilities.md"
    library_file.write_text(
        textwrap.dedent(
            """
            ## 核心能力库使用说明

            ### H. 伦理与安全能力

            #### `ethical_judgment` (H2)
            - **适配问题类型**：`ethical_assessment`
            - **能力说明**：对方案进行伦理审查。
            - **典型示例**：评估算法公平性。
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    patch_markdown = textwrap.dedent(
        """
        [Reasoning]
        需要新增能力以覆盖政策差距分析。

        ### H. 伦理与安全能力

        #### `compliance_audit` (H3)
        - **适配问题类型**：`regulation_update`、`policy_gap_analysis`
        - **能力说明**：对比新旧政策条款，识别合规差距并提供调整建议。
        - **典型示例**：分析最新金融监管条例下银行业务流程是否合规。
        """
    ).strip()

    config = CapabilityUpgradeConfig(
        api_key="stub-key",
        auto_apply_patch=True,
        attach_envelope=False,
        backup_before_write=False,
        library_file=str(library_file),
    )

    agent = CapabilityUpgradeAgent(config=config)
    agent._model = _StubModel(patch_markdown)  # type: ignore[attr-defined]

    await agent.evaluate_text(
        metacognitive_report="示例任务需要新的合规能力。",
        suspected_new_capabilities=["compliance_audit"],
    )

    updated = library_file.read_text(encoding="utf-8")
    assert patch_markdown.splitlines()[-1] in updated
    assert updated.strip().endswith(
        "\n".join(patch_markdown.splitlines()[2:]).strip()
    )

    assert agent.last_patch_markdown is not None
    assert agent.last_applied_path == library_file

