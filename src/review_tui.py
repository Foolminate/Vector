import sqlite3
import webbrowser
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Static, ContentSwitcher
from textual.containers import Horizontal, Vertical, Container
from textual.binding import Binding

# Local imports
from .database import DatabaseManager

class JobItem(ListItem):
    def __init__(self, job_data):
        super().__init__()
        self.job = job_data
        self.title = job_data[1]
        self.company = job_data[2]
        self.score = job_data[7]

    def compose(self) -> ComposeResult:
        yield Label(f"[{self.score}] {self.title} - {self.company}")

class JobDetail(Static):
    def update_detail(self, job_data):
        if not job_data:
            self.update("Select a job to view details")
            return
        
        # Unpack columns (now 12 with seek_job_id)
        # 0:id, 1:title, 2:company, 3:location, 4:url, 5:text, 6:status, 7:score, 8:rationale, 9:analysis, 10:created, 11:seek_id
        _, title, company, location, url, text, status, score, rationale = job_data[:9]
        
        content = f"""
# {title}
**Company:** {company}
**Location:** {location}
**Score:** {score}
**Status:** {status}

## AI Rationale
{rationale}

## URL
{url}

---
[Press 'O' to open in browser]
"""
        self.update(content)

class ReviewApp(App):
    TITLE = "Project Vector: Human Review"
    CSS = """
    Screen {
        layout: horizontal;
    }
    #sidebar {
        width: 40%;
        border-right: solid $accent;
    }
    #detail-pane {
        width: 60%;
        padding: 1;
    }
    ListItem {
        padding: 1;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "promote", "Promote (High-Pass)", show=True),
        Binding("r", "reject", "Reject", show=True),
        Binding("o", "open_url", "Open URL", show=True),
        Binding("u", "refresh", "Refresh List", show=True),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self.current_job = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Label("Edge-Case Roles", id="list-header")
                yield ListView(id="job-list")
            with Container(id="detail-pane"):
                yield JobDetail(id="details")
        yield Footer()

    def on_mount(self):
        self.refresh_list()

    def refresh_list(self):
        job_list = self.query_one("#job-list", ListView)
        job_list.clear()
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE status = 'edge-case' ORDER BY score DESC")
            jobs = [list(row) for row in cursor.fetchall()]

        for job in jobs:
            job_list.append(JobItem(job))
        
        if jobs:
            job_list.index = 0
            self.current_job = jobs[0]
            self.query_one("#details", JobDetail).update_detail(self.current_job)
        else:
            self.current_job = None
            self.query_one("#details", JobDetail).update("No edge-case jobs to review.")

    def on_list_view_highlighted(self, event: ListView.Highlighted):
        if event.item:
            self.current_job = event.item.job
            self.query_one("#details", JobDetail).update_detail(self.current_job)

    def on_list_view_selected(self, event: ListView.Selected):
        # Selected (Enter/Click) can also trigger detail update just in case
        if event.item:
            self.current_job = event.item.job
            self.query_one("#details", JobDetail).update_detail(self.current_job)

    def action_promote(self):
        if self.current_job:
            self.update_job_status(self.current_job[0], 'high-pass')
            self.notify(f"Promoted: {self.current_job[1]}")
            self.refresh_list()

    def action_reject(self):
        if self.current_job:
            self.update_job_status(self.current_job[0], 'rejected')
            self.notify(f"Rejected: {self.current_job[1]}")
            self.refresh_list()

    def action_open_url(self):
        if self.current_job:
            url = self.current_job[4]
            webbrowser.open(url)
            self.notify("Opening browser...")

    def action_refresh(self):
        self.refresh_list()

    def update_job_status(self, job_id, new_status):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))
            conn.commit()
        self.db.log_action("human_review", f"Job {job_id} manually set to {new_status}")

if __name__ == "__main__":
    db = DatabaseManager()
    app = ReviewApp(db)
    app.run()
