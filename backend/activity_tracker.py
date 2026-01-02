"""
Activity tracking module for Rin's learning capabilities.
Monitors file changes and application usage to learn user patterns.
"""

import os
import time
import threading
import fnmatch
from datetime import datetime
from typing import Optional, Callable

# Windows-specific imports
try:
    import win32gui
    import win32process
    import psutil
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    print("[ActivityTracker] Warning: pywin32/psutil not available. App tracking disabled.")

# File watching
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    # Provide stubs so class definitions don't fail
    Observer = None
    FileSystemEventHandler = object
    FileSystemEvent = object
    print("[ActivityTracker] Warning: watchdog not available. File tracking disabled.")

import database
from learning_config import get_config, is_path_excluded, is_app_excluded


class FileActivityHandler(FileSystemEventHandler):
    """Handles file system events and logs them to database."""
    
    def __init__(self, excluded_patterns: list = None):
        super().__init__()
        self.excluded_patterns = excluded_patterns or []
        self._last_events = {}  # Debounce rapid events
        self._debounce_seconds = 1.0
    
    def _should_track(self, path: str) -> bool:
        """Check if this file should be tracked."""
        if is_path_excluded(path, self.excluded_patterns):
            return False
        return True
    
    def _debounce(self, path: str, action: str) -> bool:
        """Prevent logging rapid duplicate events."""
        key = f"{path}:{action}"
        now = time.time()
        
        if key in self._last_events:
            if now - self._last_events[key] < self._debounce_seconds:
                return False
        
        self._last_events[key] = now
        return True
    
    def _log_event(self, path: str, action: str):
        """Log a file event to the database."""
        if not self._should_track(path):
            return
        
        if not self._debounce(path, action):
            return
        
        try:
            file_type = os.path.splitext(path)[1].lower() or None
            directory = os.path.dirname(path)
            
            database.add_file_activity(
                path=path,
                action=action,
                file_type=file_type,
                directory=directory
            )
            print(f"[FileTracker] {action}: {os.path.basename(path)}")
        except Exception as e:
            print(f"[FileTracker] Error logging event: {e}")
    
    def on_created(self, event: FileSystemEvent):
        if not event.is_directory:
            self._log_event(event.src_path, "created")
    
    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory:
            self._log_event(event.src_path, "modified")
    
    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory:
            self._log_event(event.src_path, "deleted")
    
    def on_moved(self, event: FileSystemEvent):
        if not event.is_directory:
            self._log_event(event.src_path, "moved_from")
            self._log_event(event.dest_path, "moved_to")


class AppTracker:
    """Tracks active application/window focus."""
    
    def __init__(self, poll_interval: float = 1.0):
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_app: Optional[str] = None
        self._current_title: Optional[str] = None
        self._focus_start: Optional[float] = None
        self._config = get_config()
    
    def _get_active_window_info(self) -> tuple[Optional[str], Optional[str]]:
        """Get the currently focused window's app name and title."""
        if not HAS_WIN32:
            return None, None
        
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None, None
            
            # Get window title
            title = win32gui.GetWindowText(hwnd)
            
            # Get process name
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process = psutil.Process(pid)
                app_name = process.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                app_name = "Unknown"
            
            return app_name, title
        except Exception:
            return None, None
    
    def _categorize_app(self, app_name: str, title: str) -> str:
        """Categorize an application based on name/title."""
        app_lower = app_name.lower()
        title_lower = title.lower() if title else ""
        
        # Development
        if any(x in app_lower for x in ["code", "studio", "pycharm", "idea", "vim", "nvim", "cursor", "antigravity"]):
            return "development"
        if any(x in app_lower for x in ["cmd", "powershell", "terminal", "windowsterminal"]):
            return "development"
        
        # Browsers
        if any(x in app_lower for x in ["chrome", "firefox", "edge", "brave", "opera", "zen"]):
            # Try to subcategorize based on title
            if any(x in title_lower for x in ["github", "stackoverflow", "docs", "documentation"]):
                return "development"
            if any(x in title_lower for x in ["youtube", "twitch", "netflix"]):
                return "entertainment"
            return "browsing"
        
        # Communication
        if any(x in app_lower for x in ["discord", "slack", "teams", "zoom", "telegram"]):
            return "communication"
        
        # Entertainment
        if any(x in app_lower for x in ["spotify", "vlc", "steam"]):
            return "entertainment"
        
        # Games (common game processes or if window title suggests game)
        if any(x in title_lower for x in ["game", "playing"]):
            return "gaming"
        
        # Productivity
        if any(x in app_lower for x in ["word", "excel", "powerpoint", "outlook", "notion"]):
            return "productivity"
        
        # File management
        if any(x in app_lower for x in ["explorer", "totalcmd", "7z"]):
            return "files"
        
        return "other"
    
    def _log_focus_end(self):
        """Log the end of focus on current app."""
        if self._current_app and self._focus_start:
            duration = int(time.time() - self._focus_start)
            min_focus = self._config.get("min_focus_seconds", 2)
            
            if duration >= min_focus and not is_app_excluded(self._current_app):
                category = self._categorize_app(self._current_app, self._current_title or "")
                database.add_app_activity(
                    app_name=self._current_app,
                    window_title=self._current_title,
                    duration_seconds=duration,
                    category=category
                )
                print(f"[AppTracker] {self._current_app} focused for {duration}s ({category})")
    
    def _poll_loop(self):
        """Main polling loop for app tracking."""
        while self._running:
            try:
                app_name, title = self._get_active_window_info()
                
                # Check if focus changed
                if app_name != self._current_app or title != self._current_title:
                    # Log end of previous focus
                    self._log_focus_end()
                    
                    # Start new focus tracking
                    self._current_app = app_name
                    self._current_title = title
                    self._focus_start = time.time()
            
            except Exception as e:
                print(f"[AppTracker] Poll error: {e}")
            
            time.sleep(self.poll_interval)
    
    def start(self):
        """Start the app tracker."""
        if self._running:
            return
        
        if not HAS_WIN32:
            print("[AppTracker] Cannot start: pywin32/psutil not available")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        print("[AppTracker] Started")
    
    def stop(self):
        """Stop the app tracker."""
        if not self._running:
            return
        
        self._running = False
        self._log_focus_end()  # Log final focus
        
        if self._thread:
            self._thread.join(timeout=2.0)
        
        print("[AppTracker] Stopped")


class ActivityCollector:
    """Main controller for all activity tracking."""
    
    def __init__(self):
        self._config = get_config()
        self._file_observer: Optional[Observer] = None
        self._app_tracker: Optional[AppTracker] = None
        self._running = False
    
    def start(self):
        """Start all activity collectors based on config."""
        if self._running:
            return
        
        if not self._config.get("enabled", True):
            print("[ActivityCollector] Tracking disabled in config")
            return
        
        self._running = True
        
        # Start file watcher
        if self._config.get("track_files", True) and HAS_WATCHDOG:
            self._start_file_watcher()
        
        # Start app tracker
        if self._config.get("track_apps", True) and HAS_WIN32:
            self._app_tracker = AppTracker()
            self._app_tracker.start()
        
        print("[ActivityCollector] Started")
    
    def _start_file_watcher(self):
        """Initialize and start file system watcher."""
        try:
            watched_dirs = self._config.get("watched_directories", [])
            excluded = self._config.get("excluded_paths", [])
            
            handler = FileActivityHandler(excluded_patterns=excluded)
            self._file_observer = Observer()
            
            for directory in watched_dirs:
                expanded = os.path.expanduser(directory)
                if os.path.isdir(expanded):
                    self._file_observer.schedule(handler, expanded, recursive=True)
                    print(f"[ActivityCollector] Watching: {expanded}")
                else:
                    print(f"[ActivityCollector] Skipping non-existent: {expanded}")
            
            self._file_observer.start()
        except Exception as e:
            print(f"[ActivityCollector] Error starting file watcher: {e}")
    
    def stop(self):
        """Stop all activity collectors."""
        if not self._running:
            return
        
        self._running = False
        
        if self._file_observer:
            self._file_observer.stop()
            self._file_observer.join(timeout=2.0)
        
        if self._app_tracker:
            self._app_tracker.stop()
        
        print("[ActivityCollector] Stopped")
    
    def is_running(self) -> bool:
        return self._running


# Global instance
activity_collector = ActivityCollector()
