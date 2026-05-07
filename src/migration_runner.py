import os
import sqlite3
from typing import List

class MigrationRunner:
    def __init__(self, db_path: str, migrations_dir: str = "migrations"):
        self.db_path = db_path
        self.migrations_dir = migrations_dir

    def run(self):
        applied_migrations = self._get_applied_migrations()
        all_migrations = self._get_all_migrations()

        conn = sqlite3.connect(self.db_path)
        try:
            for migration_file in all_migrations:
                if migration_file not in applied_migrations:
                    print(f"Applying migration: {migration_file}")
                    self._apply_migration(conn, migration_file)
        finally:
            conn.close()

    def _get_applied_migrations(self) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM migrations")
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            return [] # Table doesn't exist yet
        finally:
            conn.close()

    def _get_all_migrations(self) -> List[str]:
        if not os.path.exists(self.migrations_dir):
            return []
        files = [f for f in os.listdir(self.migrations_dir) if f.endswith(".sql")]
        
        def extract_version(filename):
            match = re.search(r'^v(\d+)', filename)
            return int(match.group(1)) if match else 0
            
        import re
        return sorted(files, key=extract_version)

    def _apply_migration(self, conn: sqlite3.Connection, filename: str):
        path = os.path.join(self.migrations_dir, filename)
        with open(path, 'r') as f:
            sql = f.read()

        cursor = conn.cursor()
        try:
            # Execute script
            cursor.executescript(sql)
            
            # Record migration
            # We need to ensure the migrations table exists even if it was just created in v1
            cursor.execute("CREATE TABLE IF NOT EXISTS migrations (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            cursor.execute("INSERT INTO migrations (name) VALUES (?)", (filename,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Failed to apply migration {filename}: {e}")
            raise e
