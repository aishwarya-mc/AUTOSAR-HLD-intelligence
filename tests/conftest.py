import os

# Isolated in-memory database for every test session (must be set before app import).
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LLM_PROVIDER"] = "local"  # tests are deterministic; LLM tests fake the server

import tempfile

os.environ["VECTOR_DIR"] = tempfile.mkdtemp(prefix="hld_vectors_")
