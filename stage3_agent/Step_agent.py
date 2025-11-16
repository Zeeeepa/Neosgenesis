# -*- coding: utf-8 -*-
"""Stage 3 execution plan agent powered by DeepSeekChatModel."""

from __future__ import annotations

import inspect
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Iterable, Mapping, Sequence

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from model import ChatResponse, DeepSeekChatModel
from workflow.finish_form_utils import update_form_section

PROMPT_PATH = Path(__file__).with_name("step.md")


@dataclass(slots=True)
class Stage3ExecutionAgentConfig:
    """Configuration container for :class:`Stage3ExecutionAgent`."""

    api_key: str | None = None
    model_name: str = "deepseek-chat"
    stream: bool = False
    base_url: str = "https://api.deepseek.com"
    reasoning_effort: str | None = "medium"
    system_prompt: str | None = None
    generate_kwargs: dict[str, Any] | None = field(default_factory=dict)


class Stage3ExecutionAgent:
    """Agent responsible for translating strategies into executable plans."""

    agent_name: str = "Stage3ExecutionAgent"
    agent_stage: str = "stage3"
    agent_function: str = "execution_plan"

    def __init__(
        self,
        config: Stage3ExecutionAgentConfig | None = None,
        **overrides: Any,
    ) -> None:
        config_data = asdict(config or Stage3ExecutionAgentConfig())
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

        self._debug_last_response: ChatResponse | None = None
        self._debug_last_snapshot: dict[str, Any] | None = None

    @property
    def system_prompt(self) -> str | None:
        """Return the current system prompt."""

        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, prompt: str | None) -> None:
        """Update the system prompt used for execution planning."""

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
        refined_strategy: Mapping[str, Any],
        handover_notes: Mapping[str, Any] | Sequence[Any] | None = None,
        objective: str | None = None,
        success_criteria: Sequence[Any] | str | None = None,
        failure_indicators: Sequence[Any] | str | None = None,
        content_quality: Mapping[str, Any] | None = None,
        required_capabilities: Sequence[Mapping[str, Any]] | None = None,
        timeliness_and_knowledge_boundary: Mapping[str, Any] | None = None,
        execution_constraints: Iterable[str] | None = None,
        context_snapshot: str | None = None,
        tool_catalog: Sequence[str] | None = None,
        strategy_id: str | None = None,
        structured_model: Any | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        """Synthesize executable plans using DeepSeek."""

        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        prompt = self._build_prompt(
            meta_analysis=meta_analysis,
            refined_strategy=refined_strategy,
            handover_notes=handover_notes,
            objective=objective,
            success_criteria=success_criteria,
            failure_indicators=failure_indicators,
            content_quality=content_quality,
            required_capabilities=required_capabilities,
            timeliness_and_knowledge_boundary=timeliness_and_knowledge_boundary,
            execution_constraints=execution_constraints,
            context_snapshot=context_snapshot,
            tool_catalog=tool_catalog,
            strategy_id=strategy_id,
        )
        messages.append({"role": "user", "content": prompt})

        result = await self._model(
            messages=messages,
            structured_model=structured_model,
            **kwargs,
        )

        if inspect.isasyncgen(result):
            self._debug_last_response = None
            self._debug_last_snapshot = None
            return result

        self._debug_last_response = result
        self._debug_last_snapshot = {
            "text_preview": (self._extract_text(result) or "")[:1000],
            "metadata": getattr(result, "metadata", None),
            "raw": getattr(result, "raw", None),
        }
        return result

    async def analyze_text(self, **kwargs: Any) -> str:
        """Convenience wrapper returning plain text output."""

        finish_form_path = kwargs.pop("finish_form_path", None)
        finish_form_marker = kwargs.pop("finish_form_marker", "STAGE3_PLAN")
        finish_form_header = kwargs.pop(
            "finish_form_header",
            "## 阶段三：执行步骤规划（Step_agent）",
        )

        response = await self.analyze(**kwargs)

        if inspect.isasyncgen(response):
            chunks: list[str] = []
            async for item in response:
                chunks.append(self._extract_text(item))
            result_text = "".join(chunks).strip()
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
        refined_strategy: Mapping[str, Any],
        handover_notes: Mapping[str, Any] | Sequence[Any] | None,
        objective: str | None,
        success_criteria: Sequence[Any] | str | None,
        failure_indicators: Sequence[Any] | str | None,
        content_quality: Mapping[str, Any] | None,
        required_capabilities: Sequence[Mapping[str, Any]] | None,
        timeliness_and_knowledge_boundary: Mapping[str, Any] | None,
        execution_constraints: Iterable[str] | None,
        context_snapshot: str | None,
        tool_catalog: Sequence[str] | None,
        strategy_id: str | None,
    ) -> str:
        sections: list[str] = []

        if objective:
            sections.append(f"### Objective\n{objective.strip()}")

        sections.append(f"### META_ANALYSIS\n{meta_analysis.strip()}")

        sections.append("### REFINED_STRATEGY\n" + self._format_json(refined_strategy))

        if strategy_id:
            sections.append(f"### STRATEGY_ID\n{strategy_id.strip()}")

        if handover_notes:
            sections.append("### HANDOVER_NOTES\n" + self._format_json(handover_notes))

        normalized_success = self._normalize_to_list(success_criteria)
        if not normalized_success:
            normalized_success = self._extract_from_mapping(refined_strategy, "success_criteria")
        if normalized_success:
            success_block = "\n".join(f"- {item}" for item in normalized_success)
            sections.append(f"### SUCCESS_CRITERIA\n{success_block}")

        normalized_failure = self._normalize_to_list(failure_indicators)
        if not normalized_failure:
            normalized_failure = self._extract_from_mapping(refined_strategy, "failure_indicators")
        if normalized_failure:
            failure_block = "\n".join(f"- {item}" for item in normalized_failure)
            sections.append(f"### FAILURE_INDICATORS\n{failure_block}")

        if required_capabilities:
            capability_lines = []
            for capability in required_capabilities:
                if not isinstance(capability, Mapping):
                    capability_lines.append(f"- {capability!r}")
                    continue
                name = capability.get("name") or capability.get("ability_name") or "Unknown Capability"
                source = capability.get("ability_source") or capability.get("source")
                risk = capability.get("risk")
                role = capability.get("role")
                line = f"- {name}"
                if source:
                    line += f" ({source})"
                if role:
                    line += f" :: {role}"
                if risk:
                    line += f" | risk: {risk}"
                capability_lines.append(line)
            if capability_lines:
                sections.append("### REQUIRED_CAPABILITIES\n" + "\n".join(capability_lines))

        if timeliness_and_knowledge_boundary:
            sections.append(
                "### TIMELINESS_AND_KNOWLEDGE_BOUNDARY\n"
                + self._format_json(timeliness_and_knowledge_boundary)
            )

        if content_quality:
            sections.append("### CONTENT_QUALITY\n" + self._format_json(content_quality))

        if execution_constraints:
            constraint_lines = [
                f"- {str(item).strip()}" for item in execution_constraints if str(item).strip()
            ]
            if constraint_lines:
                sections.append("### EXECUTION_CONSTRAINTS\n" + "\n".join(constraint_lines))

        if context_snapshot:
            sections.append(f"### SUPPLEMENTAL_CONTEXT\n{context_snapshot.strip()}")

        if tool_catalog:
            tool_lines = [f"- {tool}" for tool in tool_catalog if str(tool).strip()]
            if tool_lines:
                sections.append("### TOOL_CATALOG\n" + "\n".join(tool_lines))

        sections.append(
            "### TASK_DIRECTIVES\n"
            "1. 复用 Stage 2 的关键步骤，必要时拆解为便于执行的子任务，并说明排序与依赖关系。\n"
            "2. 为每个子步骤补充所需能力（引用 Stage 1 编号/名称）、质量检查要点与风险缓释措施。\n"
            "3. 标明可并行或需串行的步骤，并给出可追踪的里程碑与验收标准。\n"
            "4. 若发现 Stage 1 或 Stage 2 的假设/约束存在缺失，记录在待确认事项并提出补救建议。\n"
            "5. 输出请使用英文，结构清晰，便于直接执行或追踪。"
        )

        sections.append(
            "### OUTPUT_GUIDELINES\n"
            "- 按阶段或里程碑组织执行计划，说明步骤、负责人/能力、所需资源与风险控制措施。\n"
            "- 描述成败判据的覆盖情况，并显式标注尚未满足的条件或残留风险。\n"
            "- 汇总未决问题、信息缺口或阻塞点，并提出后续推进建议。\n"
            "- 需要时补充资源或时间预估，但保持内容紧凑、重点明确。"
        )

        return "\n\n".join(section for section in sections if section.strip())

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

        if response.metadata:
            return json.dumps(
                response.metadata,
                ensure_ascii=False,
                indent=2,
            )

        return ""

    @staticmethod
    def _normalize_to_list(value: Sequence[Any] | str | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    return [stripped]
                if isinstance(parsed, Sequence) and not isinstance(parsed, (str, bytes)):
                    return [str(item).strip() for item in parsed if str(item).strip()]
                return [stripped]
            return [stripped]
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _extract_from_mapping(mapping: Mapping[str, Any], key: str) -> list[str]:
        value = mapping.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @staticmethod
    def _format_json(data: Any) -> str:
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except TypeError:
            return repr(data)

    @staticmethod
    def _load_default_prompt() -> str | None:
        if not PROMPT_PATH.exists():
            return None
        content = PROMPT_PATH.read_text(encoding="utf-8").strip()
        return content or None

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


__all__ = [
    "Stage3ExecutionAgent",
    "Stage3ExecutionAgentConfig",
]


