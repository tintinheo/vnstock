from tradingos.data.provider_registry import admitted_providers, load_provider_registry


def test_registry_has_governance_fields_and_no_implicit_admission():
    registry = load_provider_registry()
    assert registry["registry_version"] == "1.0.0"
    assert {provider["id"] for provider in registry["providers"]} >= {"ssi_iboard", "dnse"}
    assert all(provider["evidence_ref"] for provider in registry["providers"])
    assert admitted_providers(registry) == []
