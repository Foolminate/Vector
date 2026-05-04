import sqlite3
from contextlib import contextmanager
from .migration_runner import MigrationRunner

class DatabaseManager:
    def __init__(self, db_path="data/vector.db", migrations_dir="migrations"):
        self.db_path = db_path
        self.migrations_dir = migrations_dir
        self.init_db()

    @contextmanager
    def get_connection(self):
        """Context manager for SQLite connections with robust defaults."""
        conn = sqlite3.connect(self.db_path, timeout=30.0) # 30s busy timeout
        conn.row_factory = sqlite3.Row
        try:
            # Ensure WAL mode is active for every connection (idempotent)
            conn.execute("PRAGMA journal_mode=WAL;")
            yield conn
        finally:
            conn.close()

    def init_db(self):
        """Initialize database using migration runner."""
        # Ensure directory exists
        import os
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        runner = MigrationRunner(self.db_path, self.migrations_dir)
        runner.run()

    def log_action(self, action, details=None):
        with self.get_connection() as conn:
            conn.execute('INSERT INTO audit_log (action, details) VALUES (?, ?)', (action, details))
            conn.commit()

    def log_suggestion(self, keywords, source_keyword, total_jobs):
        """Logs or updates a related search suggestion."""
        with self.get_connection() as conn:
            try:
                conn.execute('''
                    INSERT INTO search_suggestions (keywords, source_keyword, total_jobs)
                    VALUES (?, ?, ?)
                    ON CONFLICT(keywords) DO UPDATE SET
                        total_jobs = excluded.total_jobs,
                        discovered_at = CURRENT_TIMESTAMP
                ''', (keywords, source_keyword, total_jobs))
                conn.commit()
            except sqlite3.Error as e:
                print(f"Database error logging suggestion: {e}")
