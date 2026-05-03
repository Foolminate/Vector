import sqlite3

class DatabaseManager:
    def __init__(self, db_path="data/vector.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create jobs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                url TEXT UNIQUE,
                raw_text TEXT,
                status TEXT DEFAULT 'new',
                score INTEGER,
                rationale TEXT,
                analysis_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create audit_log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action TEXT NOT NULL,
                details TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    def log_action(self, action, details=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO audit_log (action, details) VALUES (?, ?)', (action, details))
        conn.commit()
        conn.close()
