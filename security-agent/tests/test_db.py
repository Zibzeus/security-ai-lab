from app.db import Database


def test_knowledge_search(tmp_path) -> None:
    db = Database(tmp_path / "test.db")
    db.index_document("soc.md", "SOC", "Kerberos authentication anomaly playbook")
    results = db.search("Investigate Kerberos anomaly")
    assert results[0]["source"] == "soc.md"
