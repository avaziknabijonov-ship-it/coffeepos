"""Provider-neutral fiscal integration contract.

No real fiscalization happens until a certified provider adapter is configured.
Never treat a non-fiscal receipt as a fiscal receipt.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FiscalTenantConfig:
    company_id: int
    tin: str
    provider: str
    terminal_id: str
    enabled: bool = False

    def validate(self) -> None:
        if self.company_id <= 0:
            raise ValueError("Invalid company ID")
        if not (self.tin.isdigit() and len(self.tin) == 9):
            raise ValueError("STIR must contain 9 digits")
        if not self.provider or not self.terminal_id:
            raise ValueError("Provider and terminal are required")


@dataclass(frozen=True)
class FiscalResult:
    provider_receipt_id: str
    fiscal_sign: str
    qr_payload: str


class FiscalProvider(Protocol):
    def issue_receipt(self, *, tenant: FiscalTenantConfig, order_id: int,
                      idempotency_key: str) -> FiscalResult: ...


class FiscalNotConfigured(RuntimeError):
    pass


def issue_fiscal_receipt(*, tenant: FiscalTenantConfig, order_id: int,
                         idempotency_key: str,
                         provider: FiscalProvider | None) -> FiscalResult:
    """Fail closed: do not silently complete mandatory fiscalization."""
    tenant.validate()
    if not tenant.enabled or provider is None:
        raise FiscalNotConfigured("Certified fiscal provider is not configured")
    if order_id <= 0 or not idempotency_key.strip():
        raise ValueError("Order ID and idempotency key are required")
    result = provider.issue_receipt(tenant=tenant, order_id=order_id,
                                    idempotency_key=idempotency_key)
    if not result.provider_receipt_id or not result.fiscal_sign or not result.qr_payload:
        raise RuntimeError("Provider did not return a valid fiscal receipt")
    return result
