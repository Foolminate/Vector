import os
import sqlite3
import pytest
from src.migration_runner import MigrationRunner

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.db"
    return str(db_path)

@pytest.fixture
def migration_dir(tmp_path):
    m_dir = tmp_path / "migrations"
    m_dir.mkdir()
    return str(m_dir)

def test_run_migrations(test_db, migration_dir):
    # Create a dummy migration
    v1_path = os.path.join(migration_dir, "v1_test.sql")
    with open(v1_path, "w") as f:
        f.write("CREATE TABLE test_table (id INTEGER PRIMARY KEY);")
    
    runner = MigrationRunner(test_db, migration_dir)
    runner.run()
    
    # Verify table exists
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
    assert cursor.fetchone() is not None
    
    # Verify migration recorded
    cursor.execute("SELECT name FROM migrations WHERE name='v1_test.sql'")
    assert cursor.fetchone() is not None
    conn.close()

def test_skip_applied_migrations(test_db, migration_dir):
    # Setup base migrations table
    conn = sqlite3.connect(test_db)
    conn.execute("CREATE TABLE migrations (id INTEGER PRIMARY KEY, name TEXT UNIQUE, applied_at TIMESTAMP)")
    conn.execute("INSERT INTO migrations (name) VALUES ('v1_test.sql')")
    conn.commit()
    conn.close()
    
    v1_path = os.path.join(migration_dir, "v1_test.sql")
    with open(v1_path, "w") as f:
        f.write("CREATE TABLE test_table (id INTEGER PRIMARY KEY);") # This should be skipped
        
    runner = MigrationRunner(test_db, migration_dir)
    runner.run()
    
    # Verify table DOES NOT exist (skipped)
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
    assert cursor.fetchone() is None
    conn.close()
