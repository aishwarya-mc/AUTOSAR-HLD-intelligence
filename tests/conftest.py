import os

# Isolated in-memory database for every test session (must be set before app import).
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
