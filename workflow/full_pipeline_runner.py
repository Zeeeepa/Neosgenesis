# -*- coding: utf-8 -*-
"""多阶段代理全流程调度器。

该脚本负责串联模板生成、阶段 1-4 代理、Stage 2 策略能力升级代理（负责策略库）与能力升级代理（维护能力库）。
Stage 1 元分析代理仅访问能力库，不直接修改策略库；策略库的变更由 Stage 2 策略能力升级代理统一产出。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import httpx

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from Document_Checking.template_generation import (
    TemplateGenerationAgent,
    TemplateGenerationConfig,
)
from capability_upgrade_agent.capability_upgrade_agent import (
    CapabilityUpgradeAgent,
    CapabilityUpgradeConfig,
)
from stage1_agent.Metacognitive_Analysis_agnet import (
    MetacognitiveAnalysisAgent,
    MetacognitiveAgentConfig,
)
from stage2_agent.Strategy_Selection_agent import (
    StrategySelectionAgent,
    StrategySelectionAgentConfig,
)
from stage2_candidate_agent.Candidate_Selection_agent import (
    CandidateSelectionAgent,
    CandidateSelectionAgentConfig,
)
from stage2_capability_upgrade_agent.stage2_capability_upgrade_agent import (
    Stage2CapabilityUpgradeAgent,
    Stage2CapabilityUpgradeConfig,
)
from stage3_agent.Step_agent import Stage3ExecutionAgent, Stage3ExecutionAgentConfig
from stage4_agent.Executor_agent import Stage4ExecutorAgent, Stage4ExecutorAgentConfig



@dataclass(slots=True)
class SharedModelConfig:
    """共享模型配置，便于统一注入各代理。"""

    api_key: str | None = None
    model_name: str = "deepseek-chat"
    stream: bool = False
    base_url: str = "https://api.deepseek.com"
    reasoning_effort: str | None = "medium"


class FullPipelineRunner:
    """封装阶段 1-4 与能力升级代理的调度逻辑。"""

    def __init__(
        self,
        *,
        shared_config: SharedModelConfig,
        finish_form_dir: Path | None = None,
        template_path: Path | None = None,
        encoding: str = "utf-8",
        template_threshold: int = 8,
        strategy_auto_apply: bool = True,
        capability_auto_apply: bool = False,
    ) -> None:
        self._encoding = encoding
        self._finish_form_dir = Path(finish_form_dir or PROJECT_ROOT / "finish_form").expanduser().resolve()
        self._template_path = Path(
            template_path or PROJECT_ROOT / "form_templates" / "standard template.md"
        ).expanduser().resolve()
        self._finish_form_dir.mkdir(parents=True, exist_ok=True)

        if not self._template_path.is_file():
            raise FileNotFoundError(f"模板文件未找到: {self._template_path}")

        shared_kwargs = {
            "api_key": shared_config.api_key or os.getenv("DEEPSEEK_API_KEY"),
            "model_name": shared_config.model_name,
            "stream": shared_config.stream,
            "base_url": shared_config.base_url,
            "reasoning_effort": shared_config.reasoning_effort,
        }
        if not shared_kwargs["api_key"]:
            raise ValueError("未检测到 DeepSeek API Key，请通过参数或环境变量提供。")

        template_config = TemplateGenerationConfig(
            threshold=template_threshold,
            finish_form_dir=self._finish_form_dir,
            template_path=self._template_path,
            encoding=encoding,
        )
        self._template_agent = TemplateGenerationAgent(config=template_config)

        self._stage1_agent = MetacognitiveAnalysisAgent(MetacognitiveAgentConfig(**shared_kwargs))
        self._candidate_agent = CandidateSelectionAgent(CandidateSelectionAgentConfig(**shared_kwargs))
        self._stage2_agent = StrategySelectionAgent(StrategySelectionAgentConfig(**shared_kwargs))
        self._stage2_selection_retry_attempts = 3
        self._stage2_selection_retry_delay = 1.0

        stage2_upgrade_config = Stage2CapabilityUpgradeConfig(
            api_key=shared_kwargs["api_key"],
            model_name=shared_kwargs["model_name"],
            stream=shared_kwargs["stream"],
            base_url=shared_kwargs["base_url"],
            reasoning_effort=shared_kwargs["reasoning_effort"],
            auto_apply_patch=strategy_auto_apply,
        )
        self._stage2_upgrade_agent = Stage2CapabilityUpgradeAgent(config=stage2_upgrade_config)

        capability_config = CapabilityUpgradeConfig(
            api_key=shared_kwargs["api_key"],
            model_name=shared_kwargs["model_name"],
            stream=shared_kwargs["stream"],
            base_url=shared_kwargs["base_url"],
            reasoning_effort=shared_kwargs["reasoning_effort"],
            auto_apply_patch=capability_auto_apply,
        )
        self._capability_agent = CapabilityUpgradeAgent(config=capability_config)

        self._stage3_agent = Stage3ExecutionAgent(Stage3ExecutionAgentConfig(**shared_kwargs))
        self._stage4_agent = Stage4ExecutorAgent(Stage4ExecutorAgentConfig(**shared_kwargs))

    async def run(
        self,
        *,
        objective: str,
        context_snapshot: str | None = None,
        candidate_limit: int | None = None,
        tool_catalog: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """依次执行阶段 1-4 与能力升级代理，返回各阶段原始输出。"""

        document_path = self._prepare_finish_form_document()
        index_block = self._extract_index_block(document_path)

        stage1_text = await self._run_stage1(
            document_path,
            objective=objective,
            user_context=context_snapshot,
            index_block=index_block,
            tool_catalog=tool_catalog,
        )

        stage2_candidate_text = await self._run_stage2_candidate(
            document_path,
            objective=objective,
            meta_text=stage1_text,
            candidate_limit=candidate_limit,
        )

        stage2_selection_text = await self._run_stage2_selection(
            document_path,
            objective=objective,
            meta_text=stage1_text,
            candidate_text=stage2_candidate_text,
            context_snapshot=context_snapshot,
        )

        stage2_upgrade_text = await self._run_stage2_upgrade(
            document_path,
            selection_text=stage2_selection_text,
        )

        stage3_text = await self._run_stage3(
            document_path,
            objective=objective,
            meta_text=stage1_text,
            stage2_selection_text=stage2_selection_text,
            context_snapshot=context_snapshot,
            tool_catalog=tool_catalog,
        )

        stage4_text = await self._run_stage4(
            document_path,
            objective=objective,
            meta_text=stage1_text,
            stage2_selection_text=stage2_selection_text,
            stage3_text=stage3_text,
            context_snapshot=context_snapshot,
            tool_catalog=tool_catalog,
        )

        capability_upgrade_text = await self._run_capability_upgrade(stage1_text)

        return {
            "document": self._relativize(document_path),
            "stage1": stage1_text,
            "stage2_candidate": stage2_candidate_text,
            "stage2_selection": stage2_selection_text,
            "stage2_upgrade": stage2_upgrade_text,
            "stage3": stage3_text,
            "stage4": stage4_text,
            "capability_upgrade": capability_upgrade_text,
        }

    def _prepare_finish_form_document(self) -> Path:
        before = set(self._finish_form_dir.glob("*.md"))
        result = self._template_agent.run()
        created = result.get("created")
        if created:
            candidate = (PROJECT_ROOT / created).resolve()
            if candidate.exists():
                return candidate

        after = set(self._finish_form_dir.glob("*.md"))
        new_docs = after - before
        if new_docs:
            return max(new_docs, key=lambda item: item.stat().st_mtime)

        if after:
            return max(after, key=lambda item: item.stat().st_mtime)

        raise RuntimeError("未能创建或定位 finish_form 文档。")

    def _read_document(self, path: Path) -> str:
        return path.read_text(encoding=self._encoding)

    def _extract_index_block(self, path: Path) -> str:
        text = self._read_document(path)
        match = re.search(r"## 索引.*?(?=\n## )", text, re.DOTALL)
        if match:
            return match.group(0).strip()
        return ""


    @staticmethod
    def _relativize(path: Path) -> str:
        try:
            return path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            return path.as_posix()

    def _build_stage1_context(
        self,
        *,
        index_block: str,
        user_context: str | None,
    ) -> str:
        sections: list[str] = []
        if user_context:
            sections.append("### 用户附加上下文\n" + user_context.strip())
        if index_block:
            sections.append("### 协作表单索引快照\n" + index_block.strip())
        sections.append(
            "### 文档写入提醒\n"
            "1. 基于索引确认锚点位置，将完整分析写入 `<!-- STAGE1_ANALYSIS_START -->` 与 `<!-- STAGE1_ANALYSIS_END -->` 之间。\n"
            "2. 输出需涵盖问题诊断、所需能力、风险及质量评估，为下游阶段提供引用。"
        )
        return "\n\n".join(section for section in sections if section.strip())

    async def _run_stage1(
        self,
        document_path: Path,
        *,
        objective: str,
        user_context: str | None,
        index_block: str,
        tool_catalog: Sequence[str] | None,
    ) -> str:
        context_block = self._build_stage1_context(
            index_block=index_block,
            user_context=user_context,
        )
        try:
            result_text = await self._stage1_agent.analyze_text(
                objective=objective,
                context=context_block or None,
                tool_catalog=tool_catalog,
                finish_form_path=str(document_path),
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._log_stage_exception("阶段一代理执行失败", exc)
            raise

        return self._normalize_stage_output(result_text)

    async def _run_stage2_candidate(
        self,
        document_path: Path,
        *,
        objective: str,
        meta_text: str,
        candidate_limit: int | None,
    ) -> str:
        kwargs: dict[str, Any] = {}
        if candidate_limit is not None:
            kwargs["candidate_limit"] = candidate_limit

        try:
            result_text = await self._candidate_agent.analyze_text(
                meta_analysis=meta_text,
                objective=objective,
                finish_form_path=str(document_path),
                **kwargs,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._log_stage_exception("阶段二-A 候选策略生成失败", exc)
            raise

        return self._normalize_stage_output(result_text)

    async def _run_stage2_selection(
        self,
        document_path: Path,
        *,
        objective: str,
        meta_text: str,
        candidate_text: str,
        context_snapshot: str | None,
    ) -> str:
        try:
            result_text = await self._run_stage2_selection_with_retries(
                document_path=document_path,
                meta_text=meta_text,
                candidate_text=candidate_text,
                objective=objective,
                context_snapshot=context_snapshot,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._log_stage_exception("阶段二-B 策略遴选失败", exc)
            raise

        return self._normalize_stage_output(result_text)

    async def _run_stage2_selection_with_retries(
        self,
        *,
        document_path: Path,
        meta_text: str,
        candidate_text: str,
        objective: str,
        context_snapshot: str | None,
    ) -> str:
        retries = 0
        while True:
            try:
                return await self._stage2_agent.analyze_text(
                    meta_analysis=meta_text,
                    candidate_sheet=candidate_text,
                    objective=objective,
                    context_snapshot=context_snapshot,
                    finish_form_path=str(document_path),
                )
            except httpx.HTTPError as exc:
                retries += 1
                if retries >= self._stage2_selection_retry_attempts:
                    raise
                LOGGER.warning(
                    "Stage 2 Selection attempt %d/%d failed: %s; retrying after %.1fs",
                    retries,
                    self._stage2_selection_retry_attempts,
                    exc,
                    self._stage2_selection_retry_delay,
                )
                await asyncio.sleep(self._stage2_selection_retry_delay)

    async def _run_stage2_upgrade(
        self,
        document_path: Path,
        *,
        selection_text: str,
    ) -> str | None:
        try:
            result_text = await self._stage2_upgrade_agent.evaluate_text(
                metacognitive_report=selection_text,
                suspected_new_capabilities=None,  # No longer extracting from JSON
                finish_form_path=str(document_path),
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._log_stage_exception("阶段二-C 策略库升级代理执行失败", exc)
            raise

        body = self._normalize_stage_output(result_text).strip()
        return body or None

    async def _run_stage3(
        self,
        document_path: Path,
        *,
        objective: str,
        meta_text: str,
        stage2_selection_text: str,
        context_snapshot: str | None,
        tool_catalog: Sequence[str] | None,
    ) -> str:
        try:
            # Note: Stage3 agent may need to be updated to accept raw text instead of structured data
            result_text = await self._stage3_agent.analyze_text(
                meta_analysis=meta_text,
                refined_strategy={},  # Placeholder - stage3 agent should parse from stage2_selection_text
                handover_notes={},   # Placeholder - stage3 agent should parse from stage2_selection_text
                objective=objective,
                context_snapshot=context_snapshot,
                tool_catalog=tool_catalog,
                finish_form_path=str(document_path),
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._log_stage_exception("阶段三执行规划代理执行失败", exc)
            raise

        return self._normalize_stage_output(result_text)

    async def _run_stage4(
        self,
        document_path: Path,
        *,
        objective: str,
        meta_text: str,
        stage2_selection_text: str,
        stage3_text: str,
        context_snapshot: str | None,
        tool_catalog: Sequence[str] | None,
    ) -> str:
        try:
            # Note: Stage4 agent may need to be updated to accept raw text instead of structured data
            result_text = await self._stage4_agent.analyze_text(
                execution_plan=stage3_text,
                objective=objective,
                meta_analysis=meta_text,
                refined_strategy=None,
                handover_notes=None,
                context_snapshot=context_snapshot,
                tool_catalog=tool_catalog,
                finish_form_path=str(document_path),
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._log_stage_exception("阶段四执行记录代理执行失败", exc)
            raise

        return self._normalize_stage_output(result_text)

    async def _run_capability_upgrade(self, stage1_text: str) -> str | None:
        try:
            result_text = await self._capability_agent.evaluate_text(
                metacognitive_report=stage1_text,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._log_stage_exception("能力库升级代理执行失败", exc)
            raise
        return self._normalize_stage_output(result_text).strip() or None

    @staticmethod
    def _log_stage_exception(stage: str, exc: Exception) -> None:
        import traceback

        print("\n" + "=" * 60)
        print(f"{stage}，异常详情：{exc.__class__.__name__}: {exc}")
        traceback.print_exc(limit=None)
        print("=" * 60 + "\n")

    @staticmethod
    def _normalize_stage_output(value: Any) -> str:
        """Normalize various MCP/Stage agent outputs into plain text."""

        if value is None:
            return ""

        if isinstance(value, str):
            return value

        if isinstance(value, (list, tuple)):
            segments = [
                FullPipelineRunner._normalize_stage_output(item).strip()
                for item in value
            ]
            return "\n".join(segment for segment in segments if segment)

        if isinstance(value, dict):
            for key in ("text", "content"):
                candidate = value.get(key)
                if candidate is not None:
                    return FullPipelineRunner._normalize_stage_output(candidate)
            segments: list[str] = []
            for key, item in value.items():
                normalized = FullPipelineRunner._normalize_stage_output(item).strip()
                if normalized:
                    segments.append(f"{key}: {normalized}")
            return "\n".join(segments)

        text_attr = getattr(value, "text", None)
        if isinstance(text_attr, str):
            return text_attr

        content_attr = getattr(value, "content", None)
        if content_attr is not None:
            return FullPipelineRunner._normalize_stage_output(content_attr)

        if hasattr(value, "__dict__"):
            try:
                payload = {
                    key: val
                    for key, val in value.__dict__.items()
                    if not key.startswith("_")
                }
            except Exception:
                payload = None
            if payload:
                try:
                    return json.dumps(payload, ensure_ascii=False)
                except TypeError:
                    pass

        return str(value)


def _parse_tool_catalog(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="运行阶段 1-4 代理与能力升级代理的全流程调度器。",
    )
    parser.add_argument("--objective", help="任务目标描述。")
    parser.add_argument("--context", help="补充上下文说明。")
    parser.add_argument("--candidate-limit", type=int, help="候选策略数量上限。")
    parser.add_argument("--finish-dir", type=Path, help="finish_form 目录路径。")
    parser.add_argument("--template", type=Path, help="标准模板文件路径。")
    parser.add_argument("--encoding", default="utf-8", help="文档读写编码（默认 utf-8）。")
    parser.add_argument("--api-key", dest="api_key", help="DeepSeek API Key，如省略则读取环境变量。")
    parser.add_argument("--model", default="deepseek-chat", help="模型名称。")
    parser.add_argument("--base-url", default="https://api.deepseek.com", help="模型服务基础地址。")
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        default="medium",
        help="推理强度设置。",
    )
    parser.add_argument("--stream", action="store_true", help="启用流式输出。")
    parser.add_argument(
        "--no-strategy-auto-apply",
        action="store_true",
        help="禁用阶段二策略库自动写入。",
    )
    parser.add_argument(
        "--auto-apply-capability",
        action="store_true",
        help="启用能力库自动写入。",
    )
    parser.add_argument(
        "--tool-catalog",
        help="可用工具清单，使用逗号分隔（例如：foo,bar）。",
    )
    return parser.parse_args()


async def _async_main(args: argparse.Namespace) -> dict[str, Any]:
    shared_config = SharedModelConfig(
        api_key=args.api_key,
        model_name=args.model,
        stream=args.stream,
        base_url=args.base_url,
        reasoning_effort=args.reasoning_effort,
    )
    runner = FullPipelineRunner(
        shared_config=shared_config,
        finish_form_dir=args.finish_dir,
        template_path=args.template,
        encoding=args.encoding,
        strategy_auto_apply=not args.no_strategy_auto_apply,
        capability_auto_apply=args.auto_apply_capability,
    )
    tool_catalog = _parse_tool_catalog(args.tool_catalog)
    return await runner.run(
        objective=args.objective,
        context_snapshot=args.context,
        candidate_limit=args.candidate_limit,
        tool_catalog=tool_catalog,
    )


def main() -> None:
    args = _parse_args()
    if not args.objective:
        try:
            args.objective = input("请输入任务目标: ").strip()
        except KeyboardInterrupt:
            print("\n已取消。")
            raise SystemExit(130) from None
    if not args.objective:
        print("未提供任务目标，已取消执行。")
        raise SystemExit(1)
    try:
        result = asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        print("已取消。")
        raise SystemExit(130) from None
    except Exception as exc:  # pylint: disable=broad-except
        print(f"执行失败：{exc}")
        raise SystemExit(1) from exc

    document = result.get("document")
    print("🎯 全流程执行完成。")
    if document:
        print(f"- 协作表单：{document}")
    if result.get("stage2_upgrade"):
        print("- 已生成策略库升级补丁，请检查 stage2 能力升级代理输出。")
    if result.get("capability_upgrade"):
        print("- 已完成能力库升级评估，可根据需要写入补丁。")


if __name__ == "__main__":
    main()


