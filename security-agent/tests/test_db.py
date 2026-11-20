from app.db import Database


def test_knowledge_search(tmp_path) -> None:
    db = Database(tmp_path / "test.db")
    db.index_document("soc.md", "SOC", "Kerberos authentication anomaly playbook")
    results = db.search("Investigate Kerberos anomaly")
    assert results[0]["source"] == "soc.md"


def test_case_conversation_and_approval_lifecycle(tmp_path) -> None:
    db = Database(tmp_path / "test.db")
    case = db.create_case("case-1", "soc", "Kerberos triage")
    assert case["status"] == "open"

    db.add_message("case-1", "user", "Investigate host", evidence=["alert-1"])
    db.add_message(
        "case-1",
        "assistant",
        "Acknowledge",
        tool_results=[{"name": "mcp_query", "status": "success"}],
    )
    history = db.recent_conversation("case-1", limit=8, max_chars=100)
    assert [item["role"] for item in history] == ["user", "assistant"]
    assert db.list_cases()[0]["message_count"] == 2

    approval = db.create_approval(
        "approval-1",
        "case-1",
        "caldera.launch_operation",
        {"capability": "caldera.launch_operation"},
        "Authorized emulation requires approval",
    )
    assert approval["status"] == "pending"
    assert db.get_case("case-1")["status"] == "pending_approval"
    assert db.claim_approval("approval-1")["status"] == "executing"
    assert db.claim_approval("approval-1") is None
    db.set_approval_status("approval-1", "approved")
    assert db.get_case("case-1")["status"] == "open"


def test_replace_document_chunks_removes_stale_chunks(tmp_path) -> None:
    db = Database(tmp_path / "test.db")
    db.replace_document_chunks(
        "rag-sources/runbook.pdf",
        [
            {
                "source": "rag-sources/runbook.pdf#page=1#chunk=1",
                "title": "Runbook",
                "content": "Ransomware containment workflow",
            },
            {
                "source": "rag-sources/runbook.pdf#page=2#chunk=1",
                "title": "Runbook",
                "content": "Preserve forensic evidence",
            },
        ],
    )
    db.replace_document_chunks(
        "rag-sources/runbook.pdf",
        [
            {
                "source": "rag-sources/runbook.pdf#page=1#chunk=1",
                "title": "Runbook",
                "content": "Updated ransomware containment workflow",
            }
        ],
    )
    assert len(db.search("ransomware")) == 1
    assert not db.search("forensic")


def test_rebuild_knowledge_removes_deleted_documents(tmp_path) -> None:
    db = Database(tmp_path / "test.db")
    db.index_document("old.md", "Old", "obsolete knowledge")
    documents = [
        [
            {
                "source": "new.md#chunk=1",
                "title": "New",
                "content": "current knowledge",
            }
        ]
    ]
    assert db.rebuild_knowledge(documents) == (1, 1)
    assert not db.search("obsolete")
    assert db.search("current")[0]["source"] == "new.md#chunk=1"
