# -*- coding: utf-8 -*-
"""Candidate strategy selection agent powered by DeepSeekChatModel."""

from __future__ import annotations

import inspect
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Mapping, Sequence

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from model import ChatResponse, DeepSeekChatModel
from workflow.finish_form_utils import update_form_section

PROMPT_PATH = Path(__file__).with_name("selector.md")
STRATEGY_LIBRARY_DIR = PROJECT_ROOT / "strategy_library"


@dataclass(slots=True)
class CandidateSelectionAgentConfig:
    """Configuration container for :class:`CandidateSelectionAgent`."""

    api_key: str | None = None
    model_name: str = "deepseek-chat"
    stream: bool = False
    base_url: str = "https://api.deepseek.com"
    reasoning_effort: str | None = "medium"
    system_prompt: str | None = None
    generate_kwargs: dict[str, Any] | None = field(default_factory=dict)
    default_candidate_limit: int = 3


class CandidateSelectionAgent:
    """Agent responsible for curating candidate strategies via DeepSeek."""

    agent_name: str = "StrategyCandidateSelectionAgent"
    agent_stage: str = "stage2_candidates"
    agent_function: str = "candidate_selection"

    def __init__(
        self,
        config: CandidateSelectionAgentConfig | None = None,
        **overrides: Any,
    ) -> None:
        config_data = asdict(config or CandidateSelectionAgentConfig())
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

        self._default_candidate_limit = int(config_data.get("default_candidate_limit", 3))
        self._debug_last_response: ChatResponse | None = None
        self._debug_last_snapshot: dict[str, Any] | None = None

    @property
    def system_prompt(self) -> str | None:
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, prompt: str | None) -> None:
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
        objective: str | None = None,
        required_capabilities: Sequence[Mapping[str, Any]] | None = None,
        problem_type: Mapping[str, Any] | None = None,
        content_quality: Mapping[str, Any] | None = None,
        candidate_limit: int | None = None,
        structured_model: Any | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        messages.append(
            {
                "role": "user",
                "content": self._build_prompt(
                    meta_analysis=meta_analysis,
                    objective=objective,
                    required_capabilities=required_capabilities,
                    problem_type=problem_type,
                    content_quality=content_quality,
                    candidate_limit=candidate_limit or self._default_candidate_limit,
                ),
            }
        )

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
        finish_form_path = kwargs.pop("finish_form_path", None)
        finish_form_marker = kwargs.pop("finish_form_marker", "STAGE2A_ANALYSIS")
        finish_form_header = kwargs.pop(
            "finish_form_header",
            "## 阶段二-A：候选策略产出（Candidate_Selection_agent）",
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
        objective: str | None,
        required_capabilities: Sequence[Mapping[str, Any]] | None,
        problem_type: Mapping[str, Any] | None,
        content_quality: Mapping[str, Any] | None,
        candidate_limit: int,
    ) -> str:
        sections: list[str] = [
            f"### Candidate Limit\n{max(candidate_limit, 2)}",
            "### META_ANALYSIS\n" + meta_analysis.strip(),
        ]

        if objective:
            sections.append(f"### Objective\n{objective.strip()}")

        if required_capabilities:
            capability_lines = []
            for capability in required_capabilities:
                name = str(capability.get("name") if isinstance(capability, Mapping) else capability)
                role = capability.get("role") if isinstance(capability, Mapping) else None
                capability_lines.append(f"- {name}{' :: ' + str(role) if role else ''}")
            if capability_lines:
                sections.append("### REQUIRED_CAPABILITIES\n" + "\n".join(capability_lines))

        if problem_type:
            try:
                problem_json = json.dumps(problem_type, ensure_ascii=False, indent=2)
            except TypeError:
                problem_json = repr(problem_type)
            sections.append("### PROBLEM_TYPE\n" + problem_json)

        if content_quality:
            try:
                quality_json = json.dumps(content_quality, ensure_ascii=False, indent=2)
            except TypeError:
                quality_json = repr(content_quality)
            sections.append("### CONTENT_QUALITY\n" + quality_json)

        sections.append(
            "### TASKS\n"
            "1. 从策略库中检索最匹配的 2-3 个策略，优先覆盖所需能力与挑战。\n"
            "2. 结合 content_quality 判断是否需要补强或组合策略。\n"
            "3. 对每个候选策略给出 summary / alignment / coverage / risks_or_gaps / notes 字段。\n"
            "4. 汇总筛选原理，并复述 Stage 1 的关键诊断以便下游核对。\n"
            "5. 全程使用英文撰写内容，如需引用中文名称，可在英文说明后括号标注原文。"
        )

        sections.append(
            "### OUTPUT_GUIDELINES\n"
            "- Use concise English bullet points or short paragraphs for each strategy.\n"
            "- Preserve original strategy IDs while translating narrative descriptions to English.\n"
            "- Highlight any residual risks or assumptions explicitly in English."
        )

        return "\n\n".join(section for section in sections if section.strip())

    @staticmethod
    def _extract_text(response: ChatResponse) -> str:
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

    @staticmethod
    def _load_default_prompt() -> str | None:
        if not PROMPT_PATH.exists():
            return None

        content = PROMPT_PATH.read_text(encoding="utf-8").strip()
        strategy_sections: list[str] = []

        if STRATEGY_LIBRARY_DIR.exists() and STRATEGY_LIBRARY_DIR.is_dir():
            for strategy_file in sorted(STRATEGY_LIBRARY_DIR.glob("*.md")):
                data = strategy_file.read_text(encoding="utf-8").strip()
                if not data:
                    continue
                title = strategy_file.stem.replace("_", " ")
                strategy_sections.append(f"## 策略库：{title}\n\n{data}")

        if strategy_sections:
            merged_sections = "\n\n".join(strategy_sections).strip()
            if content:
                content = f"{content}\n\n{merged_sections}"
            else:
                content = merged_sections

        return content or None


__all__ = [
    "CandidateSelectionAgent",
    "CandidateSelectionAgentConfig",
]

