"""Pure payment/refund validation, independent of gateway integrations.

All amounts are integer UZS. These helpers do not charge or refund money.
"""
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class PaymentPart:
    method: str
    amount: int


SUPPORTED_METHODS = frozenset({"naqd", "karta", "payme", "click"})


def validate_split_payment(total: int, parts: Sequence[PaymentPart]) -> None:
    if not isinstance(total, int) or isinstance(total, bool) or total <= 0:
        raise ValueError("Total must be a positive integer")
    if not parts:
        raise ValueError("At least one payment is required")
    for part in parts:
        if part.method not in SUPPORTED_METHODS:
            raise ValueError("Unsupported payment method")
        if not isinstance(part.amount, int) or isinstance(part.amount, bool) or part.amount <= 0:
            raise ValueError("Payment amount must be a positive integer")
    if sum(p.amount for p in parts) != total:
        raise ValueError("Payments must add up to the order total")


def validate_refund(*, paid: int, already_refunded: int, requested: int) -> None:
    if any(not isinstance(v, int) or isinstance(v, bool) for v in (paid, already_refunded, requested)):
        raise ValueError("Refund amounts must be integers")
    if paid <= 0 or already_refunded < 0 or requested <= 0:
        raise ValueError("Invalid refund amounts")
    if already_refunded > paid or requested > paid - already_refunded:
        raise ValueError("Refund exceeds remaining paid amount")
