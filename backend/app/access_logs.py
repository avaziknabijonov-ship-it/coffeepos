"""Mask receipt bearer tokens in the standard Uvicorn access logger."""
import logging
import re

_RECEIPT_PATH = re.compile(r'(/api/public/receipts/)[^\s?"\'#]+(?:\?[^\s"\'#]*)?')


class ReceiptAccessFilter(logging.Filter):
    def filter(self, record):
        def redact(value):
            return _RECEIPT_PATH.sub(r'\1[REDACTED]', value) if isinstance(value, str) else value
        record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(value) for value in record.args)
        elif isinstance(record.args, dict):
            record.args = {key: redact(value) for key, value in record.args.items()}
        return True


def install_receipt_access_filter():
    logger = logging.getLogger('uvicorn.access')
    if not any(isinstance(item, ReceiptAccessFilter) for item in logger.filters):
        logger.addFilter(ReceiptAccessFilter())
