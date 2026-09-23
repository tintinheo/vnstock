from scripts.check_traceability import validate_traceability


def test_traceability_ledger_is_complete_and_resolves():
    assert validate_traceability() == []
