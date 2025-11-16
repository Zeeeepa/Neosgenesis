# -*- coding: utf-8 -*-
"""Strategy selection agent powered by DeepSeekChatModel."""

from __future__ import annotations

import inspect
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Iterable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from model import ChatResponse, DeepSeekChatModel
from workflow.finish_form_utils import update_form_section

PROMPT_PATH = Path(__file__).with_name("verifire.md")
STRATEGY_LIBRARY_DIR = PROJECT_ROOT / "strategy_library"


@dataclass(slots=True)
class StrategySelectionAgentConfig:
    """Configuration container for :class:`StrategySelectionAgent`."""

    api_key: str | None = None
    model_name: str = "deepseek-chat"
    stream: bool = False
    base_url: str = "https://api.deepseek.com"
    reasoning_effort: str | None = "medium"
    system_prompt: str | None = None
    generate_kwargs: dict[str, Any] | None = field(default_factory=dict)


class StrategySelectionAgent:
    """Agent that performs strategy selection and refinement through DeepSeek."""

    agent_name: str = "StrategySelectionAgent"
    agent_stage: str = "stage2"
    agent_function: str = "strategy_selection"

    def __init__(
        self,
        config: StrategySelectionAgentConfig | None = None,
        **overrides: Any,
    ) -> None:
        """Initialize the agent and underlying :class:`DeepSeekChatModel`."""

        config_data = asdict(config or StrategySelectionAgentConfig())
        config_data.update(overrides)

        api_key = config_data.get("api_key") or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError(
                "DeepSeek API key is required. Provide it via `api_key` "
                "or set the DEEPSEEK_API_KEY environment variable.",
            )

        system_prompt = config_data.get("system_prompt")
        if system_prompt is None:
            system_prompt = self._load_default_prompt()
        elif not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("system_prompt must be a non-empty string when provided.")
        else:
            system_prompt = system_prompt.strip()

        self._system_prompt: str | None = system_prompt
        self._model = DeepSeekChatModel(
            model_name=config_data.get("model_name", "deepseek-chat"),
            api_key=api_key,
            stream=bool(config_data.get("stream", False)),
            base_url=config_data.get("base_url", "https://api.deepseek.com"),
            reasoning_effort=config_data.get("reasoning_effort"),
            generate_kwargs=config_data.get("generate_kwargs") or {},
        )

    @property
    def system_prompt(self) -> str | None:
        """Return the current system prompt."""

        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, prompt: str | None) -> None:
        """Update the system prompt used for selection."""

        if prompt is None:
            self._system_prompt = None
            return

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("System prompt must be a non-empty string when provided.")
        self._system_prompt = prompt.strip()

    async def analyze(
        self,
        *,
        meta_analysis: str,
        candidate_sheet: str,
        objective: str | None = None,
        context_snapshot: str | None = None,
        execution_constraints: Iterable[str] | None = None,
        content_quality: Mapping[str, Any] | None = None,
        finish_form_path: str | None = None,
        structured_model: Any | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        """Select and refine strategies using DeepSeek."""

        if not isinstance(candidate_sheet, str) or not candidate_sheet.strip():
            raise ValueError("candidate_sheet must be a non-empty string.")

        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        messages.append(
            {
                "role": "user",
                "content": self._build_prompt(
                    meta_analysis=meta_analysis,
                    candidate_sheet=candidate_sheet,
                    objective=objective,
                    context_snapshot=context_snapshot,
                    execution_constraints=execution_constraints,
                    content_quality=content_quality,
                    finish_form_path=finish_form_path,
                ),
            }
        )

        result = await self._model(
            messages=messages,
            structured_model=structured_model,
            **kwargs,
        )

        if inspect.isasyncgen(result):
            return result

        return result

    async def analyze_text(
        self,
        **kwargs: Any,
    ) -> str:
        """Convenience wrapper around :meth:`analyze` returning plain text."""

        finish_form_marker = kwargs.pop("finish_form_marker", "STAGE2B_ANALYSIS")
        finish_form_header = kwargs.pop(
            "finish_form_header",
            "## 阶段二-B：策略遴选（Strategy_Selection_agent）",
        )
        finish_form_path = kwargs.get("finish_form_path")

        response = await self.analyze(**kwargs)

        if inspect.isasyncgen(response):
            chunks: list[str] = []
            async for item in response:
                chunks.append(self._extract_text(item))
            result_text = "".join(chunks).strip()
        else:
            payload_dict = self._coerce_payload_dict(getattr(response, "payload", None))
            if payload_dict is not None:
                result_text = json.dumps(payload_dict, ensure_ascii=False, indent=2)
            else:
                result_text = self._extract_text(response)

        if finish_form_path:
            self._write_finish_form(
                finish_form_path,
                result_text,
                marker=finish_form_marker,
                header=finish_form_header,
            )

        return result_text

    def _build_prompt(
        self,
        *,
        meta_analysis: str,
        candidate_sheet: str,
        objective: str | None,
        context_snapshot: str | None,
        execution_constraints: Iterable[str] | None,
        content_quality: Mapping[str, Any] | None,
        finish_form_path: str | None,
    ) -> str:
        """Assemble the user prompt from individual components."""

        sections: list[str] = []

        if objective:
            sections.append(f"### Objective\n{objective.strip()}")

        sections.append(f"### META_ANALYSIS_BLOCK\n{meta_analysis.strip()}")

        if content_quality:
            quality_lines = []
            for key in ("completeness", "accuracy", "timeliness"):
                if key in content_quality:
                    quality_lines.append(f"- {key}: {content_quality[key]}")
            gaps = content_quality.get("gaps") if isinstance(content_quality.get("gaps"), Iterable) else None
            if gaps:
                formatted_gaps = [f"  - {str(gap).strip()}" for gap in gaps if str(gap).strip()]
                if formatted_gaps:
                    quality_lines.append("- gaps:\n" + "\n".join(formatted_gaps))
            sections.append("### CONTENT_QUALITY\n" + "\n".join(quality_lines))

        sections.append("### CANDIDATE_SHEET_MARKDOWN\n" + candidate_sheet.strip())

        if finish_form_path:
            sections.append(f"### FINISH_FORM_PATH\n{finish_form_path.strip()}")

        if context_snapshot:
            sections.append(f"### SUPPLEMENTAL_CONTEXT\n{context_snapshot.strip()}")

        if execution_constraints:
            constraint_lines = [f"- {str(item).strip()}" for item in execution_constraints if str(item).strip()]
            if constraint_lines:
                sections.append("### EXECUTION_CONSTRAINTS\n" + "\n".join(constraint_lines))

        sections.append(
            "### ANALYSIS_TASKS\n"
            "1. 遵循 `verifire.md` 中的 "
            "Task 1 要求，对候选策略逐一评估优势、缺口、必要改造与能力匹配。\n"
            "2. 根据 Stage 1 `content_quality` 判断是否需要融合多策略或保留单一策略。\n"
            "3. 按 Task 2 输出改造后的 `refined_strategy`、成功/失败判据与 `handover_notes`。\n"
            "4. 所有分析说明与总结必须使用英文撰写，必要时可在括号内保留中文术语。"
        )

        sections.append(
            "### OUTPUT_GUIDELINES\n"
            "- 以清晰的小节或项目符号总结每个候选策略的评估与改造建议。\n"
            "- 在策略引用中使用 `strategy_library/strategy.md` 的原始编号与名称。\n"
            "- 解释最终方案如何覆盖 `required_capabilities` 与主要风险点。\n"
            "- 保持全篇英文表达，确保 Stage 3 能直接继承。"
        )

        return "\n\n".join(sections).strip()

    @staticmethod
    def _extract_text(response: ChatResponse) -> str:
        """Extract textual content (including thinking) from a response."""

        parts: list[str] = []
        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                parts.append(getattr(block, "text", ""))
            elif block_type == "thinking":
                parts.append("[Reasoning]\n" + getattr(block, "thinking", ""))
        if parts:
            return "\n".join(part.strip() for part in parts if part).strip()

        payload_dict = StrategySelectionAgent._coerce_payload_dict(getattr(response, "payload", None))
        if payload_dict is not None:
            return json.dumps(payload_dict, ensure_ascii=False, indent=2)

        if response.metadata:
            return json.dumps(
                response.metadata,
                ensure_ascii=False,
                indent=2,
            )

        return ""

    @staticmethod
    def _load_default_prompt() -> str | None:
        """Load the default system prompt from ``verifire.md`` with strategy library."""

        if not PROMPT_PATH.exists():
            return None

        content = PROMPT_PATH.read_text(encoding="utf-8").strip()
        strategy_sections: list[str] = []

        if STRATEGY_LIBRARY_DIR.exists() and STRATEGY_LIBRARY_DIR.is_dir():
            library_files = sorted(STRATEGY_LIBRARY_DIR.glob("*.md"))
            for strategy_file in library_files:
                data = strategy_file.read_text(encoding="utf-8").strip()
                if not data:
                    continue
                title = strategy_file.stem.replace("_", " ")
                section_header = f"## 策略库：{title}"
                strategy_sections.append(f"{section_header}\n\n{data}")

        if strategy_sections:
            merged_sections = "\n\n".join(strategy_sections).strip()
            if content:
                content = f"{content}\n\n{merged_sections}"
            else:
                content = merged_sections

        return content or None

    @staticmethod
    def _coerce_payload_dict(payload: Any) -> Mapping[str, Any] | list[Any] | Any | None:
        if payload is None:
            return None

        for attr in ("model_dump", "dict"):
            if hasattr(payload, attr):
                method = getattr(payload, attr)
                try:
                    return method(exclude_none=True)  # type: ignore[call-arg]
                except TypeError:
                    return method()
                except Exception:
                    continue

        if isinstance(payload, Mapping):
            return dict(payload)

        if isinstance(payload, (list, tuple)):
            return [StrategySelectionAgent._coerce_payload_dict(item) for item in payload]

        return payload

    @staticmethod
    def _write_finish_form(
        finish_form_path: str | Path,
        content: str,
        *,
        marker: str,
        header: str,
    ) -> None:
        update_form_section(
            finish_form_path,
            marker_name=marker,
            content=content,
            header=header,
        )
