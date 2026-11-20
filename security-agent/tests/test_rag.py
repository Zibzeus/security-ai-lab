from app.rag import chunk_text, discover_documents, normalize_text


def test_normalize_and_chunk_text_preserves_overlap() -> None:
    text = "Alpha   beta.\n\n" + ("Gamma delta epsilon. " * 80)
    chunks = chunk_text(text, chunk_chars=300, overlap_chars=40)
    assert len(chunks) > 1
    assert chunks[0].startswith("Alpha beta.")
    assert all(len(chunk) <= 301 for chunk in chunks)


def test_discover_markdown_document(tmp_path) -> None:
    source = tmp_path / "rag-sources"
    source.mkdir()
    (source / "runbook.md").write_text(
        "# Ransomware\n\nContain the affected host and preserve evidence.",
        encoding="utf-8",
    )
    (source / "ignore.bin").write_bytes(b"ignored")

    documents = list(
        discover_documents(
            [source],
            max_documents=10,
            max_file_bytes=1024 * 1024,
            chunk_chars=512,
            overlap_chars=50,
        )
    )

    assert len(documents) == 1
    assert documents[0].source_root == "rag-sources/runbook.md"
    assert documents[0].chunks[0].source.endswith("#chunk=1")
    assert "Contain the affected host" in documents[0].chunks[0].content


def test_normalize_text_removes_excess_spacing() -> None:
    assert normalize_text("A    B\n\n\n\nC") == "A B\n\nC"
