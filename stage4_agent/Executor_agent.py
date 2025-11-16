# -*- coding: utf-8 -*-
"""Stage 4 execution logging agent powered by DeepSeekChatModel."""

from __future__ import annotations

import inspect
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Iterable, Mapping, Sequence

import re

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from model import ChatResponse, DeepSeekChatModel
from workflow.finish_form_utils import update_form_section

from MCP.code_interpreter import code_interpreter_tool
from MCP.tavily import get_default_tavily_search_tool

PROMPT_PATH = Path(__file__).with_name("executor.md")


@dataclass(slots=True)
class ToolRunRecord:
    """结构化记录一次工具调用的结果，便于写入提示词与附件。"""

    step_id: str | None
    tool: str
    query: str
    status: str
    output: str | None = None
    full_output: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "step_id": self.step_id,
            "tool": self.tool,
            "query": self.query,
            "status": self.status,
            "output": self.output,
            "full_output": self.full_output,
            "error": self.error,
        }
        return {key: value for key, value in payload.items() if value is not None}


@dataclass(slots=True)
class Stage4ExecutorAgentConfig:
    """Configuration container for :class:`Stage4ExecutorAgent`."""

    api_key: str | None = None
    model_name: str = "deepseek-chat"
    stream: bool = False
    base_url: str = "https://api.deepseek.com"
    reasoning_effort: str | None = "medium"
    system_prompt: str | None = None
    generate_kwargs: dict[str, Any] | None = field(default_factory=dict)


class Stage4ExecutorAgent:
    """Agent responsible for transforming execution plans into actionable logs."""

    agent_name: str = "Stage4ExecutorAgent"
    agent_stage: str = "stage4"
    agent_function: str = "execution_reporting"
    FINAL_ANSWER_LABEL_RE = re.compile(
        r"(?:\*\*)?(?:最终答案|Final answer)(?:\*\*)?[:：]\s*",
        re.IGNORECASE,
    )
    ANSWER_HINT_RE = re.compile(r"(?:答案|answer)", re.IGNORECASE)

    def __init__(
        self,
        config: Stage4ExecutorAgentConfig | None = None,
        **overrides: Any,
    ) -> None:
        config_data = asdict(config or Stage4ExecutorAgentConfig())
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
        """Update the system prompt used for execution logging."""

        if prompt is None:
            self._system_prompt = None
            return
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("System prompt must be a non-empty string when provided.")
        self._system_prompt = prompt.strip()

    async def analyze(
        self,
        *,
        execution_plan: Mapping[str, Any],
        objective: str | None = None,
        meta_analysis: str | None = None,
        refined_strategy: Mapping[str, Any] | None = None,
        handover_notes: Mapping[str, Any] | Sequence[Any] | None = None,
        success_criteria: Sequence[Any] | str | None = None,
        failure_indicators: Sequence[Any] | str | None = None,
        required_capabilities: Sequence[Mapping[str, Any]] | None = None,
        timeliness_and_knowledge_boundary: Mapping[str, Any] | None = None,
        external_constraints: Sequence[str] | None = None,
        tool_catalog: Sequence[str] | None = None,
        context_snapshot: str | None = None,
        prior_execution_state: Mapping[str, Any] | None = None,
        evidence_inputs: Sequence[Mapping[str, Any]] | None = None,
        attachments: Mapping[str, Any] | Sequence[Any] | None = None,
        structured_model: Any | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        """Generate execution-ready logs based on Stage 3 plans."""

        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        prompt = self._build_prompt(
            execution_plan=execution_plan,
            objective=objective,
            meta_analysis=meta_analysis,
            refined_strategy=refined_strategy,
            handover_notes=handover_notes,
            success_criteria=success_criteria,
            failure_indicators=failure_indicators,
            required_capabilities=required_capabilities,
            timeliness_and_knowledge_boundary=timeliness_and_knowledge_boundary,
            external_constraints=external_constraints,
            tool_catalog=tool_catalog,
            context_snapshot=context_snapshot,
            prior_execution_state=prior_execution_state,
            evidence_inputs=evidence_inputs,
            attachments=attachments,
            tool_run_log=kwargs.pop("tool_run_log", None),
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
        finish_form_marker = kwargs.pop("finish_form_marker", "STAGE4_EXECUTION")
        finish_form_header = kwargs.pop(
            "finish_form_header",
            "## 执行阶段：任务落实（Executor）",
        )

        plan_text = self._stringify_execution_plan(kwargs.get("execution_plan"))

        tool_run_log, tool_run_records = await self._collect_tool_runs(
            plan_text=plan_text,
            objective=kwargs.get("objective"),
            tool_catalog=kwargs.get("tool_catalog"),
        )
        if tool_run_log:
            kwargs["tool_run_log"] = tool_run_log
            kwargs["attachments"] = self._merge_tool_run_attachment(
                kwargs.get("attachments"),
                tool_run_records,
            )

        response = await self.analyze(**kwargs)

        if inspect.isasyncgen(response):
            chunks: list[str] = []
            async for item in response:
                chunks.append(self._extract_text(item))
            result_text = "".join(chunks).strip()
        else:
            result_text = self._extract_text(response)

        result_text = self._ensure_final_answer_line(result_text)

        if finish_form_path:
            self._write_finish_form(
                finish_form_path,
                result_text,
                marker=finish_form_marker,
                header=finish_form_header,
            )

        return result_text

    async def _collect_tool_runs(
        self,
        *,
        plan_text: str | None,
        objective: str | None,
        tool_catalog: Sequence[str] | None,
    ) -> tuple[str | None, list[ToolRunRecord]]:
        records: list[ToolRunRecord] = []

        records.extend(
            await self._execute_search_queries(
                plan_text=plan_text,
                objective=objective,
                tool_catalog=tool_catalog,
            )
        )

        records.extend(
            await self._execute_code_blocks(
                plan_text=plan_text,
                tool_catalog=tool_catalog,
            )
        )

        if not records:
            return None, []

        log_text = self._format_tool_run_log(records)
        return log_text or None, records

    async def _execute_search_queries(
        self,
        *,
        plan_text: str | None,
        objective: str | None,
        tool_catalog: Sequence[str] | None,
    ) -> list[ToolRunRecord]:
        queries: list[dict[str, Any]] = []

        extracted = self._extract_search_queries(plan_text)
        if extracted:
            queries.extend(extracted)

        if not queries and isinstance(objective, str) and objective.strip():
            queries.append({"step": None, "query": objective.strip()})

        if not queries:
            return []

        has_tool_listing = self._has_tavily_tool(tool_catalog)
        has_env_token = bool(os.getenv("TAVILY_API_KEY"))
        if not (has_tool_listing or has_env_token):
            return [
                ToolRunRecord(
                    step_id=item["step"],
                    tool="Tavily.search",
                    query=item["query"],
                    status="skipped",
                    error="未在工具清单发现 Tavily，且未配置 TAVILY_API_KEY。",
                )
                for item in queries
            ]

        try:
            search_tool = await get_default_tavily_search_tool()
        except Exception as exc:  # pylint: disable=broad-except
            message = self._describe_exception(exc)
            return [
                ToolRunRecord(
                    step_id=item["step"],
                    tool="Tavily.search",
                    query=item["query"],
                    status="error",
                    error=message,
                )
                for item in queries
            ]

        records: list[ToolRunRecord] = []
        for item in queries:
            step_id = item["step"]
            query = item["query"]
            try:
                response = await search_tool(query=query)
            except Exception as exc:  # pylint: disable=broad-except
                records.append(
                    ToolRunRecord(
                        step_id=step_id,
                        tool="Tavily.search",
                        query=query,
                        status="error",
                        error=self._describe_exception(exc),
                    )
                )
                continue

            response_text = getattr(response, "content", None)
            if isinstance(response_text, str):
                response_text = response_text.strip()
            else:
                response_text = str(response).strip()

            records.append(
                ToolRunRecord(
                    step_id=step_id,
                    tool="Tavily.search",
                    query=query,
                    status="success",
                    output=response_text or None,
                    full_output=response_text or None,
                )
            )

        return records

    async def _execute_code_blocks(
        self,
        *,
        plan_text: str | None,
        tool_catalog: Sequence[str] | None,
    ) -> list[ToolRunRecord]:
        code_blocks = self._extract_python_blocks(plan_text)
        if not code_blocks:
            return []

        if not self._has_code_interpreter_tool(tool_catalog):
            return [
                ToolRunRecord(
                    step_id=block.get("step"),
                    tool="CodeInterpreter.python",
                    query=self._truncate_text(block["code"]),
                    status="skipped",
                    error="工具清单未包含 Code Interpreter 或未启用本地服务。",
                )
                for block in code_blocks
            ]

        records: list[ToolRunRecord] = []
        try:
            async with code_interpreter_tool("python") as python_tool:
                for block in code_blocks:
                    code_snippet = block["code"]
                    step_id = block.get("step")
                    try:
                        response = await python_tool(code=code_snippet)
                        output_text = getattr(response, "content", None)
                        if isinstance(output_text, str):
                            output_text = output_text.strip()
                        else:
                            output_text = str(response).strip()
                        records.append(
                            ToolRunRecord(
                                step_id=step_id,
                                tool="CodeInterpreter.python",
                                query=self._truncate_text(code_snippet),
                                status="success",
                                output=self._truncate_text(output_text),
                                full_output=output_text or None,
                            )
                        )
                    except Exception as exc:  # pylint: disable=broad-except
                        records.append(
                            ToolRunRecord(
                                step_id=step_id,
                                tool="CodeInterpreter.python",
                                query=self._truncate_text(code_snippet),
                                status="error",
                                error=self._describe_exception(exc),
                            )
                        )
        except Exception as exc:  # pylint: disable=broad-except
            message = self._describe_exception(exc)
            return [
                ToolRunRecord(
                    step_id=block.get("step"),
                    tool="CodeInterpreter.python",
                    query=self._truncate_text(block["code"]),
                    status="error",
                    error=message,
                )
                for block in code_blocks
            ]

        return records

    @staticmethod
    def _merge_tool_run_attachment(
        existing: Mapping[str, Any] | Sequence[Any] | None,
        records: Iterable[ToolRunRecord],
    ) -> Mapping[str, Any] | Sequence[Any] | None:
        serialized = [record.as_dict() for record in records]
        if not serialized:
            return existing

        if existing is None:
            return {"tool_runs": serialized}

        if isinstance(existing, Mapping):
            merged = dict(existing)
            merged.setdefault("tool_runs", serialized)
            return merged

        if isinstance(existing, Sequence) and not isinstance(existing, (str, bytes)):
            return [*existing, {"tool_runs": serialized}]

        return existing

    @staticmethod
    def _has_tavily_tool(tool_catalog: Sequence[str] | None) -> bool:
        if not tool_catalog:
            return False
        return any("tavily" in entry.lower() for entry in tool_catalog)

    @staticmethod
    def _has_code_interpreter_tool(tool_catalog: Sequence[str] | None) -> bool:
        if not tool_catalog:
            return False
        lowered = [entry.lower() for entry in tool_catalog]
        return any("code interpreter" in entry or "python" in entry for entry in lowered)

    @staticmethod
    def _describe_exception(exc: Exception) -> str:
        return f"{exc.__class__.__name__}: {exc}"

    @staticmethod
    def _format_tool_run_log(records: Iterable[ToolRunRecord]) -> str:
        lines: list[str] = []
        for record in records:
            header_parts = []
            if record.step_id:
                header_parts.append(str(record.step_id))
            header_parts.append(record.tool)
            header = " · ".join(header_parts)
            lines.append(f"- {header}")
            lines.append(f"  Query: {record.query}")
            lines.append(f"  Status: {record.status}")
            if record.error:
                lines.append(f"  Error: {record.error}")
            if record.output:
                lines.append(f"  Output: {record.output}")
        return "\n".join(lines).strip()

    def _build_prompt(
        self,
        *,
        execution_plan: Any,
        objective: str | None,
        meta_analysis: str | None,
        refined_strategy: Mapping[str, Any] | Sequence[Any] | str | None,
        handover_notes: Mapping[str, Any] | Sequence[Any] | str | None,
        success_criteria: Sequence[Any] | str | None,
        failure_indicators: Sequence[Any] | str | None,
        required_capabilities: Sequence[Mapping[str, Any]] | None,
        timeliness_and_knowledge_boundary: Mapping[str, Any] | str | None,
        external_constraints: Sequence[str] | None,
        tool_catalog: Sequence[str] | None,
        context_snapshot: str | None,
        prior_execution_state: Mapping[str, Any] | None,
        evidence_inputs: Sequence[Mapping[str, Any]] | None,
        attachments: Mapping[str, Any] | Sequence[Any] | None,
        tool_run_log: str | None = None,
    ) -> str:
        sections: list[str] = []

        if objective:
            sections.append(f"### OBJECTIVE\n{objective.strip()}")

        output_language = self._infer_output_language(objective, meta_analysis, context_snapshot)
        sections.append(f"### OUTPUT_LANGUAGE\n{output_language}")

        plan_block = self._format_section_content(execution_plan)
        if plan_block:
            sections.append("### EXECUTION_PLAN\n" + plan_block)

        if meta_analysis:
            sections.append(f"### META_ANALYSIS\n{meta_analysis.strip()}")

        refined_block = self._format_section_content(refined_strategy)
        if refined_block:
            sections.append("### REFINED_STRATEGY\n" + refined_block)

        handover_block = self._format_section_content(handover_notes)
        if handover_block:
            sections.append("### HANDOVER_NOTES\n" + handover_block)

        normalized_success = self._normalize_to_list(success_criteria)
        if not normalized_success and refined_strategy:
            normalized_success = self._extract_from_mapping(refined_strategy, "success_criteria")
        if normalized_success:
            success_block = "\n".join(f"- {item}" for item in normalized_success)
            sections.append(f"### SUCCESS_CRITERIA\n{success_block}")

        normalized_failure = self._normalize_to_list(failure_indicators)
        if not normalized_failure and refined_strategy:
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
                role = capability.get("role")
                risk = capability.get("risk")
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
                + self._format_section_content(timeliness_and_knowledge_boundary)
            )

        if external_constraints:
            constraint_lines = [
                f"- {str(item).strip()}" for item in external_constraints if str(item).strip()
            ]
            if constraint_lines:
                sections.append("### EXECUTION_CONSTRAINTS\n" + "\n".join(constraint_lines))

        if tool_catalog:
            tool_lines = [f"- {tool}" for tool in tool_catalog if str(tool).strip()]
            if tool_lines:
                sections.append("### TOOL_CATALOG\n" + "\n".join(tool_lines))

        if context_snapshot:
            sections.append(f"### SUPPLEMENTAL_CONTEXT\n{context_snapshot.strip()}")

        if prior_execution_state:
            sections.append("### PRIOR_EXECUTION_STATE\n" + self._format_json(prior_execution_state))

        if evidence_inputs:
            sections.append("### EVIDENCE_INPUTS\n" + self._format_json(list(evidence_inputs)))

        if attachments:
            sections.append("### ATTACHMENTS\n" + self._format_json(attachments))

        if tool_run_log:
            sections.append("### TOOL_RUN_LOG\n" + tool_run_log.strip())

        sections.append(
            "### TASK_DIRECTIVES\n"
            "1. 对照执行计划逐条落实，填写表单内“执行准备检查”“执行记录”“总结与反馈”等字段。\n"
            "2. 对每个 step_id 记录实际耗时、结果、偏差、后续行动，保持与 Stage 3 命名一致。\n"
            "3. 若触发失败信号或风险阈值，记录触发条件、影响范围与采取的回退措施。\n"
            "4. 结合 success_criteria 评估目标达成度，提炼经验并反馈给上游阶段。\n"
            "5. OUTPUT_LANGUAGE 恒定为 English，请全程使用英文输出并保持与模板一致。\n"
            "6. 若任何工具执行失败或未实际调用，必须在执行记录中如实说明原因，严禁编造成功结果。"
        )

        sections.append(
            "### OUTPUT_GUIDELINES\n"
            "- 首先更新执行准备检查表，标注未满足项与补救计划。\n"
            "- 按 step_id 顺序描述执行过程，区分串行/并行关系，突出关键产出与验证方式。\n"
            "- 明确监控指标的状态与风险处理结果，提供回退或补救措施。\n"
            "- 在总结中说明目标达成度、经验沉淀、回传建议及待跟进事项。\n"
            "- 若存在附件或引用，请列出路径或链接，确保审计可追溯。"
        )

        return "\n\n".join(section for section in sections if section.strip())

    @staticmethod
    def _stringify_execution_plan(execution_plan: Any) -> str | None:
        if execution_plan is None:
            return None
        if isinstance(execution_plan, str):
            return execution_plan.strip() or None
        if isinstance(execution_plan, Mapping):
            try:
                return json.dumps(execution_plan, ensure_ascii=False, indent=2)
            except TypeError:
                return repr(execution_plan)
        if isinstance(execution_plan, Sequence) and not isinstance(execution_plan, (str, bytes)):
            try:
                return json.dumps(list(execution_plan), ensure_ascii=False, indent=2)
            except TypeError:
                return "\n".join(str(item) for item in execution_plan)
        return str(execution_plan)

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

    @classmethod
    def _ensure_final_answer_line(cls, text: str | None) -> str:
        if not text:
            return ""
        if cls.FINAL_ANSWER_LABEL_RE.search(text):
            return text
        candidate = cls._find_final_answer_candidate(text)
        if not candidate:
            return text
        return text.rstrip() + f"\n\n**最终答案**: {candidate}"

    @classmethod
    def _find_final_answer_candidate(cls, text: str) -> str | None:
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        if not lines:
            return None
        for line in reversed(lines):
            if cls.ANSWER_HINT_RE.search(line):
                return line
        return lines[-1]

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
    def _extract_from_mapping(mapping: Any, key: str) -> list[str]:
        if not isinstance(mapping, Mapping):
            return []
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
    def _format_section_content(data: Any) -> str:
        if data is None:
            return ""
        if isinstance(data, str):
            return data.strip()
        return Stage4ExecutorAgent._format_json(data)

    @staticmethod
    def _infer_output_language(*texts: str | None) -> str:
        return "English"

    @staticmethod
    def _truncate_text(text: str | None, limit: int = 400) -> str:
        if not text:
            return ""
        text = text.strip()
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    @staticmethod
    def _extract_search_queries(plan_text: str | None) -> list[dict[str, Any]]:
        if not plan_text:
            return []

        pattern = re.compile(
            r"(?:搜索|查询|search)\s*[:：]\s*(?P<query>[^\n]+)", re.IGNORECASE
        )
        queries: list[dict[str, Any]] = []
        seen: set[str] = set()

        for line in plan_text.splitlines():
            match = pattern.search(line)
            if not match:
                continue
            query = match.group("query").strip()
            if not query or query in seen:
                continue
            seen.add(query)
            step = None
            step_match = re.search(r"\b(S\d+-\d+|Step-\d+)\b", line)
            if step_match:
                step = step_match.group(1)
            queries.append({"step": step, "query": query})

        return queries

    @staticmethod
    def _extract_python_blocks(plan_text: str | None) -> list[dict[str, Any]]:
        if not plan_text:
            return []

        code_pattern = re.compile(r"```python\s+(?P<code>.*?)```", re.IGNORECASE | re.DOTALL)
        blocks: list[dict[str, Any]] = []

        for match in code_pattern.finditer(plan_text):
            code = match.group("code").strip()
            if not code:
                continue
            prefix = plan_text[: match.start()]
            step_candidates = re.findall(r"(S\d+-\d+|Step-\d+)", prefix)
            step_id = step_candidates[-1] if step_candidates else None
            blocks.append({"step": step_id, "code": code})

        return blocks

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
    "Stage4ExecutorAgent",
    "Stage4ExecutorAgentConfig",
]



