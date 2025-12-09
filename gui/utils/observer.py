from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import threading
import time

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, callback, target_file, debounce_ms=100):
        self.callback = callback
        self.target_file = str(Path(target_file).resolve())
        self.last_triggered = 0
        self.debounce_ms = debounce_ms / 1000.0

    def _trigger(self, event_path):
        # Check if the event is for our target file
        try:
            if str(Path(event_path).resolve()) == self.target_file:
                current_time = time.time()
                # Simple debounce
                if current_time - self.last_triggered > self.debounce_ms:
                    self.last_triggered = current_time
                    self.callback()
        except Exception:
            pass

    def on_modified(self, event):
        self._trigger(event.src_path)

    def on_created(self, event):
        self._trigger(event.src_path)
        
    def on_moved(self, event):
        # Handle file rename/move cases if the target file is the destination
        self._trigger(event.dest_path)

class AppObserver:
    def __init__(self):
        self.observer = Observer()
        self.started = False

    def start(self):
        if not self.started:
            self.observer.start()
            self.started = True

    def stop(self):
        if self.started:
            self.observer.stop()
            self.observer.join()
            self.started = False

    def schedule_file(self, file_path, callback):
        """Schedule a callback when a specific file changes."""
        path = Path(file_path)
        parent_dir = path.parent
        
        # Ensure parent exists, if not, we can't watch it yet.
        # Ideally we'd watch for creation of parent, but let's assume parent (config dir) exists.
        if not parent_dir.exists():
            print(f"Warning: Cannot watch {file_path} because parent directory {parent_dir} does not exist.")
            return

        handler = FileChangeHandler(callback, path)
        self.observer.schedule(handler, str(parent_dir), recursive=False)
