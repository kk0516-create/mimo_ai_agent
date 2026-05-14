"""PDF 转 Markdown 解析器模块。"""

import re
from pathlib import Path
from typing import Optional

from pypdf import PdfReader


class PDFToMarkdownParser:
    """将 PDF 文件转换为 Markdown 格式，并支持语义切片。

    该解析器使用 pypdf 提取 PDF 文本内容，将其转换为 Markdown 格式，
    并按照章节/条款进行语义切片，以便后续 Agent 处理。
    """

    def __init__(self) -> None:
        """初始化 PDF 解析器。"""
        self._reader: Optional[PdfReader] = None
        self._pdf_path: Optional[Path] = None

    def extract_text(self, pdf_path: str | Path) -> str:
        """提取 PDF 文件的原始文本内容。

        Args:
            pdf_path: PDF 文件路径。

        Returns:
            提取的原始文本字符串。

        Raises:
            FileNotFoundError: 当 PDF 文件不存在时。
            ValueError: 当 PDF 文件无法读取时。
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        try:
            self._reader = PdfReader(str(pdf_path))
            self._pdf_path = pdf_path
            text_parts: list[str] = []
            for page in self._reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n".join(text_parts)
        except Exception as e:
            raise ValueError(f"PDF 文件读取失败: {e}") from e

    def to_markdown(self, pdf_path: str | Path) -> str:
        """将 PDF 文件转换为 Markdown 格式。

        转换规则：
        - 根据文本结构识别标题（第X章、第X条等），转换为 Markdown 标题语法
        - 保留段落结构
        - 添加页码标记

        Args:
            pdf_path: PDF 文件路径。

        Returns:
            转换后的 Markdown 文本。
        """
        raw_text = self.extract_text(pdf_path)
        lines = raw_text.split("\n")
        md_lines: list[str] = []
        current_page = 1

        for line in lines:
            stripped = line.strip()
            if not stripped:
                md_lines.append("")
                continue

            chapter_match = re.match(r"^(第[一二三四五六七八九十百千\d]+章)\s*(.*)", stripped)
            article_match = re.match(r"^(第[一二三四五六七八九十百千\d]+条)\s*(.*)", stripped)

            if chapter_match:
                md_lines.append(f"## {chapter_match.group(1)} {chapter_match.group(2)}")
            elif article_match:
                md_lines.append(f"### {article_match.group(1)} {article_match.group(2)}")
            else:
                md_lines.append(stripped)

        return "\n".join(md_lines)

    def semantic_chunking(
        self,
        markdown_text: str,
        chunk_size: int = 5000,
    ) -> list[dict]:
        """对 Markdown 文本进行语义切片。

        按照章节/条款边界进行切片，尽量保持语义完整性。
        每个切片不超过 chunk_size 字符。

        Args:
            markdown_text: 待切片的 Markdown 文本。
            chunk_size: 每个切片的最大字符数，默认 5000。

        Returns:
            切片列表，每个元素为包含 chunk_id, title, content, page_number 的字典。
        """
        chunks: list[dict] = []
        section_pattern = re.compile(r"^(#{1,3}\s+.+)$", re.MULTILINE)
        sections = list(section_pattern.finditer(markdown_text))

        if not sections:
            for i in range(0, len(markdown_text), chunk_size):
                content = markdown_text[i : i + chunk_size].strip()
                if content:
                    chunks.append({
                        "chunk_id": len(chunks),
                        "title": f"段落_{len(chunks) + 1}",
                        "content": content,
                        "page_number": len(chunks) + 1,
                    })
            return chunks

        for idx, match in enumerate(sections):
            start = match.start()
            end = sections[idx + 1].start() if idx + 1 < len(sections) else len(markdown_text)
            title = match.group(1).strip()
            content = markdown_text[start:end].strip()

            if len(content) > chunk_size:
                sub_chunks = self._split_large_chunk(content, chunk_size, title)
                chunks.extend(sub_chunks)
            else:
                chunks.append({
                    "chunk_id": len(chunks),
                    "title": title,
                    "content": content,
                    "page_number": idx + 1,
                })

        return chunks

    def _split_large_chunk(
        self,
        content: str,
        chunk_size: int,
        base_title: str,
    ) -> list[dict]:
        """将过大的切片拆分为更小的子切片。

        Args:
            content: 待拆分的内容。
            chunk_size: 每个子切片的最大字符数。
            base_title: 基础标题。

        Returns:
            子切片列表。
        """
        sub_chunks: list[dict] = []
        paragraphs = re.split(r"\n{2,}", content)
        current_content = ""
        sub_idx = 0

        for para in paragraphs:
            if len(current_content) + len(para) + 2 > chunk_size and current_content:
                sub_chunks.append({
                    "chunk_id": len(sub_chunks),
                    "title": f"{base_title} (续{sub_idx + 1})",
                    "content": current_content.strip(),
                    "page_number": sub_idx + 1,
                })
                sub_idx += 1
                current_content = para
            else:
                current_content += "\n\n" + para if current_content else para

        if current_content.strip():
            sub_chunks.append({
                "chunk_id": len(sub_chunks),
                "title": f"{base_title} (续{sub_idx + 1})",
                "content": current_content.strip(),
                "page_number": sub_idx + 1,
            })

        return sub_chunks
