from __future__ import annotations
#!/usr/bin/env python3

r"""
SparkVerse :: NexCore Mission Board TUI

- Hybrid H1 layout (Tasks / Projects / Ideas)
- ANSI Shadow MISSION BOARD banner in @ + \ frame
- Theme switching: solarized_muted <-> nightowl_muted
- Modes:
    1 = Tasks (Kanban-style columns)
    2 = Projects (with progress bars)
    3 = Ideas (with simple bars)
- Data stored in /opt/nexcore/data/

Dependencies:
    pip install textual
"""


import json
import os
from dataclasses import dataclass, asdict
from typing import List, Literal, Optional
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Footer, Input, ListView, ListItem, Label
from textual.reactive import reactive
from textual.theme import Theme

# ----------------------------
# Paths
# ----------------------------

DATA_DIR = "/opt/nexcore/data"
TASKS_PATH = os.path.join(DATA_DIR, "mission_tasks.json")
PROJECTS_PATH = os.path.join(DATA_DIR, "mission_projects.json")
IDEAS_PATH = os.path.join(DATA_DIR, "mission_ideas.json")


# ----------------------------
# Data models
# ----------------------------

Status = Literal["ToDo", "Doing", "Done"]
Term = Literal["Short", "Mid", "Long"]


@dataclass
class Task:
    title: str
    priority: str = "Medium"
    status: Status = "ToDo"
    due_term: Term = "Short"
    notes: str = ""


@dataclass
class Project:
    name: str
    term: Term = "Mid"
    priority: str = "Medium"
    status: str = "Active"
    progress: int = 0  # 0-100


@dataclass
class Idea:
    title: str
    category: str = "General"
    metric_label: str = "Signal"
    metric_value: int = 0  # 0-100


# ----------------------------
# Persistence helpers
# ----------------------------

def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def load_json(path: str, default):
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return default
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data) -> None:
    _ensure_data_dir()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_tasks() -> List[Task]:
    raw = load_json(TASKS_PATH, [])
    return [Task(**t) for t in raw]


def save_tasks(tasks: List[Task]) -> None:
    save_json(TASKS_PATH, [asdict(t) for t in tasks])


def load_projects() -> List[Project]:
    raw = load_json(PROJECTS_PATH, [])
    return [Project(**p) for p in raw]


def save_projects(projects: List[Project]) -> None:
    save_json(PROJECTS_PATH, [asdict(p) for p in projects])


def load_ideas() -> List[Idea]:
    raw = load_json(IDEAS_PATH, [])
    return [Idea(**i) for i in raw]


def save_ideas(ideas: List[Idea]) -> None:
    save_json(IDEAS_PATH, [asdict(i) for i in ideas])


# ----------------------------
# Progress bar helpers (ASCII, muted)
# ----------------------------

def ascii_bar(percent: int, width: int = 20) -> str:
    """Return a muted block-style ASCII bar like [▓▓▓░░]."""
    percent = max(0, min(100, percent))
    filled = int(width * (percent / 100))
    empty = width - filled
    return "[" + ("▓" * filled) + ("░" * empty) + f"] {percent:3d}%"


# ----------------------------
# Banner (ANSI Shadow + @ / \ frame)
# ----------------------------

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


class BannerView(Static):
    """Big dramatic ASCII header for 'drama mode'."""

    def compose(self) -> ComposeResult:
        yield Static(BANNER, id="banner-ascii")


# ----------------------------
# Theme definitions (muted, navy/slate, no neon)
# ----------------------------

SOLARIZED_MUTED = Theme(
    name="solarized_muted",
    primary="#5f8f9d",
    secondary="#3c5a70",
    accent="#6fa9bd",
    foreground="#cbd6d1",
    background="#002b36",
    surface="#073642",
    panel="#073642",
    success="#6a9f70",
    warning="#cb8b4b",
    error="#dc322f",
    dark=True,
)

NIGHTOWL_MUTED = Theme(
    name="nightowl_muted",
    primary="#6fa9bd",
    secondary="#4a657a",
    accent="#93e9eb",
    foreground="#c7dff4",
    background="#01111c",
    surface="#08202e",
    panel="#08202e",
    success="#6a9f70",
    warning="#e0a85c",
    error="#dc322f",
    dark=True,
)


# ----------------------------
# Main App
# ----------------------------

class MissionBoardApp(App):
    """SparkVerse :: Mission Board for NexCore."""

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
        color: $foreground;
    }

    #title-bar {
        height: 1;
        padding: 0 2;
        background: $surface;
        color: $foreground;
        text-style: bold;
    }

    #mode-container {
        height: 1fr;
        padding: 1 1;
    }

    #mode-root {
        height: 1fr;
    }

    #status-bar {
        height: 2;
        padding: 0 1;
        background: $surface;
        color: $foreground-muted;
    }

    Footer {
        background: $surface;
        color: $foreground-muted;
    }

    #tasks-kanban {
        layout: horizontal;
        height: 1fr;
    }

    .kanban-column {
        border: round $panel;
        background: $panel;
        height: 1fr;
    }

    .kanban-header {
        height: 1;
        padding: 0 1;
        text-style: bold;
        background: $surface;
    }

    ListView {
        height: 1fr;
    }

    ListView:focus {
        border: round $accent;
    }

    .proj-line, .idea-line {
        height: auto;
        padding: 0 1;
    }

    #banner-ascii {
        padding: 1 1;
        text-align: center;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("1", "mode_tasks", "Tasks"),
        ("2", "mode_projects", "Projects"),
        ("3", "mode_ideas", "Ideas"),
        ("t", "switch_theme", "Theme"),
        ("h", "toggle_banner", "Header"),
        ("a", "add_item", "Add"),
        ("e", "edit_item", "Edit"),
        ("d", "delete_item", "Delete"),
        ("space", "cycle_status", "Cycle Status"),
        (":", "focus_command", "Command"),
    ]

    current_mode: reactive[str] = reactive("tasks")
    current_theme_name: reactive[str] = reactive("nightowl_muted")
    show_banner: reactive[bool] = reactive(True)

    tasks: reactive[List[Task]] = reactive([])
    projects: reactive[List[Project]] = reactive([])
    ideas: reactive[List[Idea]] = reactive([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks = load_tasks()
        self.projects = load_projects()
        self.ideas = load_ideas()

    # ----------------------------
    # Compose UI
    # ----------------------------

    def compose(self) -> ComposeResult:
        if self.show_banner:
            yield BannerView(id="banner-root")
        else:
            yield Static(self._title_text(), id="title-bar")
            with Vertical(id="mode-container"):
                yield Vertical(id="mode-root")  # Vertical so it can hold child widgets
            yield Static("Ready.", id="status-bar")
            yield Input(placeholder="Command (Esc to cancel)", id="command-input")
            yield Footer()

    # ----------------------------
    # Lifecycle
    # ----------------------------

    def on_mount(self) -> None:
        self.register_theme(SOLARIZED_MUTED)
        self.register_theme(NIGHTOWL_MUTED)
        self.theme = self.current_theme_name

        if self.show_banner:
            banner = self.query_one("#banner-root")
            if banner:
                self.set_focus(banner)
        else:
            self._refresh_mode_root()

    # ----------------------------
    # Core layout refresh
    # ----------------------------

    def _refresh_mode_root(self) -> None:
        """Clear mode-root and re-mount content for the current mode."""
        mode_root = self.query_one("#mode-root", Vertical)

        # Remove all existing children cleanly
        for child in list(mode_root.children):
            child.remove()

        # Mount fresh content directly into mode_root (which IS attached)
        if self.current_mode == "tasks":
            self._mount_tasks(mode_root)
        elif self.current_mode == "projects":
            self._mount_projects(mode_root)
        else:
            self._mount_ideas(mode_root)

        # Keep command input hidden until invoked
        cmd = self.query_one("#command-input", Input)
        cmd.display = False

    # ----------------------------
    # Mode mounters
    # (parent is always already attached to the DOM when these are called)
    # ----------------------------

    def _mount_tasks(self, parent: Vertical) -> None:
        """Build and mount the Kanban board into parent."""
        columns: dict[str, list] = {"ToDo": [], "Doing": [], "Done": []}
        for idx, t in enumerate(self.tasks, start=1):
            columns[t.status].append((idx, t))

        # Mount the kanban container into the already-attached parent first
        kanban = Horizontal(id="tasks-kanban")
        parent.mount(kanban)  # kanban is now attached

        for name in ["ToDo", "Doing", "Done"]:
            lv = ListView(id=f"kanban-{name.lower()}")
            for idx, t in columns[name]:
                glyph = self._status_glyph(t)
                lv.append(ListItem(Label(f"[{idx:02d}] {t.title}  {glyph}")))

            # Pass children into constructor — safe before col is mounted
            col = Vertical(
                Static(f" {name.upper()}", classes="kanban-header"),
                lv,
                classes="kanban-column",
            )
            kanban.mount(col)  # kanban IS attached, so this is safe

    def _mount_projects(self, parent: Vertical) -> None:
        """Build and mount project lines into parent."""
        if not self.projects:
            parent.mount(Static("No projects yet. Press 'a' to add one.", classes="proj-line"))
            return
        for idx, p in enumerate(self.projects, start=1):
            bar = ascii_bar(p.progress, width=20)
            line = f"[{idx:02d}] {p.name:<28} {bar}"
            parent.mount(Static(line, classes="proj-line"))

    def _mount_ideas(self, parent: Vertical) -> None:
        """Build and mount idea lines into parent."""
        if not self.ideas:
            parent.mount(Static("No ideas logged. Press 'a' to add one.", classes="idea-line"))
            return
        for idx, idea in enumerate(self.ideas, start=1):
            bar = ascii_bar(idea.metric_value, width=14)
            line = f"[{idx:02d}] {idea.category:<10} {idea.title:<32} {idea.metric_label}: {bar}"
            parent.mount(Static(line, classes="idea-line"))

    # ----------------------------
    # Status glyph helper
    # ----------------------------

    def _status_glyph(self, task: Task) -> str:
        if task.status == "ToDo":
            return "● 0%"
        elif task.status == "Doing":
            return "◐ 50%"
        else:
            return "● 100%"

    # ----------------------------
    # Title + status bar
    # ----------------------------

    def _title_text(self) -> str:
        mode_label = {
            "tasks": "TASKS",
            "projects": "PROJECTS",
            "ideas": "IDEAS",
        }[self.current_mode]
        return f"SPARKVERSE :: MISSION BOARD — MODE: {mode_label} | Theme: {self.current_theme_name}"

    def set_status(self, msg: str) -> None:
        if self.show_banner:
            return
        bar = self.query_one("#status-bar", Static)
        bar.update(msg)

    # ----------------------------
    # Actions / keybindings
    # ----------------------------

    def action_mode_tasks(self) -> None:
        if self.show_banner:
            return
        self.current_mode = "tasks"
        self.query_one("#title-bar", Static).update(self._title_text())
        self._refresh_mode_root()
        self.set_status("Switched to Tasks mode.")

    def action_mode_projects(self) -> None:
        if self.show_banner:
            return
        self.current_mode = "projects"
        self.query_one("#title-bar", Static).update(self._title_text())
        self._refresh_mode_root()
        self.set_status("Switched to Projects mode.")

    def action_mode_ideas(self) -> None:
        if self.show_banner:
            return
        self.current_mode = "ideas"
        self.query_one("#title-bar", Static).update(self._title_text())
        self._refresh_mode_root()
        self.set_status("Switched to Ideas mode.")

    def action_switch_theme(self) -> None:
        if self.current_theme_name == "nightowl_muted":
            self.current_theme_name = "solarized_muted"
        else:
            self.current_theme_name = "nightowl_muted"
        self.theme = self.current_theme_name
        if not self.show_banner:
            self.query_one("#title-bar", Static).update(self._title_text())
            self.set_status(f"Switched theme to {self.current_theme_name}.")

    def action_toggle_banner(self) -> None:
        """Dismiss the splash banner and build the real interface."""
        if not self.show_banner:
            return

        self.show_banner = False
        self.query_one("#banner-root").remove()

        # Mount title bar
        self.mount(Static(self._title_text(), id="title-bar"))

        # Mount mode-container with mode-root inside
        # We mount the container first, then mount mode-root into it
        # so mode-root is attached before _refresh_mode_root queries it
        container = Vertical(id="mode-container")
        self.mount(container)
        container.mount(Vertical(id="mode-root"))

        # Mount remaining chrome
        self.mount(Static("Ready.", id="status-bar"))
        cmd = Input(placeholder="Command (Esc to cancel)", id="command-input")
        cmd.display = False
        self.mount(cmd)
        self.mount(Footer())

        # Now safe to populate mode-root — it's attached
        self._refresh_mode_root()

    def action_focus_command(self) -> None:
        if self.show_banner:
            return
        cmd = self.query_one("#command-input", Input)
        cmd.display = True
        cmd.value = ""
        self.set_focus(cmd)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "command-input":
            return
        raw = event.value.strip()
        event.input.display = False
        if not raw:
            return
        try:
            self._handle_command(raw)
        except Exception as e:
            self.set_status(f"Command error: {e!r}")

    # ----------------------------
    # Command parser
    # ----------------------------

    def _handle_command(self, cmd: str) -> None:
        parts = cmd.split()
        head, *rest = parts

        if head == "addtask":
            text = " ".join(rest)
            title = _extract_quoted(text) or text
            if not title:
                self.set_status("addtask needs a title.")
                return
            self.tasks.append(Task(title=title))
            save_tasks(self.tasks)
            self._refresh_mode_root()
            self.set_status(f"Added task: {title!r}")

        elif head == "addproject":
            text = " ".join(rest)
            title = _extract_quoted(text) or text
            progress = _parse_int_flag(text, "progress", default=0)
            self.projects.append(Project(name=title, progress=progress))
            save_projects(self.projects)
            self._refresh_mode_root()
            self.set_status(f"Added project: {title!r}")

        elif head == "addidea":
            text = " ".join(rest)
            title = _extract_quoted(text) or text
            category = _parse_str_flag(text, "category", default="General")
            metric_label = _parse_str_flag(text, "metric", default="Signal")
            metric_value = _parse_int_flag(text, "value", default=0)
            self.ideas.append(
                Idea(title=title, category=category,
                     metric_label=metric_label, metric_value=metric_value)
            )
            save_ideas(self.ideas)
            self._refresh_mode_root()
            self.set_status(f"Added idea: {title!r}")

        else:
            self.set_status(f"Unknown command: {head!r}")

    # ----------------------------
    # Editing hooks
    # ----------------------------

    def action_add_item(self) -> None:
        if self.show_banner:
            return
        if self.current_mode == "tasks":
            self.set_status('Use ":" then: addtask "Title"')
        elif self.current_mode == "projects":
            self.set_status('Use ":" then: addproject "Name" progress=10')
        else:
            self.set_status('Use ":" then: addidea "Title" category=CALDERA metric=Complexity value=20')

    def action_edit_item(self) -> None:
        if self.show_banner:
            return
        self.set_status("Editing is currently via command mode only (e.g. rerun with modified JSON).")

    def action_delete_item(self) -> None:
        if self.show_banner:
            return
        self.set_status("Delete is not implemented yet. (Wire up indices + commands later.)")

    def action_cycle_status(self) -> None:
        if self.show_banner or self.current_mode != "tasks":
            return
        self.set_status("Use ':' then 'addtask', or later wire SPACE to a selected row.")

    def on_input_blurred(self, event: Input.Blurred) -> None:
        if event.input.id == "command-input":
            event.input.display = False


# ----------------------------
# Parsing helpers
# ----------------------------

def _extract_quoted(text: str) -> Optional[str]:
    """Extract the first quoted string, if present."""
    if '"' not in text:
        return None
    first = text.find('"')
    second = text.find('"', first + 1)
    if first != -1 and second != -1:
        return text[first + 1:second]
    return None


def _parse_int_flag(text: str, name: str, default: int = 0) -> int:
    token = f"{name}="
    for part in text.split():
        if part.startswith(token):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return default
    return default


def _parse_str_flag(text: str, name: str, default: str = "") -> str:
    token = f"{name}="
    for part in text.split():
        if part.startswith(token):
            return part.split("=", 1)[1]
    return default or ""


if __name__ == "__main__":
    app = MissionBoardApp()
    app.run()