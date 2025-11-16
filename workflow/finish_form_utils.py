"""Utility helpers for writing agent outputs into ``finish_form`` documents."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

DEFAULT_PLACEHOLDER = "`待填写`"


def update_form_section(
    path: str | Path,
    *,
    marker_name: str,
    content: str,
    header: str | None = None,
    encoding: str = "utf-8",
    placeholder: str = DEFAULT_PLACEHOLDER,
) -> None:
    """Write ``content`` into the markdown section identified by ``marker_name``.

    Preference order:
    1. Replace an existing ``<!-- {marker_name}_START --> ... <!-- {marker_name}_END -->`` block.
    2. If the block is missing but ``header`` is provided, insert the block after that header.
    3. Otherwise append the block to the end of the document.
    """

    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"finish_form document not found: {target}")

    text = target.read_text(encoding=encoding)
    normalized = text.replace("\r\n", "\n")

    sanitized = _sanitize_content(content, placeholder=placeholder)
    start_marker = f"<!-- {marker_name}_START -->"
    end_marker = f"<!-- {marker_name}_END -->"
    replacement_block = f"{start_marker}\n{sanitized}\n{end_marker}"

    pattern = re.compile(
        rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}",
        re.DOTALL,
    )
    new_text, count = pattern.subn(lambda _: replacement_block, normalized, count=1)

    if count == 0:
        insertion = replacement_block
        if header:
            header_pattern = re.compile(re.escape(header))
            match = header_pattern.search(normalized)
            if match:
                insert_pos = normalized.find("\n", match.end())
                if insert_pos == -1:
                    insert_pos = match.end()
                else:
                    insert_pos += 1
                new_text = (
                    normalized[:insert_pos].rstrip("\n")
                    + "\n\n"
                    + insertion
                    + "\n"
                    + normalized[insert_pos:].lstrip("\n")
                )
            else:
                new_text = normalized.rstrip("\n") + "\n\n" + insertion + "\n"
        else:
            new_text = normalized.rstrip("\n") + "\n\n" + insertion + "\n"

    target.write_text(new_text.replace("\n", "\n"), encoding=encoding)


def _sanitize_content(content: str, *, placeholder: str) -> str:
    stripped = (content or "").strip()
    return stripped if stripped else placeholder


def ensure_markers(
    path: str | Path,
    *,
    marker_pairs: Iterable[tuple[str, str]],
    encoding: str = "utf-8",
) -> None:
    """Ensure each marker pair exists in the document, appending placeholders if needed."""

    target = Path(path).expanduser().resolve()
    if not target.exists():
        return

    text = target.read_text(encoding=encoding).replace("\r\n", "\n")
    updated = False

    for marker_name, placeholder in marker_pairs:
        start_marker = f"<!-- {marker_name}_START -->"
        end_marker = f"<!-- {marker_name}_END -->"
        if start_marker in text and end_marker in text:
            continue
        block = (
            f"{start_marker}\n{placeholder or DEFAULT_PLACEHOLDER}\n{end_marker}"
        )
        text = text.rstrip("\n") + "\n\n" + block + "\n"
        updated = True

    if updated:
        target.write_text(text, encoding=encoding)

