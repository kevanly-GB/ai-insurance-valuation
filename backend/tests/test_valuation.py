from types import SimpleNamespace
from app.agents.valuation import evaluate, read_amount

def test_explicit_label_only():
    assert read_amount("Replacement cost: AUD 1,200.50", ("replacement cost",)) == 1200.50
    assert read_amount("Invoice: AUD 2,000", ("replacement cost",)) is None

def test_five_agents_evidence_traceability():
    docs = [SimpleNamespace(id="d1", classification="assets", text="Replacement cost: $5,000\nOther: $9,000"),
            SimpleNamespace(id="d2", classification="property", text="Repair estimate: AUD 1,250")]
    result = evaluate(docs)
    assert len(result["agents"]) == 5
    assert result["total_aud"] == 6250
    assert result["agents"][0]["evidence"][0]["document_id"] == "d1"
    assert result["human_approval_required"] is True

def test_no_evidence_never_invents_amount():
    result = evaluate([])
    assert result["total_aud"] == 0
    assert result["anomalies"]
