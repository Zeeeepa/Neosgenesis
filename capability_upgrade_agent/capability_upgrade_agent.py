"""Capability upgrade agent for maintaining the ability library."""

from __future__ import annotations

import inspect
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Literal, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from model import ChatResponse, DeepSeekChatModel

PROMPT_PATH = Path(__file__).with_name("thinking.md")
ABILITY_LIBRARY_DIR = PROJECT_ROOT / "ability_library"


@dataclass(slots=True)
class CapabilityUpgradeConfig:
    """Configuration container for :class:`CapabilityUpgradeAgent`."""

    api_key: str | None = None
    model_name: str = "deepseek-chat"
    stream: bool = False
    base_url: str = "https://api.deepseek.com"
    reasoning_effort: Literal["low", "medium", "high"] | None = "medium"
    system_prompt: str | None = None
    generate_kwargs: dict[str, Any] | None = field(default_factory=dict)
    timeout: float = 60.0
    max_retries: int = 2
    retry_base_delay: float = 1.0
    retry_backoff_factor: float = 2.0
    max_library_chars: int | None = 120_000
    attach_envelope: bool = True
    summary_width: int = 160
    auto_apply_patch: bool = False
    backup_before_write: bool = True
    library_file: str | None = None


class CapabilityUpgradeAgent:
    """Agent responsible for auditing and extending the capability library."""

    agent_name: str = "CapabilityUpgradeAgent"
    agent_stage: str = "library"
    agent_function: str = "capability_upgrade"

    def __init__(
        self,
        config: CapabilityUpgradeConfig | None = None,
        **overrides: Any,
    ) -> None:
        """Initialize the agent and underlying :class:`DeepSeekChatModel`."""

        config_data = asdict(config or CapabilityUpgradeConfig())
        config_data.update(overrides)

        api_key = config_data.get("api_key") or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError(
                "DeepSeek API key is required. Provide it via `api_key` "
                "or set the DEEPSEEK_API_KEY environment variable.",
            )

        timeout = float(config_data.get("timeout", 60.0) or 60.0)
        max_retries = int(config_data.get("max_retries", 2) or 0)
        retry_base_delay = float(config_data.get("retry_base_delay", 1.0) or 0.0)
        retry_backoff_factor = float(config_data.get("retry_backoff_factor", 2.0) or 1.0)

        self._model = DeepSeekChatModel(
            model_name=config_data.get("model_name", "deepseek-chat"),
            api_key=api_key,
            stream=bool(config_data.get("stream", False)),
            base_url=config_data.get("base_url", "https://api.deepseek.com"),
            reasoning_effort=config_data.get("reasoning_effort"),
            generate_kwargs=config_data.get("generate_kwargs") or {},
            timeout=timeout,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
            retry_backoff_factor=retry_backoff_factor,
        )

        max_library_chars = config_data.get("max_library_chars")
        self._max_library_chars: int | None = (
            int(max_library_chars) if max_library_chars is not None else None
        )
        self._library_snapshot: str | None = self._load_library_snapshot(self._max_library_chars)

        self._custom_system_prompt: bool = bool(config_data.get("system_prompt"))
        self._system_prompt: str | None = config_data.get("system_prompt") or self._compose_default_system_prompt()

        self._attach_envelope: bool = bool(config_data.get("attach_envelope", True))
        self._auto_apply_patch: bool = bool(config_data.get("auto_apply_patch", False))
        self._backup_before_write: bool = bool(config_data.get("backup_before_write", True))

        library_file = config_data.get("library_file") or str(
            ABILITY_LIBRARY_DIR / "core_capabilities.md"
        )
        self._library_file: Path = Path(library_file).expanduser().resolve()
        self._library_file.parent.mkdir(parents=True, exist_ok=True)

        self._last_patch_markdown: str | None = None
        self._last_applied_path: Path | None = None

    @property
    def system_prompt(self) -> str | None:
        """Return the current system prompt."""

        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, prompt: str | None) -> None:
        """Update the system prompt."""

        if prompt is None:
            self._system_prompt = None
            self._custom_system_prompt = False
            return

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("system_prompt must be a non-empty string.")

        self._system_prompt = prompt.strip()
        self._custom_system_prompt = True

    def refresh_system_prompt(
        self,
        *,
        force: bool = False,
        max_library_chars: int | None = None,
    ) -> None:
        """Reload the prompt template and library snapshot."""

        if max_library_chars is not None:
            self._max_library_chars = max(1, int(max_library_chars))

        self._library_snapshot = self._load_library_snapshot(self._max_library_chars)

        if force or not self._custom_system_prompt:
            self._system_prompt = self._compose_default_system_prompt()
            self._custom_system_prompt = False

    async def evaluate(
        self,
        *,
        metacognitive_report: str,
        suspected_new_capabilities: Sequence[str] | None = None,
        maintainer_notes: str | None = None,
        pending_updates: Sequence[str] | None = None,
        additional_context: str | None = None,
        library_snapshot: str | None = None,
        payload_contract: Any | None = None,
        structured_model: Any | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        """Evaluate whether new capabilities are required."""

        if not isinstance(metacognitive_report, str) or not metacognitive_report.strip():
            raise ValueError("metacognitive_report must be a non-empty string.")

        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        prompt = self._build_prompt(
            metacognitive_report=metacognitive_report,
            suspected_new_capabilities=suspected_new_capabilities,
            maintainer_notes=maintainer_notes,
            pending_updates=pending_updates,
            additional_context=additional_context,
            library_snapshot=library_snapshot,
        )
        messages.append({"role": "user", "content": prompt})

        result = await self._model(
            messages=messages,
            structured_model=structured_model,
            payload_contract=payload_contract,
            **kwargs,
        )

        if inspect.isasyncgen(result):
            return result

        if self._attach_envelope or self._auto_apply_patch:
            text_content = self._extract_text(result)
            patch_markdown = self._extract_patch_markdown(text_content)
            applied_path: Path | None = None
            if patch_markdown and self._auto_apply_patch:
                applied_path = self.apply_patch(patch_markdown)

            self._last_patch_markdown = patch_markdown
            self._last_applied_path = applied_path

            if self._attach_envelope:
                result = self._attach_agent_envelope(
                    result,
                    raw_text=text_content,
                    patch_markdown=patch_markdown,
                    applied_path=applied_path,
                )
        return result

    async def evaluate_text(self, **kwargs: Any) -> str:
        """Convenience wrapper returning plain text."""

        response = await self.evaluate(**kwargs)
        if inspect.isasyncgen(response):
            chunks: list[str] = []
            async for chunk in response:
                chunks.append(self._extract_text(chunk))
            return "".join(chunks).strip()

        text_content = self._extract_text(response)
        patch_markdown = self._extract_patch_markdown(text_content)

        applied_path: Path | None = self._last_applied_path if self._auto_apply_patch else None
        if patch_markdown and self._auto_apply_patch and applied_path is None:
            applied_path = self.apply_patch(patch_markdown)

        self._last_patch_markdown = patch_markdown
        self._last_applied_path = applied_path
        return text_content

    @property
    def last_patch_markdown(self) -> str | None:
        return self._last_patch_markdown

    @property
    def last_applied_path(self) -> Path | None:
        return self._last_applied_path

    def apply_patch(self, markdown: str, *, backup: bool | None = None) -> Path | None:
        """Append the generated capability definition to the library file."""

        patch = (markdown or "").strip()
        if not patch:
            return None

        target_file = self._library_file
        if backup is None:
            backup = self._backup_before_write

        if backup and target_file.exists():
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            backup_path = target_file.with_suffix(
                target_file.suffix + f".bak-{timestamp}"
            )
            backup_path.write_text(
                target_file.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        existing_size = target_file.stat().st_size if target_file.exists() else 0
        append_text = patch
        if existing_size > 0 and not patch.startswith("\n"):
            append_text = "\n\n" + append_text

        append_text = append_text.rstrip() + "\n"
        with target_file.open("a", encoding="utf-8") as handler:
            handler.write(append_text)

        self._last_patch_markdown = patch
        self._last_applied_path = target_file
        return target_file

    def _compose_default_system_prompt(self) -> str | None:
        """Combine prompt template with the capability library snapshot."""

        template = self._load_prompt_template()
        library_snapshot = self._library_snapshot

        if template and library_snapshot:
            return f"{template}\n\n## 当前能力库快照\n\n{library_snapshot}"
        if template:
            return template
        return library_snapshot

    @staticmethod
    def _load_prompt_template() -> str | None:
        """Load the system prompt template from ``thinking.md``."""

        if not PROMPT_PATH.exists():
            return None
        content = PROMPT_PATH.read_text(encoding="utf-8").strip()
        return content or None

    def _load_library_snapshot(self, max_chars: int | None) -> str | None:
        """Read ability library markdown files and merge into a snapshot."""

        if not ABILITY_LIBRARY_DIR.exists():
            return None

        sections: list[str] = []
        for md_file in sorted(ABILITY_LIBRARY_DIR.glob("*.md")):
            text = md_file.read_text(encoding="utf-8").strip()
            if not text:
                continue
            title = md_file.stem.replace("_", " ").title()
            sections.append(f"### {title}\n\n{text}")

        if not sections:
            return None

        combined = "\n\n".join(sections).strip()
        if max_chars is not None and len(combined) > max_chars:
            truncated = combined[: max_chars].rstrip()
            truncated += (
                "\n\n...[内容已截断，完整能力定义请查阅 ability_library 目录中的原始 Markdown 文件]..."
            )
            return truncated
        return combined

    def _build_prompt(
        self,
        *,
        metacognitive_report: str,
        suspected_new_capabilities: Sequence[str] | None,
        maintainer_notes: str | None,
        pending_updates: Sequence[str] | None,
        additional_context: str | None,
        library_snapshot: str | None,
    ) -> str:
        """Assemble the user prompt content."""

        sections: list[str] = [
            f"### Metacognitive Analysis Output\n{metacognitive_report.strip()}",
        ]

        if additional_context and additional_context.strip():
            sections.append(f"### Additional Context\n{additional_context.strip()}")

        suspected_lines = self._format_bullets(suspected_new_capabilities)
        if suspected_lines:
            sections.append("### Suspected New Capabilities\n" + "\n".join(suspected_lines))

        pending_lines = self._format_bullets(pending_updates)
        if pending_lines:
            sections.append("### Pending Library Updates\n" + "\n".join(pending_lines))

        if maintainer_notes and maintainer_notes.strip():
            sections.append(f"### Maintainer Notes\n{maintainer_notes.strip()}")

        snapshot = library_snapshot or self._library_snapshot
        if snapshot:
            sections.append("### Current Capability Library\n" + snapshot.strip())

        sections.append(
            "### Output Reminder\n"
            "仅在确认存在新增能力时输出对应的 Markdown 段落；若无需更新能力库，请返回空字符串。\n"
            "所有输出内容必须使用英文撰写，必要时可在括号内附注中文名词以保持可追溯性。",
        )

        return "\n\n".join(sections).strip()

    @staticmethod
    def _format_bullets(entries: Sequence[str] | None) -> list[str]:
        """Format a sequence of strings into bullet points."""

        if not entries:
            return []
        lines: list[str] = []
        for item in entries:
            if not isinstance(item, str):
                continue
            cleaned = item.strip()
            if cleaned:
                lines.append(f"- {cleaned}")
        return lines

    @staticmethod
    def _extract_text(response: ChatResponse) -> str:
        """Extract textual content from a :class:`ChatResponse`."""

        parts: list[str] = []
        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                parts.append(getattr(block, "text", "") or "")
            elif block_type == "thinking":
                parts.append("[Reasoning]\n" + (getattr(block, "thinking", "") or ""))
        if parts:
            return "\n".join(part.strip() for part in parts if part).strip()
        payload = getattr(response, "payload", None)
        if payload is not None:
            return str(payload)
        if response.metadata:
            return str(response.metadata)
        return ""

    @staticmethod
    def _extract_patch_markdown(text_content: str | None) -> str | None:
        """Extract the Markdown portion representing capability patch."""

        if not text_content:
            return None

        patch_lines: list[str] = []
        recording = False
        for line in text_content.splitlines():
            if not recording and line.strip().startswith("###"):
                recording = True
            if recording:
                patch_lines.append(line)

        patch = "\n".join(patch_lines).strip()
        return patch or None

    def _attach_agent_envelope(
        self,
        response: ChatResponse,
        *,
        raw_text: str,
        patch_markdown: str | None,
        applied_path: Path | None,
    ) -> ChatResponse:
        """Attach an agent envelope summarizing the capability update."""

        if not raw_text:
            return response

        return response


__all__ = [
    "CapabilityUpgradeConfig",
    "CapabilityUpgradeAgent",
]
