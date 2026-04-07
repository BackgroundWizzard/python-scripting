#!/usr/bin/env python3
"""
SparkVerse :: NexCore Mission Board TUI

- Hybrid layout (Tasks / Projects / Ideas)
- ANSI Shadow SPARKBOARD banner
- Theme switching: solarized_muted <-> nightowl_muted
- Modes:
    1 = Tasks  (Kanban columns)
    2 = Projects (ASCII progress bars)
    3 = Ideas    (signal bars)
- Data stored in ~/.nexcore/data/  (auto-created)

NEW in this version:
    - Timestamps  : created_at / updated_at on all items
    - Notes       : per-task notes shown as a second line in kanban
    - Priority    : Low / Medium / High with glyph, cycle with [p]

Dependencies:
    pip install textual
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Literal, Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.theme import Theme
from textual.widgets import (
    ContentSwitcher,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

# ---------------------------------------------------------------------------
# Platform-safe data path
# ---------------------------------------------------------------------------

DATA_DIR      = os.path.join(os.path.expanduser("~"), ".nexcore", "data")
TASKS_PATH    = os.path.join(DATA_DIR, "mission_tasks.json")
PROJECTS_PATH = os.path.join(DATA_DIR, "mission_projects.json")
IDEAS_PATH    = os.path.join(DATA_DIR, "mission_ideas.json")


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    """ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _age(ts: str) -> str:
    """Human-readable age from an ISO timestamp string, e.g. '3d' or '2h'."""
    try:
        created = datetime.strptime(ts, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        delta   = datetime.now(timezone.utc) - created
        days    = delta.days
        hours   = delta.seconds // 3600
        if days >= 1:
            return f"{days}d"
        if hours >= 1:
            return f"{hours}h"
        mins = delta.seconds // 60
        return f"{mins}m"
    except Exception:
        return "?"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

Status   = Literal["ToDo", "Doing", "Done"]
Term     = Literal["Short", "Mid", "Long"]
Priority = Literal["Low", "Medium", "High"]

PRIORITY_CYCLE = ["Low", "Medium", "High"]
PRIORITY_GLYPH = {"Low": "▽", "Medium": "◆", "High": "▲"}


@dataclass
class Task:
    title:      str
    priority:   str    = "Medium"
    status:     Status = "ToDo"
    due_term:   Term   = "Short"
    notes:      str    = ""
    created_at: str    = field(default_factory=_now)
    updated_at: str    = field(default_factory=_now)


@dataclass
class Project:
    name:       str
    term:       Term   = "Mid"
    priority:   str    = "Medium"
    status:     str    = "Active"
    progress:   int    = 0        # 0-100
    notes:      str    = ""
    created_at: str    = field(default_factory=_now)
    updated_at: str    = field(default_factory=_now)


@dataclass
class Idea:
    title:        str
    category:     str = "General"
    metric_label: str = "Signal"
    metric_value: int = 0         # 0-100
    notes:        str = ""
    created_at:   str = field(default_factory=_now)
    updated_at:   str = field(default_factory=_now)


# ---------------------------------------------------------------------------
# Persistence  (backward-compatible loading with .get() defaults)
# ---------------------------------------------------------------------------

def _load_json(path: str, default):
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, data) -> None:
    _ensure_data_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _task_from_dict(d: dict) -> Task:
    """Load a Task, filling in new fields if they're missing from older saves."""
    return Task(
        title      = d.get("title", ""),
        priority   = d.get("priority", "Medium"),
        status     = d.get("status", "ToDo"),
        due_term   = d.get("due_term", "Short"),
        notes      = d.get("notes", ""),
        created_at = d.get("created_at", _now()),
        updated_at = d.get("updated_at", _now()),
    )


def _project_from_dict(d: dict) -> Project:
    return Project(
        name       = d.get("name", ""),
        term       = d.get("term", "Mid"),
        priority   = d.get("priority", "Medium"),
        status     = d.get("status", "Active"),
        progress   = d.get("progress", 0),
        notes      = d.get("notes", ""),
        created_at = d.get("created_at", _now()),
        updated_at = d.get("updated_at", _now()),
    )


def _idea_from_dict(d: dict) -> Idea:
    return Idea(
        title        = d.get("title", ""),
        category     = d.get("category", "General"),
        metric_label = d.get("metric_label", "Signal"),
        metric_value = d.get("metric_value", 0),
        notes        = d.get("notes", ""),
        created_at   = d.get("created_at", _now()),
        updated_at   = d.get("updated_at", _now()),
    )


def load_tasks() -> List[Task]:
    return [_task_from_dict(t) for t in _load_json(TASKS_PATH, [])]

def save_tasks(tasks: List[Task]) -> None:
    _save_json(TASKS_PATH, [asdict(t) for t in tasks])

def load_projects() -> List[Project]:
    return [_project_from_dict(p) for p in _load_json(PROJECTS_PATH, [])]

def save_projects(projects: List[Project]) -> None:
    _save_json(PROJECTS_PATH, [asdict(p) for p in projects])

def load_ideas() -> List[Idea]:
    return [_idea_from_dict(i) for i in _load_json(IDEAS_PATH, [])]

def save_ideas(ideas: List[Idea]) -> None:
    _save_json(IDEAS_PATH, [asdict(i) for i in ideas])


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def ascii_bar(percent: int, width: int = 20) -> str:
    percent = max(0, min(100, percent))
    filled  = int(width * percent / 100)
    return "[" + "▓" * filled + "░" * (width - filled) + f"] {percent:3d}%"


def status_glyph(task: Task) -> str:
    return {"ToDo": "●", "Doing": "◐", "Done": "◉"}.get(task.status, "?")


def priority_glyph(priority: str) -> str:
    return PRIORITY_GLYPH.get(priority, "◆")


def task_label(g_idx: int, t: Task) -> str:
    """Build the display string for a single task card (1-2 lines)."""
    pg   = priority_glyph(t.priority)
    sg   = status_glyph(t)
    age  = _age(t.created_at)
    line1 = f"  [{g_idx:02d}] {pg} {sg}  {t.title}  ({age})"
    if t.notes:
        line1 += f"\n       ↳ {t.notes}"
    return line1


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

BANNER = r"""
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\@
@\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\@
@\\███████╗██████╗\\█████╗\██████╗\██╗\\██╗██████╗\\██████╗\\█████╗\██████╗\██████╗\\\@
@\\██╔════╝██╔══██╗██╔══██╗██╔══██╗██║\██╔╝██╔══██╗██╔═══██╗██╔══██╗██╔══██╗██╔══██╗\\@
@\\███████╗██████╔╝███████║██████╔╝█████╔╝\██████╔╝██║\\\██║███████║██████╔╝██║\\██║\\@
@\\╚════██║██╔═══╝\██╔══██║██╔══██╗██╔═██╗\██╔══██╗██║\\\██║██╔══██║██╔══██╗██║\\██║\\@
@\\███████║██║\\\\\██║\\██║██║\\██║██║\\██╗██████╔╝╚██████╔╝██║\\██║██║\\██║██████╔╝\\@
@\\╚══════╝╚═╝\\\\\╚═╝\\╚═╝╚═╝\\╚═╝╚═╝\\╚═╝╚═════╝\\╚═════╝\╚═╝\\╚═╝╚═╝\\╚═╝╚═════╝\\\@
@\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\@
@\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
""".strip("\n")


# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------

SOLARIZED_MUTED = Theme(
    name="solarized_muted",
    primary="#5f8f9d", secondary="#3c5a70", accent="#6fa9bd",
    foreground="#cbd6d1", background="#002b36",
    surface="#073642", panel="#073642",
    success="#6a9f70", warning="#cb8b4b", error="#dc322f",
    dark=True,
)

NIGHTOWL_MUTED = Theme(
    name="nightowl_muted",
    primary="#6fa9bd", secondary="#4a657a", accent="#93e9eb",
    foreground="#c7dff4", background="#01111c",
    surface="#08202e", panel="#08202e",
    success="#6a9f70", warning="#e0a85c", error="#dc322f",
    dark=True,
)


# ---------------------------------------------------------------------------
# Permanent panel widgets  (built once in compose, never re-created)
# ---------------------------------------------------------------------------

class TasksPanel(Vertical):
    """Kanban board — three persistent ListView columns."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="kanban-row"):
            for col in ("todo", "doing", "done"):
                with Vertical(classes="kanban-col"):
                    yield Static(f"  {col.upper()}", classes="kanban-hdr")
                    yield ListView(id=f"lv-{col}")

    def refresh_data(self, tasks: List[Task]) -> None:
        buckets: dict[str, list] = {"todo": [], "doing": [], "done": []}
        for t in tasks:
            key = t.status.lower()
            if key in buckets:
                buckets[key].append(t)

        for col, task_list in buckets.items():
            lv: ListView = self.query_one(f"#lv-{col}", ListView)
            lv.clear()
            for t in task_list:
                g_idx = tasks.index(t) + 1
                lv.append(ListItem(Label(task_label(g_idx, t))))


class ProjectsPanel(VerticalScroll):
    """Scrollable project list with ASCII progress bars."""

    def compose(self) -> ComposeResult:
        yield Static(id="proj-content")

    def refresh_data(self, projects: List[Project]) -> None:
        widget = self.query_one("#proj-content", Static)
        if not projects:
            widget.update('  No projects yet.  Press [a] to add one.')
            return
        lines = []
        for idx, p in enumerate(projects, 1):
            pg   = priority_glyph(p.priority)
            bar  = ascii_bar(p.progress, width=20)
            age  = _age(p.created_at)
            line = f"  [{idx:02d}] {pg} {p.name:<26} {bar}  [{p.status}]  ({age})"
            if p.notes:
                line += f"\n       ↳ {p.notes}"
            lines.append(line)
        widget.update("\n".join(lines))


class IdeasPanel(VerticalScroll):
    """Scrollable idea list with signal bars."""

    def compose(self) -> ComposeResult:
        yield Static(id="idea-content")

    def refresh_data(self, ideas: List[Idea]) -> None:
        widget = self.query_one("#idea-content", Static)
        if not ideas:
            widget.update('  No ideas yet.  Press [a] to add one.')
            return
        lines = []
        for idx, idea in enumerate(ideas, 1):
            bar  = ascii_bar(idea.metric_value, width=14)
            age  = _age(idea.created_at)
            line = f"  [{idx:02d}] {idea.category:<10} {idea.title:<30} {idea.metric_label}: {bar}  ({age})"
            if idea.notes:
                line += f"\n       ↳ {idea.notes}"
            lines.append(line)
        widget.update("\n".join(lines))


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class MissionBoardApp(App):
    """SparkVerse :: Mission Board for NexCore."""

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
        color: $foreground;
    }

    #splash {
        height: 1fr;
        align: center middle;
        padding: 2 4;
    }
    #banner-ascii {
        text-align: center;
        color: $primary;
    }
    #banner-hint {
        text-align: center;
        color: $secondary;
        padding-top: 1;
    }

    #title-bar {
        height: 1;
        padding: 0 2;
        background: $surface;
        color: $foreground;
        text-style: bold;
    }
    #status-bar {
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $secondary;
    }
    #command-input { margin: 0 1; }
    Footer         { background: $surface; }

    ContentSwitcher { height: 1fr; padding: 1 1; }

    TasksPanel  { height: 1fr; }
    #kanban-row { height: 1fr; }
    .kanban-col {
        border: round $panel;
        background: $panel;
        height: 1fr;
        width: 1fr;
    }
    .kanban-hdr {
        height: 1;
        padding: 0 1;
        text-style: bold;
        background: $surface;
    }
    ListView       { height: 1fr; background: $panel; }
    ListView:focus { border: round $accent; }

    ProjectsPanel, IdeasPanel { height: 1fr; padding: 0 1; }
    #proj-content, #idea-content { height: auto; }
    """

    BINDINGS = [
        ("q", "quit",          "Quit"),
        ("1", "mode_tasks",    "Tasks"),
        ("2", "mode_projects", "Projects"),
        ("3", "mode_ideas",    "Ideas"),
        ("t", "switch_theme",  "Theme"),
        ("h", "toggle_banner", "Header"),
        ("a", "add_item",      "Add"),
        ("d", "delete_item",   "Delete"),
        ("n", "note_item",     "Note"),
        ("p", "priority_item", "Priority"),
        (":",  "focus_command", "Command"),
    ]

    current_mode:       reactive[str]  = reactive("tasks")
    current_theme_name: reactive[str]  = reactive("nightowl_muted")
    show_banner:        reactive[bool] = reactive(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks:    List[Task]    = load_tasks()
        self.projects: List[Project] = load_projects()
        self.ideas:    List[Idea]    = load_ideas()
        # tracks guided command bar context
        # e.g. "add:tasks", "del:tasks", "note:tasks", "priority:tasks"
        self._pending_mode: Optional[str] = None

    # ── compose ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Vertical(id="splash"):
            yield Static(BANNER, id="banner-ascii")
            yield Static("\n  Press  [H]  to enter the Mission Board", id="banner-hint")

        yield Static("", id="title-bar")
        with ContentSwitcher(initial="tasks-panel", id="switcher"):
            yield TasksPanel(id="tasks-panel")
            yield ProjectsPanel(id="projects-panel")
            yield IdeasPanel(id="ideas-panel")
        yield Static("Ready.", id="status-bar")
        cmd = Input(placeholder="Command  (Enter = submit  |  Esc = cancel)", id="command-input")
        cmd.display = False
        yield cmd
        yield Footer()

    # ── lifecycle ─────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.register_theme(SOLARIZED_MUTED)
        self.register_theme(NIGHTOWL_MUTED)
        self.theme = self.current_theme_name
        self._set_shell_visible(False)
        self._refresh_all_panels()

    # ── visibility ───────────────────────────────────────────────────────

    def _set_shell_visible(self, visible: bool) -> None:
        for wid in ("#title-bar", "#switcher", "#status-bar", "#command-input"):
            try:
                self.query_one(wid).display = visible
            except Exception:
                pass
        try:
            self.query_one(Footer).display = visible
        except Exception:
            pass

    # ── data refresh ──────────────────────────────────────────────────────

    def _refresh_all_panels(self) -> None:
        self.query_one(TasksPanel).refresh_data(self.tasks)
        self.query_one(ProjectsPanel).refresh_data(self.projects)
        self.query_one(IdeasPanel).refresh_data(self.ideas)

    def _refresh_current_panel(self) -> None:
        if self.current_mode == "tasks":
            self.query_one(TasksPanel).refresh_data(self.tasks)
        elif self.current_mode == "projects":
            self.query_one(ProjectsPanel).refresh_data(self.projects)
        else:
            self.query_one(IdeasPanel).refresh_data(self.ideas)

    # ── title / status ────────────────────────────────────────────────────

    def _title_text(self) -> str:
        label = {"tasks": "TASKS", "projects": "PROJECTS", "ideas": "IDEAS"}[self.current_mode]
        return f"  SPARKVERSE :: MISSION BOARD  —  {label}  |  theme: {self.current_theme_name}"

    def _set_status(self, msg: str) -> None:
        try:
            self.query_one("#status-bar", Static).update(msg)
        except Exception:
            pass

    # ── command bar helper ────────────────────────────────────────────────

    def _open_command(self, pending: Optional[str] = None, placeholder: str = "") -> None:
        self._pending_mode = pending
        cmd = self.query_one("#command-input", Input)
        cmd.placeholder = placeholder or "Command  (Enter = submit  |  Esc = cancel)"
        cmd.display     = True
        cmd.value       = ""
        self.set_focus(cmd)

    # ── actions ───────────────────────────────────────────────────────────

    def action_toggle_banner(self) -> None:
        if not self.show_banner:
            return
        self.show_banner = False
        self.query_one("#splash").display = False
        self._set_shell_visible(True)
        self.query_one("#title-bar", Static).update(self._title_text())
        self.query_one("#switcher", ContentSwitcher).current = "tasks-panel"

    def _switch_mode(self, mode: str, panel_id: str, label: str) -> None:
        if self.show_banner:
            return
        self.current_mode = mode
        self.query_one("#switcher", ContentSwitcher).current = panel_id
        self.query_one("#title-bar", Static).update(self._title_text())
        self._refresh_current_panel()
        self._set_status(f"{label} mode.")

    def action_mode_tasks(self)    -> None:
        self._switch_mode("tasks",    "tasks-panel",    "Tasks")

    def action_mode_projects(self) -> None:
        self._switch_mode("projects", "projects-panel", "Projects")

    def action_mode_ideas(self)    -> None:
        self._switch_mode("ideas",    "ideas-panel",    "Ideas")

    def action_switch_theme(self) -> None:
        self.current_theme_name = (
            "solarized_muted" if self.current_theme_name == "nightowl_muted"
            else "nightowl_muted"
        )
        self.theme = self.current_theme_name
        if not self.show_banner:
            self.query_one("#title-bar", Static).update(self._title_text())
            self._set_status(f"Theme: {self.current_theme_name}")

    def action_focus_command(self) -> None:
        if self.show_banner:
            return
        self._open_command(pending=None)

    def action_add_item(self) -> None:
        if self.show_banner:
            return
        prompts = {
            "tasks":    ("add:tasks",    "New task title:"),
            "projects": ("add:projects", "New project name:"),
            "ideas":    ("add:ideas",    "New idea title:"),
        }
        pending, placeholder = prompts[self.current_mode]
        self._open_command(pending=pending, placeholder=placeholder)

    def action_delete_item(self) -> None:
        if self.show_banner:
            return
        counts = {
            "tasks":    len(self.tasks),
            "projects": len(self.projects),
            "ideas":    len(self.ideas),
        }
        n = counts[self.current_mode]
        if n == 0:
            self._set_status("Nothing to delete."); return
        self._open_command(
            pending=f"del:{self.current_mode}",
            placeholder=f"Delete which number? (1-{n})",
        )

    def action_note_item(self) -> None:
        """[n] — attach or update a note on an item."""
        if self.show_banner:
            return
        counts = {
            "tasks":    len(self.tasks),
            "projects": len(self.projects),
            "ideas":    len(self.ideas),
        }
        n = counts[self.current_mode]
        if n == 0:
            self._set_status("Nothing to annotate."); return
        self._open_command(
            pending=f"note_pick:{self.current_mode}",
            placeholder=f"Add note to which number? (1-{n})",
        )

    def action_priority_item(self) -> None:
        """[p] — cycle priority on a task or project."""
        if self.show_banner:
            return
        if self.current_mode not in ("tasks", "projects"):
            self._set_status("Priority is available for Tasks and Projects only.")
            return
        counts = {"tasks": len(self.tasks), "projects": len(self.projects)}
        n = counts[self.current_mode]
        if n == 0:
            self._set_status("Nothing here yet."); return
        self._open_command(
            pending=f"priority:{self.current_mode}",
            placeholder=f"Cycle priority on which number? (1-{n})",
        )

    # ── command input events ──────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "command-input":
            return
        raw = event.value.strip()
        event.input.display     = False
        event.input.placeholder = "Command  (Enter = submit  |  Esc = cancel)"

        if not raw:
            self._pending_mode = None
            return

        pending, self._pending_mode = self._pending_mode, None

        try:
            self._dispatch_pending(pending, raw)
        except Exception as exc:
            self._set_status(f"Error: {exc!r}")

    def on_input_blurred(self, event: Input.Blurred) -> None:
        if event.input.id == "command-input":
            event.input.display     = False
            event.input.placeholder = "Command  (Enter = submit  |  Esc = cancel)"
            self._pending_mode      = None

    # ── pending dispatcher ────────────────────────────────────────────────

    def _dispatch_pending(self, pending: Optional[str], raw: str) -> None:
        """Route guided-prompt input to the right handler."""

        # ── Add ──
        if pending == "add:tasks":
            t = Task(title=raw)
            self.tasks.append(t)
            save_tasks(self.tasks)
            self.query_one(TasksPanel).refresh_data(self.tasks)
            self._set_status(f"Added task: {raw!r}")

        elif pending == "add:projects":
            p = Project(name=raw)
            self.projects.append(p)
            save_projects(self.projects)
            self.query_one(ProjectsPanel).refresh_data(self.projects)
            self._set_status(f"Added project: {raw!r}")

        elif pending == "add:ideas":
            i = Idea(title=raw)
            self.ideas.append(i)
            save_ideas(self.ideas)
            self.query_one(IdeasPanel).refresh_data(self.ideas)
            self._set_status(f"Added idea: {raw!r}")

        # ── Delete ──
        elif pending == "del:tasks":
            idx = _parse_index(raw, len(self.tasks))
            if idx is None:
                self._set_status(f"Invalid number. Enter 1-{len(self.tasks)}."); return
            removed = self.tasks.pop(idx)
            save_tasks(self.tasks)
            self.query_one(TasksPanel).refresh_data(self.tasks)
            self._set_status(f"Deleted task: {removed.title!r}")

        elif pending == "del:projects":
            idx = _parse_index(raw, len(self.projects))
            if idx is None:
                self._set_status(f"Invalid number. Enter 1-{len(self.projects)}."); return
            removed = self.projects.pop(idx)
            save_projects(self.projects)
            self.query_one(ProjectsPanel).refresh_data(self.projects)
            self._set_status(f"Deleted project: {removed.name!r}")

        elif pending == "del:ideas":
            idx = _parse_index(raw, len(self.ideas))
            if idx is None:
                self._set_status(f"Invalid number. Enter 1-{len(self.ideas)}."); return
            removed = self.ideas.pop(idx)
            save_ideas(self.ideas)
            self.query_one(IdeasPanel).refresh_data(self.ideas)
            self._set_status(f"Deleted idea: {removed.title!r}")

        # ── Note — step 1: pick item number ──
        elif pending in ("note_pick:tasks", "note_pick:projects", "note_pick:ideas"):
            mode = pending.split(":")[1]
            counts = {"tasks": len(self.tasks), "projects": len(self.projects), "ideas": len(self.ideas)}
            idx = _parse_index(raw, counts[mode])
            if idx is None:
                self._set_status(f"Invalid number."); return
            # store "note_text:tasks:2" to carry the index into next prompt
            self._open_command(
                pending=f"note_text:{mode}:{idx}",
                placeholder="Type the note (or leave blank to clear):",
            )

        # ── Note — step 2: type the note text ──
        elif pending and pending.startswith("note_text:"):
            _, mode, idx_str = pending.split(":", 2)
            idx = int(idx_str)
            if mode == "tasks":
                self.tasks[idx].notes      = raw
                self.tasks[idx].updated_at = _now()
                save_tasks(self.tasks)
                self.query_one(TasksPanel).refresh_data(self.tasks)
                name = self.tasks[idx].title
            elif mode == "projects":
                self.projects[idx].notes      = raw
                self.projects[idx].updated_at = _now()
                save_projects(self.projects)
                self.query_one(ProjectsPanel).refresh_data(self.projects)
                name = self.projects[idx].name
            else:
                self.ideas[idx].notes      = raw
                self.ideas[idx].updated_at = _now()
                save_ideas(self.ideas)
                self.query_one(IdeasPanel).refresh_data(self.ideas)
                name = self.ideas[idx].title
            verb = "Cleared note on" if not raw else "Note added to"
            self._set_status(f"{verb}: {name!r}")

        # ── Priority cycle ──
        elif pending == "priority:tasks":
            idx = _parse_index(raw, len(self.tasks))
            if idx is None:
                self._set_status(f"Invalid number. Enter 1-{len(self.tasks)}."); return
            current  = self.tasks[idx].priority
            nxt      = PRIORITY_CYCLE[(PRIORITY_CYCLE.index(current) + 1) % len(PRIORITY_CYCLE)]
            self.tasks[idx].priority   = nxt
            self.tasks[idx].updated_at = _now()
            save_tasks(self.tasks)
            self.query_one(TasksPanel).refresh_data(self.tasks)
            self._set_status(f"Priority → {nxt}  {priority_glyph(nxt)}  on: {self.tasks[idx].title!r}")

        elif pending == "priority:projects":
            idx = _parse_index(raw, len(self.projects))
            if idx is None:
                self._set_status(f"Invalid number. Enter 1-{len(self.projects)}."); return
            current  = self.projects[idx].priority
            nxt      = PRIORITY_CYCLE[(PRIORITY_CYCLE.index(current) + 1) % len(PRIORITY_CYCLE)]
            self.projects[idx].priority   = nxt
            self.projects[idx].updated_at = _now()
            save_projects(self.projects)
            self.query_one(ProjectsPanel).refresh_data(self.projects)
            self._set_status(f"Priority → {nxt}  {priority_glyph(nxt)}  on: {self.projects[idx].name!r}")

        else:
            # Raw ":" command mode
            self._handle_command(raw)

    # ── command parser  (raw ":" mode) ───────────────────────────────────

    def _handle_command(self, cmd: str) -> None:
        parts       = cmd.split()
        head, *rest = parts
        text        = " ".join(rest)

        # ── Tasks ──
        if head == "addtask":
            title = _extract_quoted(text) or text
            if not title:
                self._set_status('Usage: addtask My task title'); return
            self.tasks.append(Task(title=title))
            save_tasks(self.tasks)
            self.query_one(TasksPanel).refresh_data(self.tasks)
            self._set_status(f"Added task: {title!r}")

        elif head == "deltask":
            idx = _parse_index(text, len(self.tasks))
            if idx is None:
                self._set_status(f"Usage: deltask <1-{len(self.tasks)}>"); return
            removed = self.tasks.pop(idx)
            save_tasks(self.tasks)
            self.query_one(TasksPanel).refresh_data(self.tasks)
            self._set_status(f"Deleted task: {removed.title!r}")

        elif head == "donetask":
            idx = _parse_index(text, len(self.tasks))
            if idx is None:
                self._set_status(f"Usage: donetask <1-{len(self.tasks)}>"); return
            self.tasks[idx].status     = "Done"
            self.tasks[idx].updated_at = _now()
            save_tasks(self.tasks)
            self.query_one(TasksPanel).refresh_data(self.tasks)
            self._set_status(f"Marked done: {self.tasks[idx].title!r}")

        elif head == "doingtask":
            idx = _parse_index(text, len(self.tasks))
            if idx is None:
                self._set_status(f"Usage: doingtask <1-{len(self.tasks)}>"); return
            self.tasks[idx].status     = "Doing"
            self.tasks[idx].updated_at = _now()
            save_tasks(self.tasks)
            self.query_one(TasksPanel).refresh_data(self.tasks)
            self._set_status(f"Moved to Doing: {self.tasks[idx].title!r}")

        elif head == "todotask":
            idx = _parse_index(text, len(self.tasks))
            if idx is None:
                self._set_status(f"Usage: todotask <1-{len(self.tasks)}>"); return
            self.tasks[idx].status     = "ToDo"
            self.tasks[idx].updated_at = _now()
            save_tasks(self.tasks)
            self.query_one(TasksPanel).refresh_data(self.tasks)
            self._set_status(f"Moved to ToDo: {self.tasks[idx].title!r}")

        elif head == "note":
            # note <n> the text goes here
            tokens = text.split(None, 1)
            if len(tokens) < 1:
                self._set_status("Usage: note <n> Your note text"); return
            idx = _parse_index(tokens[0], len(self.tasks))
            if idx is None:
                self._set_status(f"Usage: note <1-{len(self.tasks)}> text"); return
            note_text = tokens[1] if len(tokens) > 1 else ""
            self.tasks[idx].notes      = note_text
            self.tasks[idx].updated_at = _now()
            save_tasks(self.tasks)
            self.query_one(TasksPanel).refresh_data(self.tasks)
            self._set_status(f"Note set on: {self.tasks[idx].title!r}")

        elif head == "priority":
            idx = _parse_index(text, len(self.tasks))
            if idx is None:
                self._set_status(f"Usage: priority <1-{len(self.tasks)}>"); return
            current = self.tasks[idx].priority
            nxt     = PRIORITY_CYCLE[(PRIORITY_CYCLE.index(current) + 1) % len(PRIORITY_CYCLE)]
            self.tasks[idx].priority   = nxt
            self.tasks[idx].updated_at = _now()
            save_tasks(self.tasks)
            self.query_one(TasksPanel).refresh_data(self.tasks)
            self._set_status(f"Priority → {nxt} on: {self.tasks[idx].title!r}")

        # ── Projects ──
        elif head == "addproject":
            title    = _extract_quoted(text) or _strip_flags(text)
            progress = _parse_int_flag(text, "progress", default=0)
            if not title:
                self._set_status('Usage: addproject My project  progress=10'); return
            self.projects.append(Project(name=title, progress=progress))
            save_projects(self.projects)
            self.query_one(ProjectsPanel).refresh_data(self.projects)
            self._set_status(f"Added project: {title!r}")

        elif head == "delproject":
            idx = _parse_index(text, len(self.projects))
            if idx is None:
                self._set_status(f"Usage: delproject <1-{len(self.projects)}>"); return
            removed = self.projects.pop(idx)
            save_projects(self.projects)
            self.query_one(ProjectsPanel).refresh_data(self.projects)
            self._set_status(f"Deleted project: {removed.name!r}")

        elif head == "progress":
            tokens = text.split()
            if len(tokens) < 2:
                self._set_status("Usage: progress <n> <0-100>"); return
            idx = _parse_index(tokens[0], len(self.projects))
            if idx is None:
                self._set_status(f"Usage: progress <1-{len(self.projects)}> <0-100>"); return
            try:
                val = max(0, min(100, int(tokens[1])))
            except ValueError:
                self._set_status("Progress value must be 0-100."); return
            self.projects[idx].progress   = val
            self.projects[idx].updated_at = _now()
            save_projects(self.projects)
            self.query_one(ProjectsPanel).refresh_data(self.projects)
            self._set_status(f"Updated: {self.projects[idx].name!r} → {val}%")

        # ── Ideas ──
        elif head == "addidea":
            title        = _extract_quoted(text) or _strip_flags(text)
            category     = _parse_str_flag(text, "category", default="General")
            metric_label = _parse_str_flag(text, "metric",   default="Signal")
            metric_value = _parse_int_flag(text, "value",    default=0)
            if not title:
                self._set_status('Usage: addidea My idea  category=Ops metric=Signal value=50')
                return
            self.ideas.append(
                Idea(title=title, category=category,
                     metric_label=metric_label, metric_value=metric_value)
            )
            save_ideas(self.ideas)
            self.query_one(IdeasPanel).refresh_data(self.ideas)
            self._set_status(f"Added idea: {title!r}")

        elif head == "delidea":
            idx = _parse_index(text, len(self.ideas))
            if idx is None:
                self._set_status(f"Usage: delidea <1-{len(self.ideas)}>"); return
            removed = self.ideas.pop(idx)
            save_ideas(self.ideas)
            self.query_one(IdeasPanel).refresh_data(self.ideas)
            self._set_status(f"Deleted idea: {removed.title!r}")

        elif head in ("help", "?"):
            self._set_status(
                "Keys: [a]dd [d]el [n]ote [p]riority  |  "
                "Commands: addtask | deltask | donetask | doingtask | todotask | note | priority | "
                "addproject | delproject | progress | addidea | delidea"
            )
        else:
            self._set_status(f"Unknown command: {head!r}  — type 'help' for a list")


# ---------------------------------------------------------------------------
# Parsing utilities
# ---------------------------------------------------------------------------

def _strip_flags(text: str) -> str:
    return " ".join(p for p in text.split() if "=" not in p).strip()


def _extract_quoted(text: str) -> Optional[str]:
    first = text.find('"')
    if first == -1:
        return None
    second = text.find('"', first + 1)
    return text[first + 1:second] if second != -1 else None


def _parse_int_flag(text: str, name: str, default: int = 0) -> int:
    for part in text.split():
        if part.startswith(f"{name}="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return default
    return default


def _parse_str_flag(text: str, name: str, default: str = "") -> str:
    for part in text.split():
        if part.startswith(f"{name}="):
            return part.split("=", 1)[1]
    return default


def _parse_index(text: str, length: int) -> Optional[int]:
    try:
        n = int(text.strip())
    except (ValueError, AttributeError):
        return None
    return n - 1 if 1 <= n <= length else None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _ensure_data_dir()
    MissionBoardApp().run()
