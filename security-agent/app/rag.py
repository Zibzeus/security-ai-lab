import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from pypdf import PdfReader


SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf"}
WHITESPACE = re.compile(r"[ \t]+")
BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class RagChunk:
    source: str
    title: str
    content: str


@dataclass(frozen=True)
class RagDocument:
    path: Path
    source_root: str
    title: str
    chunks: list[RagChunk]


def normalize_text(value: str) -> str:
    lines = [WHITESPACE.sub(" ", line).strip() for line in value.splitlines()]
    return BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def chunk_text(
    text: str,
    *,
    chunk_chars: int,
    overlap_chars: int,
) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    if chunk_chars < 256:
        raise ValueError("RAG chunk size must be at least 256 characters")
    if overlap_chars < 0 or overlap_chars >= chunk_chars:
        raise ValueError("RAG overlap must be non-negative and smaller than chunk size")

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_chars, len(normalized))
        if end < len(normalized):
            boundary = max(
                normalized.rfind("\n\n", start, end),
                normalized.rfind(". ", start, end),
                normalized.rfind(" ", start, end),
            )
            if boundary > start + chunk_chars // 2:
                end = boundary + 1
        content = normalized[start:end].strip()
        if content:
            chunks.append(content)
        if end >= len(normalized):
            break
        start = max(end - overlap_chars, start + 1)
    return chunks


def _text_document(
    path: Path,
    source_root: str,
    *,
    chunk_chars: int,
    overlap_chars: int,
) -> RagDocument:
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks = [
        RagChunk(
            source=f"{source_root}#chunk={index}",
            title=path.stem.replace("-", " ").replace("_", " ").title(),
            content=content,
        )
        for index, content in enumerate(
            chunk_text(
                text,
                chunk_chars=chunk_chars,
                overlap_chars=overlap_chars,
            ),
            start=1,
        )
    ]
    return RagDocument(path, source_root, path.stem, chunks)


def _pdf_document(
    path: Path,
    source_root: str,
    *,
    chunk_chars: int,
    overlap_chars: int,
) -> RagDocument:
    reader = PdfReader(path)
    chunks: list[RagChunk] = []
    title = str((reader.metadata or {}).get("/Title") or path.stem).strip()
    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        for chunk_number, content in enumerate(
            chunk_text(
                page_text,
                chunk_chars=chunk_chars,
                overlap_chars=overlap_chars,
            ),
            start=1,
        ):
            chunks.append(
                RagChunk(
                    source=(
                        f"{source_root}#page={page_number}"
                        f"#chunk={chunk_number}"
                    ),
                    title=title,
                    content=content,
                )
            )
    return RagDocument(path, source_root, title, chunks)


def load_document(
    path: Path,
    source_root: str,
    *,
    chunk_chars: int,
    overlap_chars: int,
) -> RagDocument:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_document(
            path,
            source_root,
            chunk_chars=chunk_chars,
            overlap_chars=overlap_chars,
        )
    if suffix in {".md", ".txt"}:
        return _text_document(
            path,
            source_root,
            chunk_chars=chunk_chars,
            overlap_chars=overlap_chars,
        )
    raise ValueError(f"Unsupported RAG document type: {suffix}")


def discover_documents(
    source_dirs: list[Path],
    *,
    max_documents: int,
    max_file_bytes: int,
    chunk_chars: int,
    overlap_chars: int,
) -> Iterator[RagDocument]:
    seen = 0
    for source_dir in source_dirs:
        if not source_dir.is_dir():
            continue
        resolved_root = source_dir.resolve()
        for path in sorted(source_dir.rglob("*")):
            if seen >= max_documents:
                return
            if (
                not path.is_file()
                or path.name.startswith(".")
                or path.suffix.lower() not in SUPPORTED_SUFFIXES
                or path.stat().st_size > max_file_bytes
            ):
                continue
            resolved_path = path.resolve()
            if resolved_root not in resolved_path.parents:
                continue
            relative = resolved_path.relative_to(resolved_root).as_posix()
            source_root = f"{source_dir.name}/{relative}"
            yield load_document(
                resolved_path,
                source_root,
                chunk_chars=chunk_chars,
                overlap_chars=overlap_chars,
            )
            seen += 1
