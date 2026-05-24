"""Convert Universalis API HTML doc snippets to clean Markdown."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import MarkdownConverter


class DocConverter(MarkdownConverter):
    """Skip empty links and collapse Mantine wrapper divs."""

    def convert_a(self, el, text, parent_tags):
        href = el.get("href") or ""
        if not text.strip():
            return ""
        if href.startswith("#"):
            return text
        return super().convert_a(el, text, parent_tags)


def extract_prism_code(pre: Tag) -> str:
    """Reassemble code from Prism's per-token span soup.

    Each `.token-line` is one source line; line-number divs are dropped.
    """
    lang = ""
    for cls in pre.get("class", []):
        if cls.startswith("language-"):
            lang = cls.removeprefix("language-")
            break

    lines: list[str] = []
    line_divs = pre.select("div.token-line")
    if line_divs:
        for line in line_divs:
            for ln in line.select("div.mantine-Prism-lineNumber"):
                ln.decompose()
            lines.append(line.get_text(""))
    else:
        lines = pre.get_text("\n").splitlines()

    body = "\n".join(lines).rstrip()
    return f"\n```{lang}\n{body}\n```\n"


SENTINEL = "CODEBLOCK{}"


def preprocess(soup: BeautifulSoup, code_blocks: list[str]) -> None:
    for tag in soup(["script", "style", "svg", "button"]):
        tag.decompose()

    # Stash Prism code blocks as sentinels so markdownify won't escape them.
    for pre in list(soup.select("pre.prism-code, pre[class*='language-']")):
        idx = len(code_blocks)
        code_blocks.append(extract_prism_code(pre))
        pre.replace_with(soup.new_string(SENTINEL.format(idx)))

    # Drop noisy class attrs so markdownify output stays clean.
    for tag in soup.find_all(True):
        for attr in ("class", "style", "id", "dir", "aria-hidden",
                     "aria-invalid", "aria-label", "aria-selected",
                     "aria-orientation", "role", "tabindex", "type",
                     "data-radix-scroll-area-viewport"):
            tag.attrs.pop(attr, None)


def html_to_md(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    code_blocks: list[str] = []
    preprocess(soup, code_blocks)
    md = DocConverter(heading_style="ATX", bullets="-", code_language="").convert_soup(soup)
    for idx, block in enumerate(code_blocks):
        md = md.replace(SENTINEL.format(idx), block)
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r"[ \t]+\n", "\n", md)
    return md.strip() + "\n"


def main(args: list[str]) -> int:
    if not args:
        print("usage: html_to_md.py <file.html> [<file.html> ...]", file=sys.stderr)
        return 2
    for arg in args:
        src = Path(arg)
        if not src.is_file():
            print(f"skip: {src} (not a file)", file=sys.stderr)
            continue
        dst = src.with_suffix(".md")
        dst.write_text(html_to_md(src.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"{src} -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
