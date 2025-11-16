# -*- coding: utf-8 -*-
"""Stage3ExecutionAgent 命令行入口脚本。"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
from getpass import getpass
from pathlib import Path
from typing import Any, Mapping, Sequence

from dotenv import load_dotenv

from tool_catalog import load_tool_catalog, merge_tool_catalogs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from .Step_agent import Stage3ExecutionAgent, Stage3ExecutionAgentConfig
except ImportError:  # pragma: no cover
    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from Step_agent import Stage3ExecutionAgent, Stage3ExecutionAgentConfig  # type: ignore # pylint: disable=import-error

from model._model_response import ChatResponse

load_dotenv(PROJECT_ROOT / ".env")

EXIT_COMMANDS = {"exit", "quit", "q"}
MULTILINE_SENTINEL = "END"

DEFAULT_TOOL_CATALOG = load_tool_catalog()


class UserExit(RuntimeError):
    """用户主动退出交互循环。"""


def _log_exception(exc: Exception) -> None:
    print(f"发生错误: {exc}\n")
    cause = exc.__cause__
    if cause is not None:
        print(f"根因: {cause}\n")
    print("详细堆栈如下：")
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    print("")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="stage3-execution-agent",
        description="交互式运行 Stage3ExecutionAgent（DeepSeek 驱动）。",
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
        help="自定义 system prompt，若不提供将使用 step.md 的默认提示词。",
    )
    parser.add_argument(
        "--candidate-limit",
        dest="candidate_limit",
        type=int,
        help="设置候选策略数量上限（仅在 pipeline 模式下生效，默认由配置决定，通常为 3）。",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="仅执行一次规划后退出（默认进入持续交互模式）。",
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
    print("Stage 3 Execution Plan Agent (DeepSeek)")
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


def _parse_json_value(raw: str, *, expect_mapping: bool | None = None) -> Any:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败: {exc}") from exc

    if expect_mapping is True and not isinstance(value, Mapping):
        raise ValueError("需要一个 JSON 对象。")
    if expect_mapping is False and not isinstance(value, Sequence):
        raise ValueError("需要一个 JSON 数组。")
    return value


def _prompt_json_mapping(prompt: str, *, required: bool) -> Mapping[str, Any]:
    while True:
        raw = _prompt_multiline(prompt, required=required)
        if raw is None:
            if required:
                continue
            return {}
        try:
            value = _parse_json_value(raw, expect_mapping=True)
        except ValueError as exc:
            print(exc)
            continue
        return value  # type: ignore[return-value]


def _prompt_optional_json(prompt: str) -> Any | None:
    raw = _prompt_multiline(prompt, required=False)
    if raw is None:
        return None
    try:
        return _parse_json_value(raw, expect_mapping=None)
    except ValueError as exc:
        print(exc)
        return _prompt_optional_json(prompt)


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
                value = _parse_json_value(stripped, expect_mapping=False)
            except ValueError as exc:
                print(exc)
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


def _collect_execution_constraints() -> list[str] | None:
    raw = _prompt_line("执行约束 (可选，使用 '|' 分隔)> ")
    if not raw:
        return None
    constraints = [item.strip() for item in raw.split("|") if item.strip()]
    return constraints or None


def _collect_tool_catalog() -> list[str] | None:
    raw = _prompt_line("可用工具清单 (可选，逗号分隔)> ")
    if not raw:
        return None
    tools = [entry.strip() for entry in raw.split(",") if entry.strip()]
    return tools or None


async def _interactive_loop_stage_three(agent: Stage3ExecutionAgent, *, single_run: bool) -> None:
    _print_banner()

    while True:
        try:
            objective = _prompt_line("目标 Objective (可选)> ")
            meta_analysis = _prompt_multiline("Stage 1 META_ANALYSIS (必填) >", required=True)
            refined_strategy = _prompt_json_mapping("Stage 2 refined_strategy JSON (必填) >", required=True)
            handover_notes = _prompt_optional_json("Stage 2 handover_notes JSON (可选) >")
            success_criteria = _collect_sequence(
                "Success Criteria (可选，JSON 数组或使用 '|' 分隔)> ",
                required=False,
            )
            failure_indicators = _collect_sequence(
                "Failure Indicators (可选，JSON 数组或使用 '|' 分隔)> ",
                required=False,
            )
            content_quality = _prompt_optional_json("Stage 1 content_quality JSON (可选) >")
            timeliness = _prompt_optional_json("Stage 1 timeliness_and_knowledge_boundary JSON (可选) >")
            required_capabilities = _prompt_optional_json("Stage 1 required_capabilities JSON 数组 (可选) >")
            if required_capabilities is not None and not isinstance(required_capabilities, Sequence):
                print("required_capabilities 必须是 JSON 数组，将忽略该输入。")
                required_capabilities = None

            execution_constraints = _collect_execution_constraints()
            context_snapshot = _prompt_multiline("补充上下文 (可选) >", required=False)
            user_tool_catalog = _collect_tool_catalog()
            tool_catalog = merge_tool_catalogs(DEFAULT_TOOL_CATALOG, user_tool_catalog)
        except UserExit:
            print("已退出。")
            break

        strategy_id = None
        if isinstance(refined_strategy, Mapping):
            candidate_strategy_id = refined_strategy.get("strategy_id")
            if isinstance(candidate_strategy_id, str):
                strategy_id = candidate_strategy_id

        print("\n生成执行计划中，请稍候...\n")
        try:
            result_text = await agent.analyze_text(
                meta_analysis=meta_analysis or "",
                refined_strategy=refined_strategy,
                handover_notes=handover_notes,
                objective=objective,
                success_criteria=success_criteria,
                failure_indicators=failure_indicators,
                content_quality=content_quality if isinstance(content_quality, Mapping) else None,
                required_capabilities=required_capabilities if isinstance(required_capabilities, Sequence) else None,
                timeliness_and_knowledge_boundary=timeliness if isinstance(timeliness, Mapping) else None,
                execution_constraints=execution_constraints,
                context_snapshot=context_snapshot,
                tool_catalog=tool_catalog,
                strategy_id=strategy_id,
            )
        except Exception as exc:  # pylint: disable=broad-except
            print(f"发生错误: {exc}\n")
            debug_snapshot = getattr(agent, "_debug_last_snapshot", None)  # pylint: disable=protected-access
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
    api_key = _ensure_api_key(args.api_key)

    config_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "model_name": args.model,
        "stream": args.stream,
        "base_url": args.base_url,
        "reasoning_effort": args.reasoning_effort,
        "system_prompt": args.system_prompt,
    }
    stage3_agent = Stage3ExecutionAgent(Stage3ExecutionAgentConfig(**config_kwargs))

    await _interactive_loop_stage_three(stage3_agent, single_run=args.once)


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


