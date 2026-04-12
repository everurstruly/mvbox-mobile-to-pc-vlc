import time
import shutil
from pathlib import Path

from PySide6 import QtCore
from PySide6.QtCore import QThread, Signal

try:
    import win32com.client  # type: ignore
    import pythoncom
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from ..devices.mtp_client import get_mtp_item_by_path, scan_mtp
from ..devices.local_scanner import scan_local
from ..core.transfer_planner import build_transfer_plan, subtitle_destination

def wait_for_copy_to_finish(
    stage_dir: Path,
    source_size: int,
    progress_callback,
    expected_name: str,
    existing_names: set[str] | None = None,
    timeout: int = 3600,
    should_abort=None,
) -> Path | None:
    """
    Since MTP CopyHere is an asynchronous Windows Shell operation, we must poll
    the destination file to know when it has finished writing before we can safely rename it.
    We watch the stage_dir dynamically because MTP can sometimes mutate filenames during transfer.
    """
    start = time.time()
    filepath = None
    existing_names = existing_names or set()
    expected_stem = Path(expected_name).stem.lower()
    expected_ext = Path(expected_name).suffix.lower()
    last_wait_notice = 0.0
    last_lock_notice = 0.0

    def choose_candidate() -> Path | None:
        candidates = [item for item in stage_dir.iterdir() if item.name not in existing_names]
        if not candidates:
            return None

        exact = [item for item in candidates if item.name.lower() == expected_name.lower()]
        if exact:
            return exact[0]

        compatible = [
            item
            for item in candidates
            if item.suffix.lower() == expected_ext and expected_stem in item.stem.lower()
        ]
        if compatible:
            compatible.sort(key=lambda item: item.stat().st_mtime, reverse=True)
            return compatible[0]

        candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        return candidates[0]
    
    # Wait for the shell to start allocating a file in the empty stage directory
    for _ in range(150): # up to 30 seconds wait for MTP preparation
        if should_abort and should_abort():
            return None
        filepath = choose_candidate()
        if filepath:
            break
        progress_callback("__FILE_PROGRESS__:PULSE")
        if time.time() - last_wait_notice >= 2.0:
            progress_callback(f"__TRANSFER_STATE__:Waiting for Windows to start copying {expected_name}")
            last_wait_notice = time.time()
        time.sleep(0.2)
        
    if not filepath:
        return None
        
    # Poll file size and wait for the write lock to release
    last_known_size = -1
    stable_ticks = 0

    while time.time() - start < timeout:
        if should_abort and should_abort():
            return None

        filepath = choose_candidate() or filepath

        try:
            curr_size = filepath.stat().st_size
        except Exception:
            time.sleep(0.5)
            continue

        # Progress display
        if source_size > 0:
            pct = min(99, int((curr_size / source_size) * 100))
            progress_callback(f"__FILE_PROGRESS__:{pct}")
        else:
            progress_callback("__FILE_PROGRESS__:PULSE")

        # Gate 1: size must reach source size before we even try the lock.
        # This is the primary fix — the old code skipped this gate entirely.
        if source_size > 0 and curr_size < source_size:
            if time.time() - last_lock_notice >= 2.0:
                progress_callback(
                    f"__TRANSFER_STATE__:Receiving {filepath.name} "
                    f"({curr_size // (1024 * 1024)} MB / {source_size // (1024 * 1024)} MB)"
                )
                last_lock_notice = time.time()
            last_known_size = curr_size
            stable_ticks = 0
            time.sleep(0.5)
            continue

        # Gate 2: size must be stable for 4 consecutive polls (2 seconds).
        # Fallback for devices where source_item.Size returns 0 or -1.
        if curr_size == last_known_size:
            stable_ticks += 1
        else:
            stable_ticks = 0
            last_known_size = curr_size

        if stable_ticks < 4:
            time.sleep(0.5)
            continue

        # Gate 3: try to open with read+write access.
        # 'r+b' maps to GENERIC_READ|GENERIC_WRITE on Windows, which is
        # genuinely exclusive. The old 'a' mode used FILE_SHARE_WRITE and
        # succeeded even while the MTP driver was still writing chunks.
        try:
            with open(filepath, 'r+b'):
                pass
            time.sleep(0.5)
            progress_callback("__FILE_PROGRESS__:100")
            return filepath
        except (IOError, PermissionError):
            stable_ticks = 0
            if time.time() - last_lock_notice >= 2.0:
                progress_callback(f"__TRANSFER_STATE__:Waiting for file access: {filepath.name}")
                progress_callback("__TRANSFER_HINT__:If Windows opened a copy dialog, resolve it to continue.")
                last_lock_notice = time.time()
            time.sleep(0.5)

    return None

def move_unique(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        source.replace(target)
        return target
    stem = target.stem
    ext = target.suffix
    for idx in range(1, 1000):
        candidate = target.with_name(f"{stem} ({idx}){ext}")
        if not candidate.exists():
            source.replace(candidate)
            return candidate
    return target

class ScanWorker(QtCore.QThread):
    progress = QtCore.Signal(str)
    finished = QtCore.Signal(list, list)
    failed = Signal(str)

    def __init__(self, mode: str, root_identifier: str, config: dict, target_paths: list = None):
        super().__init__()
        self.mode = mode
        self.root_identifier = root_identifier
        self.config = config
        self.target_paths = target_paths or []
        self._is_aborted = False
        self._use_partial = False
        self.videos = []; self.subtitles = [] # Persist state for Review
        import threading
        self._pause_event = threading.Event()
        self._pause_event.set()

    def pause(self):
        """Pause the scan at the next checkpoint in the walk loop."""
        self._pause_event.clear()

    def resume(self):
        """Resume a paused scan from where it left off."""
        self._pause_event.set()

    def abort(self, use_partial: bool = False):
        self._use_partial = use_partial
        self._is_aborted = True
        self._pause_event.set() 

    def _check_abort(self) -> bool:
        """Called inside scan loop. Blocks here when paused, returns True when aborted."""
        self._pause_event.wait()  # blocking when paused — resumes when .set() is called
        return self._is_aborted

    def run(self):
        try:
            if self.mode == "mtp":
                self.videos, self.subtitles = scan_mtp(
                    self.root_identifier,
                    self.config,
                    self.progress.emit,
                    self.target_paths,
                    should_abort=self._check_abort,
                )
            else:
                self.videos, self.subtitles = scan_local(
                    Path(self.root_identifier),
                    self.config,
                    self.progress.emit,
                    should_abort=self._check_abort,
                )
            if self._is_aborted and not self._use_partial:
                self.failed.emit("Scan cancelled.")
                return
            self.finished.emit(self.videos, self.subtitles)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.failed.emit(str(exc))

class SyncWorker(QThread):
    progress = Signal(str)
    finished = Signal()
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, items: list, config: dict):
        super().__init__()
        self.items = items
        self.config = config
        self._is_aborted = False

    def abort(self):
        self._is_aborted = True

    def run(self):
        try:
            if WIN32_AVAILABLE:
                pythoncom.CoInitialize()
                
            items = self.items
            total = len(items)
            self.progress.emit(f"Starting import of {total} items...")
            
            staging_dir_name = self.config.get("stagingFolderName", ".incoming-from-phone")
            staging_root = Path(self.config["destinationRoot"]) / staging_dir_name
            staging_root.mkdir(parents=True, exist_ok=True)
            
            for idx, item in enumerate(items, start=1):
                if self._is_aborted:
                    self.progress.emit("Import stopped by user.")
                    self.cancelled.emit()
                    return
                
                self.progress.emit(f"[{idx}/{total}] Processing: {item['media'].destination_base}")
                stage_dir = staging_root / f"task_{idx:03d}"
                stage_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy Video
                video_path = self.copy_entry(item["video"], stage_dir)
                if not video_path:
                    self.progress.emit(f"Failed to copy video for {item['media'].destination_base}. Skipping.")
                    continue
                    
                final_video = move_unique(video_path, item["destination"])
                self.progress.emit(f"Moved video to -> {final_video}")
                
                # Copy Subtitles
                for subtitle in item["subtitles"]:
                    sub_path = self.copy_entry(subtitle, stage_dir)
                    if sub_path:
                        final_sub = move_unique(sub_path, subtitle_destination(final_video, subtitle["language"], subtitle["extension"]))
                        self.progress.emit(f"Moved subtitle to -> {final_sub}")
            
            # Clean up empty staging dirs
            try:
                for child in staging_root.iterdir():
                    if child.is_dir() and not any(child.iterdir()):
                        child.rmdir()
            except Exception:
                pass

            self.progress.emit("Import complete.")
            self.finished.emit()
            
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.failed.emit(str(exc))
        finally:
            if WIN32_AVAILABLE:
                pythoncom.CoUninitialize()

    def copy_entry(self, entry: dict, stage_dir: Path) -> Path | None:
        if self._is_aborted:
            return None
        if entry["type"] == "local":
            dest = stage_dir / Path(entry["source_path"]).name
            self.progress.emit(f"Copying local file: {Path(entry['source_path']).name}")
            shutil.copy2(entry["source_path"], dest)
            return dest
            
        if not WIN32_AVAILABLE:
            return None
            
        # Extract the COM object safely within this thread
        source_item = get_mtp_item_by_path(entry["device_name"], entry["virtual_path"])
        if not source_item:
            self.progress.emit(f"Could not locate MTP file: {entry['name']}")
            return None
            
        shell = win32com.client.Dispatch("Shell.Application")
        dest_folder = shell.Namespace(str(stage_dir))
        existing_names = {item.name for item in stage_dir.iterdir()}
        
        self.progress.emit(f"Awaiting MTP transfer: {entry['name']}")
        self.progress.emit("__TRANSFER_HINT__:If Windows shows a duplicate or copy dialog, resolve it there to continue.")
        dest_folder.CopyHere(source_item, 16) # 16 = Yes to All
        
        try:
            source_size = source_item.Size
            if not isinstance(source_size, int): source_size = -1
        except Exception:
            source_size = -1
        
        return wait_for_copy_to_finish(
            stage_dir,
            source_size,
            self.progress.emit,
            entry["name"],
            existing_names=existing_names,
            should_abort=lambda: self._is_aborted,
        )
