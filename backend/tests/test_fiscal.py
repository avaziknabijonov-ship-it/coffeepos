import pytest

from app.fiscal import (
    FiscalNotConfigured, FiscalResult, FiscalTenantConfig, issue_fiscal_receipt,
)


def tenant(enabled=True):
    return FiscalTenantConfig(1, "123456789", "sandbox", "terminal-1", enabled)


def test_invalid_tin_rejected():
    with pytest.raises(ValueError):
        FiscalTenantConfig(1, "123", "sandbox", "terminal-1", True).validate()


def test_missing_provider_fails_closed():
    with pytest.raises(FiscalNotConfigured):
        issue_fiscal_receipt(tenant=tenant(), order_id=10,
                             idempotency_key="sale-10", provider=None)


def test_disabled_fiscal_mode_does_not_issue():
    with pytest.raises(FiscalNotConfigured):
        issue_fiscal_receipt(tenant=tenant(False), order_id=10,
                             idempotency_key="sale-10", provider=object())


def test_provider_response_must_have_fiscal_fields():
    class Broken:
        def issue_receipt(self, **kwargs):
            return FiscalResult("receipt", "", "qr")
    with pytest.raises(RuntimeError):
        issue_fiscal_receipt(tenant=tenant(), order_id=10,
                             idempotency_key="sale-10", provider=Broken())


def test_provider_adapter_receives_tenant_and_idempotency_key():
    class Fake:
        def issue_receipt(self, **kwargs):
            assert kwargs["tenant"].company_id == 1
            assert kwargs["idempotency_key"] == "sale-10"
            return FiscalResult("receipt", "sign", "qr")
    result = issue_fiscal_receipt(tenant=tenant(), order_id=10,
                                  idempotency_key="sale-10", provider=Fake())
    assert result.fiscal_sign == "sign"
