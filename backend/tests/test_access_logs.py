import io
import logging

from app.access_logs import ReceiptAccessFilter, install_receipt_access_filter


def test_uvicorn_receipt_tokens_and_query_strings_are_redacted():
    stream = io.StringIO()
    logger = logging.getLogger('uvicorn.access')
    handler = logging.StreamHandler(stream)
    previous_level, previous_propagate = logger.level, logger.propagate
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    try:
        install_receipt_access_filter()
        install_receipt_access_filter()
        assert sum(isinstance(f, ReceiptAccessFilter) for f in logger.filters) == 1
        logger.info('%s - "%s %s HTTP/%s" %d', '127.0.0.1', 'GET',
                    '/api/public/receipts/secret.jwt.token?lang=ru&extra=secret', '1.1', 200)
        logger.info('GET /api/public/receipts/second-token?lang=uz HTTP/1.1')
        logger.info('GET /api/orders?limit=5 HTTP/1.1')
        output = stream.getvalue()
        assert 'secret' not in output and 'second-token' not in output
        assert output.count('/api/public/receipts/[REDACTED]') == 2
        assert 'HTTP/1.1' in output and '/api/orders?limit=5' in output
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate


def test_named_log_arguments_are_redacted():
    record = logging.LogRecord('uvicorn.access', logging.INFO, __file__, 1,
                               '%(path)s', ({'path': '/api/public/receipts/token-value'},), None)
    assert ReceiptAccessFilter().filter(record)
    assert record.getMessage() == '/api/public/receipts/[REDACTED]'
