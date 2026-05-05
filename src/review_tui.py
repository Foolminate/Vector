import sqlite3
import webbrowser
import os
import glob
import asyncio
import httpx
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Static, ContentSwitcher, Markdown, TextArea, Button
from textual.containers import Horizontal, Vertical, Container
from textual.binding import Binding
from textual import work

# Local imports
from .database import DatabaseManager
from .evaluator import JobEvaluator

class JobItem(ListItem):
    def __init__(self, job_data, staged_status=None):
        super().__init__()
        self.job = job_data
        # 0:id, 1:title, 2:company, 3:location, 4:url, 5:text, 6:status, 7:score, 8:rationale, 9:analysis, 10:created, 11:seek_id, 12:notes, 13:last_checked, 14:is_valid, 15:last_decision_by, 16:expiration
        self.job_id = job_data[0]
        self.title = job_data[1]
        self.company = job_data[2]
        self.score = job_data[7]
        self.status = job_data[6]
        self.is_valid = job_data[14] if len(job_data) > 14 else 1
        self.last_decision_by = job_data[15] if len(job_data) > 15 else 'robot'
        self.staged_status = staged_status

    def compose(self) -> ComposeResult:
        yield Label(self.get_label_text(), id="job-label")

    def get_label_text(self) -> str:
        # High-Fidelity Emoji Mapping
        status = self.staged_status if self.staged_status else self.status
        decision_by = 'human' if self.staged_status else self.last_decision_by
        
        icon = ""
        who = "🤖" if decision_by == 'robot' else "👤"
        
        if self.is_valid == 0:
            icon = "⏰"
        elif status == 'shortlisted':
            icon = "✅"
        elif status == 'discarded':
            icon = "❌"
        elif status == 'high-pass':
            icon = "✅" if not self.staged_status else "⬆️"
        elif status == 'edge-case':
            icon = "❓"
        elif status == 'rejected':
            icon = "❌" if not self.staged_status else "⬇️"
        elif status == 'deleted':
            icon = "🗑️"
        elif status == 'new':
            icon = "✨"
        
        # Determine Visual Grouping
        self.remove_class("staged-promote")
        self.remove_class("staged-reject")
        self.remove_class("dimmed")
        self.remove_class("urgent")
        self.remove_class("expired")

        if self.is_valid == 0:
            self.add_class("expired")
        elif self.staged_status == 'high-pass':
            self.add_class("staged-promote")
        elif self.staged_status == 'rejected':
            self.add_class("staged-reject")
        elif self.staged_status == 'deleted':
            self.add_class("urgent")
        elif status == 'edge-case':
            self.add_class("urgent")
        elif status in ['rejected', 'discarded', 'low-pass']:
            self.add_class("dimmed")
        elif status == 'shortlisted' and decision_by == 'robot':
            self.set_class(True, "bright-shortlist")

        return f"{icon}{who} [{self.score}] {self.title} - {self.company}"

    def update_staged_status(self, status: str):
        self.staged_status = status
        self.query_one("#job-label", Label).update(self.get_label_text())

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
            return
        
        if not job_data:
            viewer.update("Select a job to view details")
            notes_input.value = ""
            return
        
        # Unpack columns (indices may vary, using list index for safety)
        # 0:id, 1:title, 2:company, 3:location, 4:url, 5:text, 6:status, 7:score, 8:rationale, 9:analysis, 10:created, 11:seek_id, 12:notes, 13:last_checked, 14:is_valid, 15:last_decision_by, 16:expiration
        title = job_data[1]
        company = job_data[2]
        location = job_data[3]
        url = job_data[4]
        status = job_data[6]
        score = job_data[7]
        rationale = job_data[8]
        is_valid = job_data[14] if len(job_data) > 14 else 1
        last_checked = job_data[13] if len(job_data) > 13 else "Never"
        expires = job_data[16] if len(job_data) > 16 else "Unknown"
        
        db_notes = job_data[12] if len(job_data) > 12 else ""
        notes_input.value = staged_note if staged_note is not None else (db_notes or "")

        content = f"""
# {title}
**Company:** {company} | **Location:** {location}
**Score:** {score} | **Status:** {status}
**Valid:** {'Yes' if is_valid else 'No (Expired)'} | **Last Checked:** {last_checked}
**Expires Around:** {expires}

## AI Rationale
{rationale}

## URL
{url}

---
[Press 'O' to open in browser | 'D' to Trigger Agent 2 (Force Digest)]
"""
        viewer.update(content)

class ReviewApp(App):
    TITLE = "Project Vector: High-Fidelity Review"
    CSS = """
    Screen { layout: vertical; }
    #main-layout { layout: horizontal; }
    #sidebar { width: 40%; border-right: solid $accent; }
    #detail-pane { width: 60%; padding: 1; }
    ListItem { padding: 0 1; }
    .staged-promote { background: $success 30%; color: $text; }
    .staged-reject { background: $error 30%; color: $text; }
    .urgent { background: $warning 20%; border: solid $warning; }
    .dimmed { opacity: 0.5; }
    .expired { background: $surface; color: $text-disabled; text-style: strike; }
    .bright-shortlist { background: $success 50%; color: $text; text-style: bold; }
    #notes-input { height: 8; border: solid $accent; }
    #digest-viewer { padding: 2; }
    #suggestion-view { padding: 2; }
    #empty-digest-state { align: center middle; height: 100%; }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "promote", "Promote", show=True),
        Binding("r", "reject", "Reject", show=True),
        Binding("x", "mark_delete", "Delete", show=True),
        Binding("backspace", "clear_stage", "Undo", show=True),
        Binding("ctrl+s", "save", "Confirm & Save", show=True),
        Binding("f", "toggle_mode", "Toggle Mode", show=True),
        Binding("d", "view_digest", "Digests", show=True),
        Binding("s", "view_suggestions", "Suggestions", show=True),
        Binding("v", "verify_selected", "Verify Row", show=True),
        Binding("V", "verify_all", "Verify All", show=True),
        Binding("D", "force_digest", "Force Agent 2", show=False),
        Binding("escape", "show_main", "Back", show=True),
        Binding("o", "open_url", "Open", show=True),
        Binding("u", "refresh", "Refresh", show=True),
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
        with ContentSwitcher(initial="review-view", id="main-switcher"):
            with Horizontal(id="review-view"):
                with Vertical(id="sidebar"):
                    yield Label("Review Mode", id="list-header")
                    yield ListView(id="job-list")
                with Container(id="detail-pane"):
                    yield JobDetail(id="details")
            with Horizontal(id="digest-view"):
                with Vertical(id="digest-sidebar"):
                    yield Label("Past Digests", id="digest-header")
                    yield ListView(id="digest-list")
                with Container(id="digest-pane"):
                    with ContentSwitcher(initial="digest-markdown"):
                        yield Markdown(id="digest-viewer")
                        with Vertical(id="empty-digest-state"):
                            yield Label("No digests found. Run Agent 2 to generate one.")
                            yield Button("Run Evaluation (High-Pass Only)", id="run-eval-btn", variant="primary")
            with Container(id="suggestion-view"):
                yield Label("Discovered Search Suggestions", classes="h1")
                yield ListView(id="suggestion-list")
        yield Footer()

    def on_mount(self):
        self.refresh_list()
        if not self.full_mode and not self.query_one("#job-list", ListView).children:
            self.action_toggle_mode()

    def refresh_list(self):
        job_list = self.query_one("#job-list", ListView)
        job_list.clear()
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM jobs "
            if not self.full_mode:
                query += "WHERE status IN ('edge-case', 'new') "
            query += "ORDER BY score DESC"
            cursor.execute(query)
            jobs = [list(row) for row in cursor.fetchall()]

        for job in jobs:
            staged = self.staged_changes.get(job[0])
            job_list.append(JobItem(job, staged_status=staged))
        
        if jobs:
            job_list.index = 0
            self.current_job = jobs[0]
            self.update_details(self.current_job)
        else:
            self.current_job = None
            self.update_details(None)

    def action_toggle_mode(self):
        if self.query_one("#main-switcher", ContentSwitcher).current != "review-view":
            self.action_show_main()
            return

        self.full_mode = not self.full_mode
        header = self.query_one("#list-header", Label)
        header.update("Full Mode" if self.full_mode else "Review Mode")
        self.refresh_list()

    def action_view_digest(self):
        switcher = self.query_one("#main-switcher", ContentSwitcher)
        if switcher.current == "digest-view":
            self.action_show_main()
            return

        switcher.current = "digest-view"
        from .digest_manager import DigestManager
        dm = DigestManager(self.db)
        
        dates = dm.get_available_dates()
        d_list = self.query_one("#digest-list", ListView)
        d_list.clear()
        
        for d in dates:
            d_list.append(ListItem(Label(d), id=f"date-{d}"))
        
        pane_switcher = self.query_one("#digest-pane ContentSwitcher")
        if dates:
            pane_switcher.current = "digest-markdown"
            d_list.index = 0
            viewer = self.query_one("#digest-viewer", Markdown)
            viewer.update(dm.render_digest(dates[0]))
        else:
            pane_switcher.current = "empty-digest-state"

    def action_view_suggestions(self):
        switcher = self.query_one("#main-switcher", ContentSwitcher)
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
            
        for s in suggestions:
            s_list.append(ListItem(Label(f"[{s[2]} jobs] '{s[0]}' (from '{s[1]}') - {s[3]}")))

    def action_show_main(self):
        self.query_one("#main-switcher", ContentSwitcher).current = "review-view"
        self.query_one("#job-list").focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "run-eval-btn":
            self.run_background_evaluation()

    @work(exclusive=True)
    async def run_background_evaluation(self):
        self.notify("Agent 2: Starting evaluation of high-pass jobs...")
        evaluator = JobEvaluator(self.db)
        # We wrap the synchronous method in a thread
        await asyncio.to_thread(evaluator.evaluate_all_new)
        self.notify("Agent 2: Evaluation complete.")
        self.action_view_digest() # Refresh view

    def action_force_digest(self):
        if self.current_job:
            self.run_single_evaluation(self.current_job)

    @work(exclusive=True)
    async def run_single_evaluation(self, job):
        await self._run_single_evaluation_logic(job)

    async def _run_single_evaluation_logic(self, job):
        self.notify(f"Forcing Agent 2 on: {job[1]}")
        evaluator = JobEvaluator(self.db)
        # job[0]:id, 1:title, 2:company, 3:location, 5:text
        result = await asyncio.to_thread(evaluator.evaluate_job, job[0], job[1], job[2], job[3], job[5])
        if result:
            await asyncio.to_thread(evaluator.save_evaluation, job[0], result)
            # Update last_decision_by to human since it was forced
            with self.db.get_connection() as conn:
                conn.execute("UPDATE jobs SET last_decision_by = 'human' WHERE id = ?", (job[0],))
                conn.commit()
            self.notify("Agent 2 evaluation complete.")
            self.refresh_list()

    def action_verify_selected(self):
        if self.current_job:
            self.run_validity_check([self.current_job])

    def action_verify_all(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # "Law": Check all active jobs, or rejected jobs past expiration
            cursor.execute("SELECT * FROM jobs WHERE status NOT IN ('rejected', 'discarded') OR expiration_date < CURRENT_TIMESTAMP")
            jobs = [list(row) for row in cursor.fetchall()]
        if jobs:
            self.run_validity_check(jobs)

    @work(exclusive=True)
    async def run_validity_check(self, jobs):
        await self._run_validity_check_logic(jobs)

    async def _run_validity_check_logic(self, jobs):
        total = len(jobs)
        self.notify(f"Starting validity check for {total} jobs...")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            with self.db.get_connection() as conn:
                for i, job in enumerate(jobs):
                    self.notify(f"Checking {i+1}/{total}: {job[1]}")
                    try:
                        is_valid = await self._check_url_validity(client, job[4])
                    except Exception:
                        is_valid = 1 # Assume valid on network error to be safe
                    
                    # Law: Auto-mark for deletion if rejected and expired
                    if is_valid == 0 and job[6] in ['rejected', 'discarded']:
                        conn.execute("UPDATE jobs SET status = 'deleted', is_valid = 0, last_checked_at = CURRENT_TIMESTAMP WHERE id = ?", (job[0],))
                    else:
                        conn.execute("UPDATE jobs SET is_valid = ?, last_checked_at = CURRENT_TIMESTAMP WHERE id = ?", (is_valid, job[0]))
                conn.commit()
            
        self.notify(f"Validity check complete for {total} jobs.")
        self.refresh_list()

    async def _check_url_validity(self, client: httpx.AsyncClient, url: str) -> int:
        """Seek URLs redirect to home or 404 if expired. Return 1 for valid, 0 for invalid."""
        resp = await client.head(url, follow_redirects=True)
        # A valid job should return 200 and have /job/ in the final URL
        return 1 if (resp.status_code == 200 and "/job/" in str(resp.url)) else 0

    def update_details(self, job):
        try:
            staged_note = self.staged_notes.get(job[0]) if job else None
            self.query_one("#details", JobDetail).update_detail(job, staged_note=staged_note)
        except Exception:
            pass

    def on_list_view_highlighted(self, event: ListView.Highlighted):
        try:
            if self.query_one("#main-switcher", ContentSwitcher).current == "review-view":
                self._capture_current_note()
        except Exception:
            pass
            
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
            
            job_list = self.query_one("#job-list", ListView)
            for child in job_list.children:
                if isinstance(child, JobItem) and child.job_id == job_id:
                    child.update_staged_status(status)
                    break
            job_list.index += 1

    def action_promote(self): self._stage_decision('high-pass')
    def action_reject(self): self._stage_decision('rejected')
    def action_mark_delete(self): self._stage_decision('deleted')
    
    def action_clear_stage(self):
        if self.current_job:
            job_id = self.current_job[0]
            if job_id in self.staged_changes:
                del self.staged_changes[job_id]
                job_list = self.query_one("#job-list", ListView)
                for child in job_list.children:
                    if isinstance(child, JobItem) and child.job_id == job_id:
                        child.update_staged_status(None)
                        break
                self.notify("Cleared staged change.")

    def action_save(self):
        self._capture_current_note()
        if not self.staged_changes and not self.staged_notes:
            self.notify("No changes to save.")
            return

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            for job_id, status in self.staged_changes.items():
                if status == 'deleted':
                    cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
                else:
                    cursor.execute("UPDATE jobs SET status = ?, last_decision_by = 'human' WHERE id = ?", (status, job_id))
            for job_id, notes in self.staged_notes.items():
                cursor.execute("UPDATE jobs SET notes = ? WHERE id = ?", (notes, job_id))
            conn.commit()
        
        self.staged_changes = {}
        self.staged_notes = {}
        self.notify("Changes saved to database.")
        self.refresh_list()

    def action_open_url(self):
        if self.current_job:
            webbrowser.open(self.current_job[4])
            self.notify("Opening browser...")

    def action_refresh(self): self.refresh_list()

if __name__ == "__main__":
    db = DatabaseManager()
    app = ReviewApp(db)
    app.run()
