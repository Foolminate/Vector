import sqlite3
import webbrowser
import os
import glob
import asyncio
import httpx
import ssl
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Static, ContentSwitcher, Markdown, TextArea, Button, ProgressBar
from textual.containers import Horizontal, Vertical, Container
from textual.binding import Binding
from textual.message import Message
from textual import work

# Robust SSL handling for Windows
try:
    import truststore
    truststore.inject_into_ssl()
    _ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
except ImportError:
    _ssl_context = None

# Local imports
from .database import DatabaseManager
from .evaluator import JobEvaluator
from .pipeline import PipelineObserver, AgentPipeline, EvaluationStrategy
from .llm_client import ModelAdapter
from .config_loader import load_config

class JobStatusUpdate(Message):
    """Sent when a job's processing status changes."""
    def __init__(self, job_id: str, processing_status: str):
        super().__init__()
        self.job_id = job_id
        self.processing_status = processing_status

class PipelineProgress(Message):
    """Sent to update the global progress bar."""
    def __init__(self, completed: int, total: int):
        super().__init__()
        self.completed = completed
        self.total = total

class TuiPipelineObserver(PipelineObserver):
    """Bridge between AgentPipeline events and Textual messages."""
    def __init__(self, app: App):
        self.app = app
        self.total = 0
        self.completed = 0

    def on_job_start(self, job_id: str):
        self.app.post_message(JobStatusUpdate(job_id, "analyzing"))

    def on_job_complete(self, job_id: str):
        self.completed += 1
        self.app.post_message(JobStatusUpdate(job_id, "idle"))
        self.app.post_message(PipelineProgress(self.completed, self.total))

    def on_job_error(self, job_id: str, error: str):
        self.app.post_message(JobStatusUpdate(job_id, "error"))

    def on_queue_empty(self):
        self.app.post_message(PipelineProgress(0, 0)) # Reset/Hide
        self.completed = 0
        self.total = 0

class JobItem(ListItem):
    def __init__(self, job_data, staged_status=None):
        super().__init__()
        self.job = job_data
        self.job_id = job_data["id"]
        self.title = job_data["job_title"]
        self.company = job_data["company"]
        self.score = job_data["score"]
        self.status = job_data["status"]
        
        # Row objects don't have .get(), use key check or indexing
        keys = job_data.keys()
        self.is_valid = job_data["is_valid"] if "is_valid" in keys else 1
        self.last_decision_by = job_data["last_decision_by"] if "last_decision_by" in keys else 'robot'
        self.processing_status = job_data["processing_status"] if "processing_status" in keys else "idle"
        self.staged_status = staged_status

    def compose(self) -> ComposeResult:
        yield Label(self.get_label_text(), id="job-label")

    def get_label_text(self) -> str:
        # High-Fidelity Emoji Mapping
        status = self.staged_status if self.staged_status else self.status
        decision_by = 'human' if self.staged_status else self.last_decision_by
        
        icon = ""
        who = "🤖" if decision_by == 'robot' else "👤"
        
        # Priority for processing icons
        if self.processing_status == "analyzing":
            icon = "🔄"
        elif self.processing_status == "error":
            icon = "⚠️"
        elif self.is_valid == 0:
            icon = "⏰"
        elif status == 'shortlisted':
            icon = "✅"
        elif status == 'discarded':
            icon = "❌" if not self.staged_status or self.staged_status == 'discarded' else "⬇️"
        elif status == 'high-pass':
            icon = "✅" if not self.staged_status else "⬆️"
        elif status == 'edge-case':
            icon = "❓"
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
        elif self.staged_status == 'discarded':
            self.add_class("staged-reject")
        elif self.staged_status == 'deleted':
            self.add_class("urgent")
        elif status == 'edge-case':
            self.add_class("urgent")
        elif status in ['discarded', 'low-pass']:
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
        
        title = job_data["job_title"]
        company = job_data["company"]
        location = job_data["location"]
        url = job_data["url"]
        status = job_data["status"]
        score = job_data["score"]
        rationale = job_data["analysis_json"] or "No rationale available."
        is_valid = job_data["is_valid"] if "is_valid" in job_data.keys() else 1
        last_checked = job_data["last_checked_at"] if "last_checked_at" in job_data.keys() else "Never"
        expires = job_data["expiration_date"] if "expiration_date" in job_data.keys() else "Unknown"
        
        db_notes = job_data["notes"] if "notes" in job_data.keys() else ""
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
    #pipeline-progress { margin: 1 2; display: none; }
    #pipeline-progress.active { display: block; }
    """
    
    BINDINGS = [
        # ... bindings ...
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
        Binding("ctrl+c", "cancel_tasks", "Stop Tasks", show=True),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self.current_job = None
        self.staged_changes = {} # job_id -> status
        self.staged_notes = {}   # job_id -> note_text
        self.full_mode = False
        
        config = load_config()
        model_id = config.get('ai_models', {}).get('evaluator', 'gemini-3.1-pro-preview')
        adapter = ModelAdapter(model_id, repo=db_manager)
        self.pipeline = AgentPipeline(db_manager, adapter)
        self.observer = TuiPipelineObserver(self)
        self.pipeline.subscribe(self.observer)

    def compose(self) -> ComposeResult:
        yield Header()
        with ContentSwitcher(initial="review-view", id="main-switcher"):
            with Horizontal(id="review-view"):
                with Vertical(id="sidebar"):
                    yield Label("Review Mode", id="list-header")
                    yield ListView(id="job-list")
                    yield ProgressBar(id="pipeline-progress", show_percentage=True, show_eta=True)
                with Container(id="detail-pane"):
                    yield JobDetail(id="details")
            # ... rest of compose ...
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

    def on_job_status_update(self, message: JobStatusUpdate):
        """Handle real-time status updates from the pipeline."""
        job_list = self.query_one("#job-list", ListView)
        for child in job_list.children:
            if isinstance(child, JobItem) and str(child.job_id) == str(message.job_id):
                child.processing_status = message.processing_status
                child.query_one("#job-label", Label).update(child.get_label_text())
                break

    def on_pipeline_progress(self, message: PipelineProgress):
        """Update the progress bar."""
        pb = self.query_one("#pipeline-progress", ProgressBar)
        if message.total > 0:
            pb.set_class(True, "active")
            pb.update(total=message.total, progress=message.completed)
        else:
            pb.set_class(False, "active")

    def action_cancel_tasks(self):
        """Interrupt all background workers."""
        for worker in self.workers:
            worker.cancel()
        self.notify("All background tasks cancelled.")
        self.query_one("#pipeline-progress", ProgressBar).set_class(False, "active")
        self.refresh_list()

    def on_mount(self):
        self.refresh_list()
        if not self.full_mode and not self.query_one("#job-list", ListView).children:
            self.action_toggle_mode()

    def refresh_list(self):
        job_list = self.query_one("#job-list", ListView)
        job_list.clear()
        
        with self.db.get_connection() as conn:
            query = "SELECT * FROM jobs "
            if not self.full_mode:
                query += "WHERE status IN ('edge-case', 'new') "
            query += "ORDER BY score DESC"
            cursor = conn.execute(query)
            jobs = cursor.fetchall()

        for job in jobs:
            staged = self.staged_changes.get(job["id"])
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
            cursor = conn.execute("SELECT keywords, source_keyword, total_jobs, discovered_at FROM search_suggestions ORDER BY discovered_at DESC")
            suggestions = cursor.fetchall()
            
        for s in suggestions:
            s_list.append(ListItem(Label(f"[{s['total_jobs']} jobs] '{s['keywords']}' (from '{s['source_keyword']}') - {s['discovered_at']}")))

    def action_show_main(self):
        self.query_one("#main-switcher", ContentSwitcher).current = "review-view"
        self.query_one("#job-list").focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "run-eval-btn":
            self.run_background_evaluation()

    @work(exclusive=True)
    async def run_background_evaluation(self):
        """Pushes all high-pass jobs to the pipeline and runs Agent 2."""
        with self.db.get_connection() as conn:
            query = "SELECT id FROM jobs WHERE status = 'high-pass' AND analysis_json IS NULL"
            jobs = conn.execute(query).fetchall()
        
        if not jobs:
            self.notify("No new high-pass jobs to evaluate.")
            return

        self.observer.total = len(jobs)
        self.query_one("#pipeline-progress", ProgressBar).set_class(True, "active")
        
        for job in jobs:
            self.db.update_processing_status(job["id"], "idle")
            self.pipeline.push(job["id"])
            
        self.notify(f"Queued {len(jobs)} jobs for deep evaluation.")
        
        # Run worker in background and wait for queue to drain
        worker = asyncio.create_task(self.pipeline.process_queue(EvaluationStrategy()))
        try:
            await self.pipeline.queue.join()
        finally:
            worker.cancel()

    def action_force_digest(self):
        if self.current_job:
            self.run_single_evaluation(self.current_job)

    @work(exclusive=True)
    async def run_single_evaluation(self, job):
        """Forces evaluation for a single job via the pipeline."""
        await self._run_single_evaluation_logic(job)

    async def _run_single_evaluation_logic(self, job):
        self.observer.total = 1
        self.query_one("#pipeline-progress", ProgressBar).set_class(True, "active")
        self.db.update_processing_status(job["id"], "idle")
        self.pipeline.push(job["id"])
        
        worker = asyncio.create_task(self.pipeline.process_queue(EvaluationStrategy(decision_by='human')))
        try:
            await self.pipeline.queue.join()
        finally:
            worker.cancel()
            
        self.refresh_list()

    def action_verify_selected(self):
        if self.current_job:
            self.run_validity_check([self.current_job])

    def action_verify_all(self):
        with self.db.get_connection() as conn:
            # "Law": Check all active jobs, or discarded jobs past expiration
            cursor = conn.execute("SELECT * FROM jobs WHERE status != 'discarded' OR expiration_date < CURRENT_TIMESTAMP")
            jobs = cursor.fetchall()
        if jobs:
            self.run_validity_check(jobs)

    @work(exclusive=True)
    async def run_validity_check(self, jobs):
        await self._run_validity_check_logic(jobs)

    async def _run_validity_check_logic(self, jobs):
        total = len(jobs)
        self.notify(f"Starting validity check for {total} jobs...")
        
        # Use robust SSL settings and increased timeouts for Windows stability
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=20.0),
            verify=_ssl_context if _ssl_context else True,
            http2=False
        ) as client:
            for i, job in enumerate(jobs):
                self.notify(f"Checking {i+1}/{total}: {job['job_title']}")
                try:
                    is_valid = await self._check_url_validity(client, job['url'])
                except Exception:
                    is_valid = 1 # Assume valid on network error to be safe
                
                # Law: Auto-mark for archiving if discarded and expired
                with self.db.get_connection() as conn:
                    if is_valid == 0 and job['status'] == 'discarded':
                        conn.execute("UPDATE jobs SET status = 'archived', is_valid = 0, last_checked_at = CURRENT_TIMESTAMP WHERE id = ?", (job['id'],))
                    else:
                        conn.execute("UPDATE jobs SET is_valid = ?, last_checked_at = CURRENT_TIMESTAMP WHERE id = ?", (is_valid, job['id']))
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
            staged_note = self.staged_notes.get(job['id']) if job else None
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
                self.staged_notes[self.current_job['id']] = notes_input.value
            except Exception:
                pass

    def _stage_decision(self, status):
        if self.current_job:
            self._capture_current_note()
            job_id = self.current_job['id']
            self.staged_changes[job_id] = status
            
            job_list = self.query_one("#job-list", ListView)
            for child in job_list.children:
                if isinstance(child, JobItem) and child.job_id == job_id:
                    child.update_staged_status(status)
                    break
            job_list.index += 1

    def action_promote(self): self._stage_decision('high-pass')
    def action_reject(self): self._stage_decision('discarded')
    def action_mark_delete(self): self._stage_decision('deleted')
    
    def action_clear_stage(self):
        if self.current_job:
            job_id = self.current_job['id']
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

        for job_id, status in self.staged_changes.items():
            if status == 'deleted':
                self.db.delete_job(job_id)
            else:
                self.db.update_job_status(job_id, status, decision_by='human')
        
        for job_id, notes in self.staged_notes.items():
            if notes.strip():
                self.db.add_note(job_id, notes)
        
        self.staged_changes = {}
        self.staged_notes = {}
        self.notify("Changes saved to database.")
        self.refresh_list()


    def action_open_url(self):
        if self.current_job:
            webbrowser.open(self.current_job["url"])
            self.notify("Opening browser...")


    def action_refresh(self): self.refresh_list()

if __name__ == "__main__":
    db = DatabaseManager()
    app = ReviewApp(db)
    app.run()
