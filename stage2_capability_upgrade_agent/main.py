"""Command-line interface for running the Stage2CapabilityUpgradeAgent interactively."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    from .stage2_capability_upgrade_agent import (
        Stage2CapabilityUpgradeAgent,
        Stage2CapabilityUpgradeConfig,
    )
except ImportError:  # pragma: no cover
    import os as _os
    import sys as _sys

    CURRENT_DIR = _os.path.dirname(_os.path.abspath(__file__))
    if CURRENT_DIR not in _sys.path:
        _sys.path.insert(0, CURRENT_DIR)

    from stage2_capability_upgrade_agent import (  # type: ignore  # pylint: disable=import-error
        Stage2CapabilityUpgradeAgent,
        Stage2CapabilityUpgradeConfig,
    )

EXIT_COMMANDS = {"exit", "quit", "q"}
REFRESH_COMMANDS = {"refresh", "reload"}
APPLY_COMMANDS = {"apply", "write"}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="stage2-capability-upgrade-agent",
        description="Interactively run the Stage2CapabilityUpgradeAgent to maintain strategy definitions.",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        help="DeepSeek API key (falls back to DEEPSEEK_API_KEY environment variable).",
    )
    parser.add_argument(
        "--model",
        default="deepseek-chat",
        help="DeepSeek model name (default: deepseek-chat).",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable streaming responses (default: disabled).",
    )
    parser.add_argument(
        "--base-url",
        default="https://api.deepseek.com",
        help="DeepSeek API base URL (default: https://api.deepseek.com).",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        default="medium",
        help="Reasoning effort level for the DeepSeek model (default: medium).",
    )
    parser.add_argument(
        "--system-prompt",
        dest="system_prompt",
        help="Optional custom system prompt. If omitted, the default template from thinking.md is used.",
    )
    parser.add_argument(
        "--max-library-chars",
        type=int,
        dest="max_library_chars",
        help="Maximum number of characters to load from the strategy library snapshot (default: 120000).",
    )
    parser.add_argument(
        "--no-auto-apply",
        dest="auto_apply_patch",
        action="store_false",
        help="Disable automatically writing generated strategy definitions to the strategy library (default: enabled).",
    )
    parser.set_defaults(auto_apply_patch=True)
    parser.add_argument(
        "--no-backup",
        dest="no_backup",
        action="store_true",
        help="Disable automatic backup before writing to the strategy library file.",
    )
    parser.add_argument(
        "--library-file",
        dest="library_file",
        help="Path to the strategy library markdown file to update (default: strategy_library/strategy.md).",
    )
    return parser.parse_args()


def _ensure_api_key(cli_api_key: str | None) -> str:
    api_key = cli_api_key or os.getenv("DEEPSEEK_API_KEY")
    if api_key:
        return api_key

    while not api_key:
        api_key = input("请输入 DeepSeek API Key (输入后按回车): ").strip()
    return api_key


def _print_banner() -> None:
    print("=" * 72)
    print("Stage 2 Strategy Upgrade Agent")
    print("输入 'exit' / 'quit' / 'q' 退出程序，输入 'refresh' 重新加载策略库快照")
    print("提示: 多条输入可使用 '|' 分隔；留空可跳过可选字段")
    print("=" * 72)


def _parse_delimited(raw: str) -> list[str] | None:
    if not raw.strip():
        return None
    entries: list[str] = []
    for token in raw.split("|"):
        cleaned = token.strip()
        if cleaned:
            entries.append(cleaned)
    return entries or None


async def _interactive_loop(agent: Stage2CapabilityUpgradeAgent) -> None:
    _print_banner()

    while True:
        try:
            stage2_report = input("Stage 2 输出 (必填)> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            break

        if not stage2_report:
            print("Stage 2 输出不能为空，请重新输入。")
            continue

        lowered = stage2_report.lower()
        if lowered in EXIT_COMMANDS:
            print("已退出。")
            break
        if lowered in REFRESH_COMMANDS:
            agent.refresh_system_prompt(force=True)
            print("已重新加载系统提示与策略库快照。\n")
            continue
        if lowered in APPLY_COMMANDS:
            patch = agent.last_patch_markdown
            if not patch:
                print("当前没有可写入的策略补丁，请先生成。\n")
                continue
            applied_path = agent.apply_patch(patch)
            if applied_path:
                print(f"已将策略补丁写入 {applied_path}\n")
            else:
                print("策略补丁为空，未执行写入。\n")
            continue

        suspected_raw = input("疑似新增策略 (可选，使用 '|' 分隔)> ").strip()
        pending_raw = input("待处理策略补丁 (可选，使用 '|' 分隔)> ").strip()
        maintainer_notes = input("维护者备注 (可选)> ").strip() or None
        additional_context = input("额外上下文 (可选)> ").strip() or None
        custom_snapshot = input("临时策略库快照覆盖 (可选)> ").strip() or None

        suspected = _parse_delimited(suspected_raw)
        pending = _parse_delimited(pending_raw)
        snapshot_override = custom_snapshot or None

        print("\n生成策略补丁中，请稍候...\n")
        try:
            result_text = await agent.evaluate_text(
                metacognitive_report=stage2_report,
                suspected_new_capabilities=suspected,
                pending_updates=pending,
                maintainer_notes=maintainer_notes,
                additional_context=additional_context,
                library_snapshot=snapshot_override,
            )
        except Exception as exc:  # pylint: disable=broad-except
            print(f"发生错误: {exc}\n")
            continue

        print("-" * 72)
        print(result_text or "<无内容>")
        print("-" * 72 + "\n")

        if agent.last_applied_path:
            print(f"✅ 已自动写入策略库：{agent.last_applied_path}\n")
        elif agent.last_patch_markdown:
            print("提示：输入 'apply' 可写入当前策略补丁；输入 'refresh' 可重载策略库快照。\n")


async def _main_async(args: argparse.Namespace) -> None:
    config = Stage2CapabilityUpgradeConfig(
        api_key=_ensure_api_key(args.api_key),
        model_name=args.model,
        stream=args.stream,
        base_url=args.base_url,
        reasoning_effort=args.reasoning_effort,
        system_prompt=args.system_prompt,
        max_library_chars=args.max_library_chars,
        auto_apply_patch=args.auto_apply_patch,
        backup_before_write=not args.no_backup,
        library_file=args.library_file,
    )

    agent = Stage2CapabilityUpgradeAgent(config=config)
    await _interactive_loop(agent)


def main() -> None:
    args = _parse_args()
    try:
        asyncio.run(_main_async(args))
    except KeyboardInterrupt:  # pragma: no cover
        print("\n已退出。")


if __name__ == "__main__":
    main()

