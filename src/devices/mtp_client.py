import os
from pathlib import Path
try:
    import win32com.client  # type: ignore
    import pythoncom
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from ..core.media_parser import detect_language, choose_metadata_source, parse_media, cleanup_name, remove_language_suffix
from ..core.config_manager import normalize_key

def normalize_mtp_path(path_str: str) -> str:
    return "/".join(part.strip() for part in str(path_str or "").replace("\\", "/").split("/") if part.strip())

def get_devices():
    if not WIN32_AVAILABLE:
        return []
    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        my_computer = shell.Namespace(17) # 17 is My Computer
        if not my_computer:
            return []
        
        devices = []
        for item in my_computer.Items():
            if item.IsFolder:
                name = item.Name
                if name and name.lower() not in {"desktop", "documents", "local disk", "c:", "d:"}:
                    devices.append({"name": name, "path": item.Path})
        return devices
    finally:
        pythoncom.CoUninitialize()

def get_device_root(device_name: str):
    if not WIN32_AVAILABLE: return None
    shell = win32com.client.Dispatch("Shell.Application")
    my_computer = shell.Namespace(17)
    for item in my_computer.Items():
        if item.Name == device_name:
            return item
    return None

def get_mtp_subfolder(root_folder, path_str: str):
    if not path_str or not root_folder:
        return root_folder
    current = root_folder
    try:
        parts = [p.strip() for p in path_str.replace("\\", "/").split("/") if p.strip()]
        for i, part in enumerate(parts):
            items = list(current.Items())
            found = False
            
            # 1. Try Exact Match (Case Insensitive)
            for item in items:
                if item.IsFolder and item.Name.lower() == part.lower():
                    current = item.GetFolder
                    found = True
                    break
            
            # 2. Try Fuzzy Match (only for long names to avoid matching 'd' with 'Android')
            if not found and len(part) > 2:
                for item in items:
                    if item.IsFolder and (part.lower() in item.Name.lower() or item.Name.lower() in part.lower()):
                        current = item.GetFolder
                        found = True
                        break
            
            if not found:
                return None
        return current
    except Exception:
        return None

def scan_mtp(device_name: str, config: dict, log_callback, target_paths: list = None, should_abort=None):
    if not WIN32_AVAILABLE:
        log_callback("pywin32 is not installed!")
        return [], []
        
    pythoncom.CoInitialize()
    try:
        root_item = get_device_root(device_name)
        if not root_item:
            log_callback(f"Could not find device: {device_name}")
            return [], []

        root_folder = root_item.GetFolder

        videos = []
        subtitles = []
        folder_count = 0
        file_count = 0
        
        max_depth = config.get("scan", {}).get("maxDepth", 6)
        explicit_max_depth = max(max_depth, 12)
        max_files = config.get("scan", {}).get("maxFiles", 4000)
        max_folders = config.get("scan", {}).get("maxFolders", 4000)
        prefer_android = config.get("scan", {}).get("preferAndroidData", True)
        seen_paths = set()

        def should_descend(name: str, depth: int, path_stack: list[str], forced: bool = False) -> bool:
            if depth >= (explicit_max_depth if forced else max_depth):
                return False
            lower_name = name.lower()
            if lower_name.startswith('.'):
                return False
            if forced:
                return True
            app_hints = config.get("scan", {}).get("appPackageHints", [])
            stack_lower = " ".join(p.lower() for p in path_stack)
            # Descend into this folder if its name matches a known app package
            if any(h in lower_name for h in app_hints):
                return True
            # Already inside a known MovieBox app folder — keep descending
            if any(h in stack_lower for h in app_hints):
                return True
            # Follow standard Android/media folder names
            media_tokens = ["android", "data", "obb", "download", "downloads",
                            "movies", "video", "mbox", "moviebox", "files", "cache"]
            if prefer_android and any(token in lower_name for token in media_tokens):
                return True
            return depth < 4

        def record_entry(item, path_stack, allowed_exts: set[str] | None = None):
            nonlocal file_count
            ext = Path(item.Name).suffix.lower()
            size = -1
            try: size = item.Size
            except Exception: pass

            all_supported = set(config["videoExtensions"]) | set(config["subtitleExtensions"])
            
            # Extension check
            is_supported = ext in all_supported
            
            # Special case for MovieBox extensionless files
            # MovieBox stores videos as hash-named files with NO extension inside a folder called 'd'
            if not is_supported and not ext:
                path_lower = [p.lower() for p in path_stack]
                in_mbox = any(h in p for p in path_lower for h in ["mbox", "moviebox", "com.community"])
                in_dl_d = "d" in path_lower and ("download" in path_lower or "files" in path_lower)
                if in_mbox or in_dl_d:
                    # Accept: large extensionless file in MovieBox territory
                    is_supported = True
                    ext = ".mp4"  # Treat as mp4 for grouping


            if not is_supported:
                return
            if allowed_exts is not None and ext not in allowed_exts:
                return

            file_count += 1
            if file_count % 3 == 0:
                log_callback(f"Found {file_count} media files... (Last: {item.Name})")

            stem = Path(item.Name).stem
            parent = path_stack[-1] if path_stack else ""
            grandparent = path_stack[-2] if len(path_stack) > 1 else ""

            language = detect_language(stem.split("_")[-1], config)
            metadata_source = choose_metadata_source(stem, parent, grandparent, ext in config["subtitleExtensions"], language, config)
            cleaned = cleanup_name(remove_language_suffix(metadata_source, language))
            media = parse_media(cleaned, ext)
            cleaned_key = normalize_key(cleaned)

            virtual_path = "\\".join([device_name] + path_stack + [item.Name])
            if virtual_path in seen_paths:
                return
            seen_paths.add(virtual_path)

            entry = {
                "name": item.Name,
                "virtual_path": virtual_path,
                "device_name": device_name,
                "extension": ext,
                "language": language,
                "media": media,
                "cleaned_key": cleaned_key,
                "type": "mtp",
            }

            if ext in config["videoExtensions"] or (not Path(item.Name).suffix and is_supported):
                videos.append(entry)
            else:
                subtitles.append(entry)

        def walk(folder, path_stack, depth, forced=False, allowed_exts: set[str] | None = None):
            nonlocal folder_count, file_count
            if folder_count >= max_folders or file_count >= max_files:
                return
            if should_abort and should_abort():
                return
            try: items = folder.Items()
            except Exception: return

            for item in items:
                if should_abort and should_abort():
                    return
                try:
                    if item.IsFolder:
                        folder_count += 1
                        if should_descend(item.Name, depth, path_stack, forced=forced):
                            full_path = "/".join(path_stack + [item.Name])
                            log_callback(f"__FOLDER__:{full_path}")
                            walk(item.GetFolder, path_stack + [item.Name], depth + 1, forced=forced, allowed_exts=allowed_exts)
                    else:
                        # Record every file encounter for UI feedback
                        file_count += 1
                        is_vid = any(item.Name.lower().endswith(e) for e in config["videoExtensions"])
                        is_sub = any(item.Name.lower().endswith(e) for e in config["subtitleExtensions"])
                        has_no_ext = not Path(item.Name).suffix
                        path_lower = [p.lower() for p in path_stack]
                        in_mbox = any(h in p for p in path_lower for h in ["mbox", "moviebox", "com.community"])
                        in_dl_d = "d" in path_lower and ("download" in path_lower or "files" in path_lower)
                        is_extensionless_mbox_file = has_no_ext and (in_mbox or in_dl_d)

                        if is_vid or is_sub or is_extensionless_mbox_file:
                            record_entry(item, path_stack, allowed_exts=allowed_exts)
                            log_callback(f"__FOUND__:{len(videos)}:{len(subtitles)}")
                        
                        # Emit regular info heartbeats
                        if file_count % 5 == 0:
                            log_callback(f"__INFO__:{folder_count}:{file_count}")
                except Exception:
                    continue

        def scan_known_sources(source_paths: list[str], label: str, allowed_exts: set[str]):
            any_found = False
            try: storage_units = list(root_folder.Items())
            except Exception as e: 
                log_callback(f"__WARN__:Could not list device storage: {e}")
                return False

            for storage_item in storage_units:
                if not storage_item.IsFolder: continue
                log_callback(f"__PHASE__:1:1:Searching {storage_item.Name}...")
                
                # Check for the app-specific path
                for raw_path in source_paths:
                    if should_abort and should_abort(): return True
                    
                    # Normalize: strip common storage prefixes if they somehow ended up here
                    clean_rel = raw_path
                    prefixes = ["Internal shared storage/", "Internal shared storage\\", "Phone/", "Internal storage/"]
                    for p in prefixes: clean_rel = clean_rel.replace(p, "")
                    
                    normalized = normalize_mtp_path(clean_rel)
                    subfolder = get_mtp_subfolder(storage_item.GetFolder, normalized)
                    
                    if subfolder:
                        any_found = True
                        log_callback(f"__PHASE__:1:1:Found MovieBox in {storage_item.Name}")
                        stack = [storage_item.Name] + [part for part in normalized.split("/") if part]
                        walk(subfolder, stack, 0, forced=True, allowed_exts=allowed_exts)
                
                # BRUTE FORCE FALLBACK: If path walk failed, search top-level for hint folders
                if not any_found:
                    try:
                        app_hints = config.get("scan", {}).get("appPackageHints", ["com.community.mbox.ke"])
                        top_items = list(storage_item.GetFolder.Items())
                        for item in top_items:
                            if item.IsFolder and any(h in item.Name.lower() for h in app_hints):
                                log_callback(f"__PHASE__:1:1:Found path via hint: {item.Name}")
                                walk(item.GetFolder, [storage_item.Name, item.Name], 0, forced=True)
                                any_found = True
                    except Exception: pass

            return any_found

        if target_paths:
            log_callback("__PHASE__:1:1:Scanning your chosen directory")
            for p in target_paths:
                if should_abort and should_abort():
                    return videos, subtitles
                normalized_path = normalize_mtp_path(p)
                log_callback(f"__FOLDER__:{normalized_path}")
                subfolder = get_mtp_subfolder(root_folder, normalized_path)
                if subfolder:
                    stack = [part for part in normalized_path.split('/') if part]
                    walk(subfolder, stack, 0, forced=True, allowed_exts=None)
                else:
                    log_callback(f"__WARN__:Could not find: {normalized_path}")
        else:
            log_callback("__PHASE__:1:1:Searching for MovieBox downloads")
            found_video_root = scan_known_sources(config.get("videoSourcePaths", []), "video", set(config["videoExtensions"]))
            scan_known_sources(config.get("subtitleSourcePaths", []), "subtitle", set(config["subtitleExtensions"]))
            if not found_video_root:
                log_callback("__WARN__:MovieBox download folders not found on this device. Try choosing the folder manually.")
        if should_abort and should_abort():
            return videos, subtitles
        log_callback(f"__DONE__:{len(videos)}:{len(subtitles)}")
        return videos, subtitles
    finally:
        pythoncom.CoUninitialize()

def get_mtp_item_by_path(device_name: str, virtual_path: str):
    root = get_device_root(device_name)
    if not root: return None
    
    parts = virtual_path.split("\\")
    if parts[0] == device_name: parts = parts[1:]
    
    current_folder = root.GetFolder
    for i, part in enumerate(parts):
        is_last = (i == len(parts) - 1)
        found = False
        for item in current_folder.Items():
            if item.Name == part:
                if is_last: return item
                else:
                    current_folder = item.GetFolder
                    found = True
                    break
        if not found: return None
    return None
