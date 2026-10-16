"""Every pytest invocation owns an isolated temporary database, before imports.

Never let test collection order select the developer's/default cafe database.
Individual subprocess/backup tests can create additional isolated databases.
"""
import os
from tempfile import TemporaryDirectory

_test_database = TemporaryDirectory(prefix='coffeepos-pytest-')
os.environ['DATABASE_URL'] = f'sqlite:///{_test_database.name}/test.db'
os.environ['SEED_DEMO'] = '1'
os.environ['ALLOW_PUBLIC_REGISTRATION'] = '1'
os.environ['LICENSE_ENFORCEMENT'] = '0'


def pytest_unconfigure(config):
    _test_database.cleanup()
