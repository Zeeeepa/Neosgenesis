"""Stage 2 capability upgrade agent for maintaining the strategy library."""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from capability_upgrade_agent.capability_upgrade_agent import (
    CapabilityUpgradeAgent,
    CapabilityUpgradeConfig,
)
from workflow.finish_form_utils import update_form_section

PROMPT_PATH = Path(__file__).with_name("thinking.md")
STRATEGY_LIBRARY_DIR = PROJECT_ROOT / "strategy_library"
STRATEGY_LIBRARY_FILE = STRATEGY_LIBRARY_DIR / "strategy.md"


@dataclass(slots=True)
class Stage2CapabilityUpgradeConfig(CapabilityUpgradeConfig):
    """Configuration container for :class:`Stage2CapabilityUpgradeAgent`."""

    library_file: str | None = str(STRATEGY_LIBRARY_FILE)
    auto_apply_patch: bool = True


class Stage2CapabilityUpgradeAgent(CapabilityUpgradeAgent):
    """Agent responsible for auditing and extending the Stage 2 strategy library."""

    agent_name: str = "Stage2CapabilityUpgradeAgent"
    agent_stage: str = "stage2"
    agent_function: str = "strategy_upgrade"

    def __init__(
        self,
        config: Stage2CapabilityUpgradeConfig | None = None,
        **overrides: Any,
    ) -> None:
        config_data = asdict(config or Stage2CapabilityUpgradeConfig())
        config_data.update(overrides)

        if not config_data.get("library_file"):
            config_data["library_file"] = str(STRATEGY_LIBRARY_FILE)

        stage2_config = Stage2CapabilityUpgradeConfig(**config_data)
        super().__init__(config=stage2_config)

    def _compose_default_system_prompt(self) -> str | None:  # type: ignore[override]
        template = self._load_prompt_template()
        library_snapshot = self._library_snapshot

        if template and library_snapshot:
            return f"{template}\n\n## 当前策略库快照\n\n{library_snapshot}"
        if template:
            return template
        return library_snapshot

    @staticmethod
    def _load_prompt_template() -> str | None:  # type: ignore[override]
        if not PROMPT_PATH.exists():
            return None
        content = PROMPT_PATH.read_text(encoding="utf-8").strip()
        return content or None

    async def evaluate_text(self, **kwargs: Any) -> str:  # type: ignore[override]
        finish_form_path = kwargs.pop("finish_form_path", None)
        finish_form_marker = kwargs.pop("finish_form_marker", "STAGE2C_ANALYSIS")
        finish_form_header = kwargs.pop(
            "finish_form_header",
            "## 阶段二-C：能力升级评估（Stage2_Capability_Upgrade_agent）",
        )

        result_text = await super().evaluate_text(**kwargs)

        if finish_form_path:
            update_form_section(
                finish_form_path,
                marker_name=finish_form_marker,
                content=result_text,
                header=finish_form_header,
            )

        return result_text

    def _load_library_snapshot(self, max_chars: int | None) -> str | None:  # type: ignore[override]
        if not STRATEGY_LIBRARY_FILE.exists():
            return None

        text = STRATEGY_LIBRARY_FILE.read_text(encoding="utf-8").strip()
        if not text:
            return None

        if max_chars is not None and len(text) > max_chars:
            truncated = text[: max_chars].rstrip()
            truncated += (
                "\n\n...[内容已截断，完整策略定义请查阅 strategy_library/strategy.md 原始文件]..."
            )
            return truncated
        return text


__all__ = [
    "Stage2CapabilityUpgradeAgent",
    "Stage2CapabilityUpgradeConfig",
]

