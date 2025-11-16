# -*- coding: utf-8 -*-
"""Metacognitive analysis agent powered by DeepSeekChatModel."""

from __future__ import annotations

import inspect
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Iterable, Literal, Mapping, Sequence

# Ensure project root is on sys.path so that `model` package can be imported
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from model import ChatResponse, DeepSeekChatModel
from workflow.finish_form_utils import update_form_section

PROMPT_PATH = Path(__file__).with_name("reasoner.md")
ABILITY_LIBRARY_DIR = PROJECT_ROOT / "ability_library"


@dataclass(slots=True)
class MetacognitiveAgentConfig:
    """Configuration container for :class:`MetacognitiveAnalysisAgent`."""

    api_key: str | None = None
    model_name: str = "deepseek-chat"
    stream: bool = False
    base_url: str = "https://api.deepseek.com"
    reasoning_effort: Literal["low", "medium", "high"] | None = "medium"
    system_prompt: str | None = None
    generate_kwargs: dict[str, Any] | None = field(default_factory=dict)


class MetacognitiveAnalysisAgent:
    """Agent that performs metacognitive analysis through DeepSeek."""

    agent_name: str = "MetacognitiveAnalysisAgent"
    agent_stage: str = "stage1"
    agent_function: str = "metacognitive_analysis"

    def __init__(
        self,
        config: MetacognitiveAgentConfig | None = None,
        **overrides: Any,
    ) -> None:
        """Initialize the agent and underlying :class:`DeepSeekChatModel`.

        Parameters mirror :class:`MetacognitiveAgentConfig`. Passing keyword
        arguments directly will override any value provided in ``config``.
        ``api_key`` can be omitted if the ``DEEPSEEK_API_KEY`` environment
        variable is set.
        """

        config_data = asdict(config or MetacognitiveAgentConfig())
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
        """Update the system prompt used for analysis."""

        if prompt is None:
            self._system_prompt = None
            return

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("System prompt must be a non-empty string when provided.")
        self._system_prompt = prompt.strip()

    async def analyze(
        self,
        *,
        objective: str,
        context: str | None = None,
        recent_thoughts: str | None = None,
        conversation_history: Sequence[dict[str, str] | tuple[str, str]] | None = None,
        critiques: Iterable[str] | None = None,
        pending_actions: Iterable[str] | None = None,
        tool_catalog: Iterable[str] | None = None,
        structured_model: Any | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        """Perform metacognitive analysis using DeepSeek.

        Parameters
        ----------
        objective:
            The primary task or goal that needs reflection.
        context:
            Optional contextual background or environment state.
        recent_thoughts:
            Latest reasoning trace or chain-of-thought snapshot to audit.
        conversation_history:
            Sequence of chat messages as dictionaries or (role, content)
            tuples, used to provide richer context.
        critiques:
            Iterable of bullet-point critiques or review comments.
        pending_actions:
            Iterable describing upcoming actions to validate.
        tool_catalog:
            Descriptions of available tools that the agent may reference, but
            tools are not invoked programmatically.
        structured_model:
            Optional Pydantic model to coerce responses into structured JSON.
        kwargs:
            Additional keyword arguments forwarded to the model call.
        """

        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        messages.append(
            {
                "role": "user",
                "content": self._build_prompt(
                    objective=objective,
                    context=context,
                    recent_thoughts=recent_thoughts,
                    conversation_history=conversation_history,
                    critiques=critiques,
                    pending_actions=pending_actions,
                    tool_catalog=tool_catalog,
                ),
            },
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

        finish_form_path = kwargs.pop("finish_form_path", None)
        finish_form_marker = kwargs.pop("finish_form_marker", "STAGE1_ANALYSIS")
        finish_form_header = kwargs.pop(
            "finish_form_header",
            "## 阶段一：元能力分析（Metacognitive_Analysis_agent）",
        )

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
        objective: str,
        context: str | None,
        recent_thoughts: str | None,
        conversation_history: Sequence[dict[str, str] | tuple[str, str]] | None,
        critiques: Iterable[str] | None,
        pending_actions: Iterable[str] | None,
        tool_catalog: Iterable[str] | None,
    ) -> str:
        """Assemble the user prompt from individual components."""

        sections: list[str] = [f"### Objective\n{objective.strip()}"]

        if context:
            sections.append(f"### Context\n{context.strip()}")

        if recent_thoughts:
            sections.append(f"### Recent Reasoning\n{recent_thoughts.strip()}")

        if conversation_history:
            formatted_dialogue = []
            for item in conversation_history:
                if isinstance(item, dict):
                    role = item.get("role", "unknown")
                    content = item.get("content", "")
                elif isinstance(item, tuple) and len(item) == 2:
                    role, content = item
                else:
                    continue
                if not content:
                    continue
                formatted_dialogue.append(f"- {role.strip()}: {content.strip()}")
            if formatted_dialogue:
                sections.append(
                    "### Conversation History\n" + "\n".join(formatted_dialogue),
                )

        if critiques:
            formatted_critiques = [f"- {c.strip()}" for c in critiques if str(c).strip()]
            if formatted_critiques:
                sections.append("### External Critiques\n" + "\n".join(formatted_critiques))

        if pending_actions:
            formatted_actions = [f"- {a.strip()}" for a in pending_actions if str(a).strip()]
            if formatted_actions:
                sections.append("### Pending Actions\n" + "\n".join(formatted_actions))

        if tool_catalog:
            formatted_tools = [f"- {t.strip()}" for t in tool_catalog if str(t).strip()]
            if formatted_tools:
                sections.append("### Available Tools\n" + "\n".join(formatted_tools))

        sections.append(
            "### Analysis Expectations\n"
            "1. Evaluate alignment between objective, context, and actions.\n"
            "2. Identify reasoning gaps, risks, or missing information.\n"
            "3. Recommend concrete next steps or corrective actions.\n"
            "4. Provide the full analysis in English so downstream agents can operate consistently."
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

        payload_dict = MetacognitiveAnalysisAgent._coerce_payload_dict(getattr(response, "payload", None))
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
        """Load the default system prompt from ``reasoner.md`` if available."""

        if not PROMPT_PATH.exists():
            return None

        content = PROMPT_PATH.read_text(encoding="utf-8").strip()
        ability_sections: list[str] = []

        if ABILITY_LIBRARY_DIR.exists() and ABILITY_LIBRARY_DIR.is_dir():
            library_files = sorted(ABILITY_LIBRARY_DIR.glob("*.md"))
            for ability_file in library_files:
                data = ability_file.read_text(encoding="utf-8").strip()
                if not data:
                    continue
                title = ability_file.stem.replace("_", " ")
                section_header = f"## 能力库：{title}"
                ability_sections.append(f"{section_header}\n\n{data}")

        if ability_sections:
            merged_sections = "\n\n".join(ability_sections).strip()
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
            return [MetacognitiveAnalysisAgent._coerce_payload_dict(item) for item in payload]

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
