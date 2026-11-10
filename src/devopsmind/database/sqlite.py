import sqlite3
from src.devopsmind.config import settings

def init_db():
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()

    # Analysis Snapshots
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analysis_runs (
            run_id TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            health_score INTEGER DEFAULT 0,
            status TEXT NOT NULL
        )
    ''')

    # Agent Findings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_findings (
            finding_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            severity TEXT NOT NULL,
            file_path TEXT NOT NULL,
            line_number INTEGER,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            recommended_fix TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES analysis_runs(run_id)
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database successfully initialized at {settings.DB_PATH}")