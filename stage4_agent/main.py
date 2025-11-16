# -*- coding: utf-8 -*-
"""Stage4ExecutorAgent 命令行入口脚本。"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from getpass import getpass
from pathlib import Path
from typing import Any, Mapping, Sequence
import sys

from dotenv import load_dotenv

from tool_catalog import load_tool_catalog, merge_tool_catalogs

try:
    from .Executor_agent import Stage4ExecutorAgent, Stage4ExecutorAgentConfig
except ImportError:  # pragma: no cover
    import sys

    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))

    from Executor_agent import Stage4ExecutorAgent, Stage4ExecutorAgentConfig  # type: ignore  # pylint: disable=import-error


EXIT_COMMANDS = {"exit", "quit", "q"}
MULTILINE_SENTINEL = "END"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_TOOL_CATALOG = load_tool_catalog()

class UserExit(RuntimeError):
    """用户主动退出交互循环。"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="stage4-executor-agent",
        description="交互式运行 Stage4ExecutorAgent（DeepSeek 驱动）。",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        help="DeepSeek API Key，若不提供则尝试从环境变量 DEEPSEEK_API_KEY 读取。",
    )
    parser.add_argument(
        "--model",
        default="deepseek-chat",
        help="DeepSeek 模型名称（默认：deepseek-chat）。",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="启用流式输出（默认关闭）。",
    )
    parser.add_argument(
        "--base-url",
        default="https://api.deepseek.com",
        help="DeepSeek API 基础地址（默认：https://api.deepseek.com）。",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        default="medium",
        help="推理强度设置（默认：medium）。",
    )
    parser.add_argument(
        "--system-prompt",
        dest="system_prompt",
        help="自定义 system prompt，若不提供将使用 executor.md 的默认提示词。",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="仅执行一次记录后退出（默认进入持续交互模式）。",
    )
    return parser.parse_args()


def _ensure_api_key(cli_api_key: str | None) -> str:
    api_key = cli_api_key or os.getenv("DEEPSEEK_API_KEY")
    if api_key:
        return api_key

    while not api_key:
        api_key = getpass("请输入 DeepSeek API Key（回车确认）: ").strip()
    return api_key


def _print_banner() -> None:
    print("=" * 78)
    print("Stage 4 Execution Agent (DeepSeek)")
    print("输入 'exit' / 'quit' / 'q' 可在任意主提示下退出。")
    print(f"多行输入请以单独一行 '{MULTILINE_SENTINEL}' 结束。")
    print("=" * 78)
    if DEFAULT_TOOL_CATALOG:
        print("默认工具清单：")
        for tool in DEFAULT_TOOL_CATALOG:
            print(f"- {tool}")
        print("=" * 78)


def _prompt_line(prompt: str, *, required: bool = False) -> str | None:
    while True:
        try:
            value = input(prompt).strip()
        except (EOFError, KeyboardInterrupt) as exc:  # pragma: no cover
            raise UserExit from exc

        if value.lower() in EXIT_COMMANDS:
            raise UserExit

        if value:
            return value

        if not required:
            return None

        print("该字段不能为空，请重新输入。")


def _prompt_multiline(prompt: str, *, required: bool = False) -> str | None:
    while True:
        print(prompt)
        if required:
            print(f"(输入完成后请单独输入 '{MULTILINE_SENTINEL}' 结束，或在内容后输入空行结束)")
        else:
            print("(直接回车留空；如需继续多行输入，可单独输入 'END')")

        lines: list[str] = []
        while True:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt) as exc:  # pragma: no cover
                raise UserExit from exc

            trimmed = line.strip()
            if not lines and trimmed.lower() in EXIT_COMMANDS:
                raise UserExit

            if trimmed == MULTILINE_SENTINEL:
                break
            if not line:
                break
            lines.append(line)

        text = "\n".join(lines).strip()
        if text:
            return text

        if not required:
            return None

        print("该字段不能为空，请重新输入。")


def _prompt_json(prompt: str, *, required: bool, expect_mapping: bool | None = None) -> Any:
    while True:
        raw = _prompt_multiline(prompt, required=required)
        if raw is None:
            if required:
                continue
            return None
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"JSON 解析失败: {exc}")
            continue

        if expect_mapping is True and not isinstance(value, Mapping):
            print("请输入 JSON 对象。")
            continue
        if expect_mapping is False and not isinstance(value, Sequence):
            print("请输入 JSON 数组。")
            continue
        return value


def _collect_sequence(prompt: str, *, required: bool = False) -> list[str] | None:
    while True:
        raw = _prompt_multiline(prompt, required=required)
        if raw is None:
            return None

        stripped = raw.strip()
        if not stripped and not required:
            return None

        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                print(f"JSON 解析失败: {exc}")
                continue
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                items = [str(item).strip() for item in value if str(item).strip()]
                if items:
                    return items
                if required:
                    print("数组不能为空，请重新输入。")
                    continue
                return None
            print("请输入有效的 JSON 数组。")
            continue

        items = [item.strip() for item in stripped.split("|") if item.strip()]
        if items:
            return items
        if not required:
            return None
        print("至少需要提供一个条目，请重新输入。")


async def _interactive_loop(agent: Stage4ExecutorAgent, *, single_run: bool) -> None:
    _print_banner()

    while True:
        try:
            objective = _prompt_line("目标 Objective (可选)> ")
            context_snapshot = _prompt_multiline("补充上下文 (可选) >", required=False)
            execution_plan = _prompt_json("Stage 3 执行计划 JSON (必填) >", required=True, expect_mapping=True)
            meta_analysis = _prompt_multiline("Stage 1 META_ANALYSIS (可选) >", required=False)
            refined_strategy = _prompt_json("Stage 2 refined_strategy JSON (可选) >", required=False, expect_mapping=True)
            handover_notes = _prompt_json("Stage 2 handover_notes JSON/数组 (可选) >", required=False, expect_mapping=None)
            success_criteria = _collect_sequence(
                "Success Criteria (可选，JSON 数组或使用 '|' 分隔)> ",
                required=False,
            )
            failure_indicators = _collect_sequence(
                "Failure Indicators (可选，JSON 数组或使用 '|' 分隔)> ",
                required=False,
            )
            required_capabilities = _prompt_json(
                "Stage 1 required_capabilities JSON 数组 (可选) >",
                required=False,
                expect_mapping=False,
            )
            timeliness = _prompt_json(
                "Stage 1 timeliness_and_knowledge_boundary JSON (可选) >",
                required=False,
                expect_mapping=True,
            )
            external_constraints = _collect_sequence(
                "执行约束 (可选，JSON 数组或使用 '|' 分隔)> ",
                required=False,
            )
            user_tool_catalog = _collect_sequence(
                "工具清单 (可选，JSON 数组或使用 '|' 分隔)> ",
                required=False,
            )
            tool_catalog = merge_tool_catalogs(DEFAULT_TOOL_CATALOG, user_tool_catalog)
            prior_execution_state = _prompt_json(
                "既有执行状态 prior_execution_state JSON (可选) >",
                required=False,
                expect_mapping=True,
            )
            evidence_inputs = _prompt_json(
                "补充证据列表 evidence_inputs JSON 数组 (可选) >",
                required=False,
                expect_mapping=False,
            )
            attachments = _prompt_json(
                "附件索引 attachments JSON (可选) >",
                required=False,
                expect_mapping=True,
            )
        except UserExit:
            print("已退出。")
            break

        print("\n生成执行记录中，请稍候...\n")
        try:
            result_text = await agent.analyze_text(
                execution_plan=execution_plan,
                objective=objective,
                meta_analysis=meta_analysis,
                refined_strategy=refined_strategy if isinstance(refined_strategy, Mapping) else None,
                handover_notes=handover_notes,
                success_criteria=success_criteria,
                failure_indicators=failure_indicators,
                required_capabilities=required_capabilities if isinstance(required_capabilities, Sequence) else None,
                timeliness_and_knowledge_boundary=timeliness if isinstance(timeliness, Mapping) else None,
                external_constraints=external_constraints,
                tool_catalog=tool_catalog,
                context_snapshot=context_snapshot,
                prior_execution_state=prior_execution_state if isinstance(prior_execution_state, Mapping) else None,
                evidence_inputs=evidence_inputs if isinstance(evidence_inputs, Sequence) else None,
                attachments=attachments,
            )
        except Exception as exc:  # pylint: disable=broad-except
            print(f"发生错误: {exc}\n")
            debug_snapshot = getattr(agent, "_debug_last_snapshot", None)
            if debug_snapshot:
                print("模型最近一次输出快照:")
                try:
                    print(json.dumps(debug_snapshot, ensure_ascii=False, indent=2, default=str))
                except TypeError:
                    print(debug_snapshot)
            if single_run:
                break
            continue

        separator = "-" * 78
        print(separator)
        print(result_text or "<无内容>")
        print(separator + "\n")

        if single_run:
            break


async def _main_async(args: argparse.Namespace) -> None:
    config = Stage4ExecutorAgentConfig(
        api_key=_ensure_api_key(args.api_key),
        model_name=args.model,
        stream=args.stream,
        base_url=args.base_url,
        reasoning_effort=args.reasoning_effort,
        system_prompt=args.system_prompt,
    )
    agent = Stage4ExecutorAgent(config=config)
    await _interactive_loop(agent, single_run=args.once)


def main() -> None:
    args = _parse_args()
    try:
        asyncio.run(_main_async(args))
    except UserExit:
        print("已退出。")
    except KeyboardInterrupt:
        print("\n已退出。")


if __name__ == "__main__":
    main()



