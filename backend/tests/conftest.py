import os
import tempfile

# Shared isolated database for the whole suite, set before the app is imported.
os.environ.setdefault("ALLOW_PUBLIC_REGISTRATION", "1")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
