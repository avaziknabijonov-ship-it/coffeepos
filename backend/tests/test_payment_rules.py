import pytest
from app.payment_rules import PaymentPart, validate_split_payment, validate_refund


def test_split_payment_accepts_exact_total():
    validate_split_payment(50000, [PaymentPart("naqd", 20000), PaymentPart("karta", 30000)])


@pytest.mark.parametrize("parts", [
    [PaymentPart("naqd", 10000)],
    [PaymentPart("naqd", 60000)],
    [PaymentPart("karta", 0), PaymentPart("naqd", 50000)],
    [PaymentPart("crypto", 50000)],
    [],
])
def test_invalid_split_rejected(parts):
    with pytest.raises(ValueError):
        validate_split_payment(50000, parts)


def test_refund_remaining_balance():
    validate_refund(paid=50000, already_refunded=20000, requested=30000)


@pytest.mark.parametrize("paid,previous,requested", [
    (50000, 20000, 30001),
    (50000, 50000, 1),
    (50000, 0, -1),
    (50000, 60000, 1),
    (50000, 0, True),
])
def test_invalid_refund_rejected(paid, previous, requested):
    with pytest.raises(ValueError):
        validate_refund(paid=paid, already_refunded=previous, requested=requested)
