import sqlite3
import webbrowser
import os
import glob
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Static, ContentSwitcher, Markdown, TextArea
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
        self.staged_status = None

    def compose(self) -> ComposeResult:
        yield Label(self.get_label_text(), id="job-label")

    def get_label_text(self) -> str:
        prefix = ""
        if self.staged_status == 'high-pass':
            prefix = "[P] "
        elif self.staged_status == 'rejected':
            prefix = "[R] "
        return f"{prefix}[{self.score}] {self.title} - {self.company}"

    def update_staged_status(self, status: str):
        self.staged_status = status
        self.query_one("#job-label", Label).update(self.get_label_text())
        if status == 'high-pass':
            self.set_class(True, "staged-promote")
            self.set_class(False, "staged-reject")
        elif status == 'rejected':
            self.set_class(False, "staged-promote")
            self.set_class(True, "staged-reject")

class JobDetail(Static):
    def compose(self) -> ComposeResult:
        yield Markdown("Select a job to view details", id="markdown-viewer")
        yield Label("Human Notes:")
        yield TextArea(id="notes-input")

    def update_detail(self, job_data, staged_note=None):
        try:
            viewer = self.query_one("#markdown-viewer", Markdown)
            notes_input = self.query_one("#notes-input", TextArea)
        except Exception:
            # If not yet composed/mounted
            return
        
        if not job_data:
            viewer.update("Select a job to view details")
            notes_input.value = ""
            return
        
        # Unpack columns
        # 0:id, 1:title, 2:company, 3:location, 4:url, 5:text, 6:status, 7:score, 8:rationale, 9:analysis, 10:created, 11:seek_id, 12:notes
        _, title, company, location, url, text, status, score, rationale = job_data[:9]
        
        # Determine notes value (staged vs database)
        db_notes = job_data[12] if len(job_data) > 12 else ""
        notes_input.value = staged_note if staged_note is not None else (db_notes or "")

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
        viewer.update(content)

class ReviewApp(App):
    TITLE = "Project Vector: Human Review & Discovery"
    CSS = """
    Screen {
        layout: vertical;
    }
    #main-layout {
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
    .staged-promote {
        background: $success 20%;
        color: $success;
    }
    .staged-reject {
        background: $error 20%;
        color: $error;
    }
    #notes-input {
        height: 10;
        border: solid $accent;
    }
    #digest-viewer {
        padding: 2;
    }
    #suggestion-view {
        padding: 2;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "promote", "Promote (Stage)", show=True),
        Binding("r", "reject", "Reject (Stage)", show=True),
        Binding("ctrl+s", "save", "Confirm & Save", show=True),
        Binding("f", "toggle_mode", "Toggle Mode", show=True),
        Binding("d", "view_digest", "Digest", show=True),
        Binding("s", "view_suggestions", "Suggestions", show=True),
        Binding("escape", "show_main", "Back", show=True),
        Binding("o", "open_url", "Open URL", show=True),
        Binding("u", "refresh", "Refresh List", show=True),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self.current_job = None
        self.staged_changes = {} # job_id -> status
        self.staged_notes = {}   # job_id -> note_text
        self.full_mode = False

    def compose(self) -> ComposeResult:
        yield Header()
        with ContentSwitcher(initial="review-view"):
            with Horizontal(id="review-view"):
                with Vertical(id="sidebar"):
                    yield Label("Review Mode (Edge-Cases)", id="list-header")
                    yield ListView(id="job-list")
                with Container(id="detail-pane"):
                    yield JobDetail(id="details")
            with Container(id="digest-view"):
                yield Label("Opportunity Digest Viewer", classes="h1")
                yield Markdown(id="digest-viewer")
            with Container(id="suggestion-view"):
                yield Label("Discovered Search Suggestions", classes="h1")
                yield ListView(id="suggestion-list")
        yield Footer()

    def on_mount(self):
        self.refresh_list()
        # Auto-switch to Full Mode if Review Mode is empty
        if not self.full_mode and not self.query_one("#job-list", ListView).children:
            self.action_toggle_mode()

    def refresh_list(self):
        job_list = self.query_one("#job-list", ListView)
        job_list.clear()
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if self.full_mode:
                cursor.execute("SELECT * FROM jobs ORDER BY score DESC")
            else:
                cursor.execute("SELECT * FROM jobs WHERE status = 'edge-case' ORDER BY score DESC")
            jobs = [list(row) for row in cursor.fetchall()]

        for job in jobs:
            job_list.append(JobItem(job))
        
        if jobs:
            job_list.index = 0
            self.current_job = jobs[0]
            self.update_details(self.current_job)
        else:
            self.current_job = None
            self.update_details(None)

    def action_toggle_mode(self):
        # If we are in a sub-view, return to review-view first
        if self.query_one(ContentSwitcher).current != "review-view":
            self.action_show_main()
            return

        self.full_mode = not self.full_mode
        header = self.query_one("#list-header", Label)
        if self.full_mode:
            header.update("Full Mode (All Jobs)")
            self.notify("Switched to Full Mode")
        else:
            header.update("Review Mode (Edge-Cases)")
            self.notify("Switched to Review Mode")
        self.refresh_list()

    def action_view_digest(self):
        switcher = self.query_one(ContentSwitcher)
        if switcher.current == "digest-view":
            self.action_show_main()
            return

        switcher.current = "digest-view"
        viewer = self.query_one("#digest-viewer", Markdown)
        
        # Find latest digest
        digest_files = glob.glob("digests/*.md")
        if not digest_files:
            viewer.update("# No Digests Found\n\nRun `uv run python -m src.main digest` to generate one.")
            return
            
        latest_file = max(digest_files, key=os.path.getctime)
        with open(latest_file, 'r') as f:
            viewer.update(f.read())
        self.notify(f"Showing latest digest: {os.path.basename(latest_file)}")

    def action_view_suggestions(self):
        switcher = self.query_one(ContentSwitcher)
        if switcher.current == "suggestion-view":
            self.action_show_main()
            return

        switcher.current = "suggestion-view"
        s_list = self.query_one("#suggestion-list", ListView)
        s_list.clear()
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT keywords, source_keyword, total_jobs, discovered_at FROM search_suggestions ORDER BY discovered_at DESC")
            suggestions = cursor.fetchall()
            
        for keywords, source, count, discovered in suggestions:
            label = f"[{count} jobs] {keywords} (from: {source})"
            s_list.append(ListItem(Label(label)))
        
        if not suggestions:
            s_list.append(ListItem(Label("No suggestions discovered yet.")))
        self.notify("Showing search suggestions")

    def action_show_main(self):
        self.query_one(ContentSwitcher).current = "review-view"

    def update_details(self, job):
        try:
            staged_note = self.staged_notes.get(job[0]) if job else None
            self.query_one("#details", JobDetail).update_detail(job, staged_note=staged_note)
        except Exception:
            pass

    def _is_review_view(self) -> bool:
        try:
            return self.query_one(ContentSwitcher).current == "review-view"
        except Exception:
            return False

    def on_list_view_highlighted(self, event: ListView.Highlighted):
        # Only capture notes if we are in review-view and have a current job
        if self._is_review_view():
            self._capture_current_note()
        
        if event.item and hasattr(event.item, 'job'):
            self.current_job = event.item.job
            self.update_details(self.current_job)

    def on_list_view_selected(self, event: ListView.Selected):
        if self._is_review_view():
            self._capture_current_note()
        if event.item and hasattr(event.item, 'job'):
            self.current_job = event.item.job
            self.update_details(self.current_job)

    def _capture_current_note(self):
        if self.current_job:
            try:
                notes_input = self.query_one("#notes-input", TextArea)
                self.staged_notes[self.current_job[0]] = notes_input.value
            except Exception:
                pass

    def _stage_decision(self, status):
        if self.current_job:
            self._capture_current_note()
            job_id = self.current_job[0]
            self.staged_changes[job_id] = status
            
            # Find and update the specific JobItem
            job_list = self.query_one("#job-list", ListView)
            for child in job_list.children:
                if isinstance(child, JobItem) and child.job[0] == job_id:
                    child.update_staged_status(status)
                    break
            
            # Auto-advance
            job_list.index += 1
            action_name = "Promotion" if status == 'high-pass' else "Rejection"
            self.notify(f"Staged {action_name}: {self.current_job[1]}")

    def action_promote(self):
        if self.query_one(ContentSwitcher).current == "review-view":
            self._stage_decision('high-pass')

    def action_reject(self):
        if self.query_one(ContentSwitcher).current == "review-view":
            self._stage_decision('rejected')

    def action_save(self):
        self._capture_current_note()
        
        if not self.staged_changes and not self.staged_notes:
            self.notify("No changes to save.")
            return

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            for job_id, status in self.staged_changes.items():
                cursor.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
                conn.execute('INSERT INTO audit_log (action, details) VALUES (?, ?)', 
                           ("human_review", f"Job {job_id} manually set to {status}"))
            for job_id, notes in self.staged_notes.items():
                cursor.execute("UPDATE jobs SET notes = ? WHERE id = ?", (notes, job_id))
            conn.commit()
        
        count = len(set(self.staged_changes.keys()) | set(self.staged_notes.keys()))
        self.staged_changes = {}
        self.staged_notes = {}
        self.notify(f"Saved changes for {count} jobs.")
        self.refresh_list()

    def action_open_url(self):
        if self.current_job:
            url = self.current_job[4]
            webbrowser.open(url)
            self.notify("Opening browser...")

    def action_refresh(self):
        self.refresh_list()

if __name__ == "__main__":
    db = DatabaseManager()
    app = ReviewApp(db)
    app.run()
