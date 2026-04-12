import os
from pathlib import Path
from typing import Any

pythoncom: Any | None = None
win32com: Any | None = None
try:
    import pythoncom
    import win32com.client  # type: ignore

    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from ..core.config_manager import normalize_key
from ..core.media_parser import (
    choose_metadata_source,
    cleanup_name,
    detect_language,
    parse_media,
    remove_language_suffix,
)


def normalize_mtp_path(path_str: str) -> str:
    return "/".join(
        part.strip()
        for part in str(path_str or "").replace("\\", "/").split("/")
        if part.strip()
    )


def get_devices():
    if not WIN32_AVAILABLE:
        return []
    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        my_computer = shell.Namespace(17)
        if not my_computer:
            return []

        devices = []
        for item in my_computer.Items():
            try:
                if not item.IsFolder:
                    continue
                name = item.Name
                path = item.Path
                if not name:
                    continue
                if name.lower() in {"desktop", "documents", "local disk", "c:", "d:"}:
                    continue
                devices.append({"name": name, "id": path, "path": path})
            except Exception:
                continue
        return devices
    finally:
        pythoncom.CoUninitialize()


def get_device_root(device_ref: str):
    if not WIN32_AVAILABLE:
        return None

    shell = win32com.client.Dispatch("Shell.Application")
    if device_ref:
        try:
            namespace = shell.Namespace(str(device_ref))
            if namespace and getattr(namespace, "Self", None):
                return namespace.Self
        except Exception:
            pass

    my_computer = shell.Namespace(17)
    if not my_computer:
        return None

    ref_key = normalize_key(device_ref)
    for item in my_computer.Items():
        try:
            if not item.IsFolder:
                continue
            if item.Name == device_ref or item.Path == device_ref:
                return item
            if ref_key and normalize_key(item.Name) == ref_key:
                return item
        except Exception:
            continue
    return None


def get_mtp_subfolder(root_folder, path_str: str):
    if not path_str or not root_folder:
        return root_folder

    current = root_folder
    try:
        parts = [p.strip() for p in str(path_str).replace("\\", "/").split("/") if p.strip()]
        for part in parts:
            found = False
            items = list(current.Items())

            for item in items:
                if item.IsFolder and item.Name.lower() == part.lower():
                    current = item.GetFolder
                    found = True
                    break

            if not found and len(part) > 2:
                for item in items:
                    if not item.IsFolder:
                        continue
                    item_name = item.Name.lower()
                    part_name = part.lower()
                    if part_name in item_name or item_name in part_name:
                        current = item.GetFolder
                        found = True
                        break

            if not found:
                return None
        return current
    except Exception:
        return None


def scan_mtp(device_ref: str, config: dict, log_callback, target_paths=None, should_abort=None):
    if not WIN32_AVAILABLE:
        log_callback("pywin32 is not installed!")
        return [], []

    pythoncom.CoInitialize()
    try:
        root_item = get_device_root(device_ref)
        if not root_item:
            raise RuntimeError("Phone access is unavailable. Unlock your phone, choose File Transfer, allow file access, then reload devices.")

        root_folder = root_item.GetFolder
        device_name = root_item.Name
        try:
            root_folder.Items()
        except Exception as exc:
            raise RuntimeError(
                "MovieBox Sync can see the phone but cannot read its files yet. Unlock the device, keep it on File Transfer, and approve access on the phone."
            ) from exc

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
        extra_video_exts = {
            ".3gp",
            ".3gpp",
            ".asf",
            ".flv",
            ".mpeg",
            ".mpg",
            ".ts",
            ".webm",
            ".wmv",
        }
        all_video_exts = {ext.lower() for ext in config["videoExtensions"]} | extra_video_exts
        all_subtitle_exts = {ext.lower() for ext in config["subtitleExtensions"]}

        def _safe_shell_prop(item, attr_name: str, fallback=""):
            try:
                value = getattr(item, attr_name)
                if callable(value):
                    value = value()
                return str(value or fallback)
            except Exception:
                return str(fallback)

        def _infer_media_type(item, path_stack: list[str], allow_shell_hints: bool = False):
            raw_name = _safe_shell_prop(item, "Name")
            ext = Path(raw_name).suffix.lower()
            shell_ext = ""
            for prop_name in ("System.FileExtension", "System.ItemTypeText", "System.MIMEType", "System.KindText"):
                try:
                    value = item.ExtendedProperty(prop_name)
                except Exception:
                    value = None
                text = str(value or "").strip()
                lower_text = text.lower()
                if prop_name == "System.FileExtension" and lower_text.startswith("."):
                    shell_ext = lower_text
                elif allow_shell_hints and lower_text:
                    haystack = f"{lower_text} {_safe_shell_prop(item, 'Type').lower()} {raw_name.lower()}"
                    if any(token in haystack for token in ["subtitle", "caption", "subrip", "vtt"]):
                        return shell_ext or ext or ".srt", "subtitle"
                    if any(token in haystack for token in ["video", "media", "movie", "vlc"]):
                        return shell_ext or ext or ".mp4", "video"

            if shell_ext:
                ext = shell_ext

            if ext in all_video_exts:
                return ext, "video"
            if ext in all_subtitle_exts:
                return ext, "subtitle"

            path_lower = [p.lower() for p in path_stack]
            in_mbox = any(h in p for p in path_lower for h in ["mbox", "moviebox", "com.community"])
            in_dl_d = "d" in path_lower and ("download" in path_lower or "files" in path_lower)
            if not ext and (in_mbox or in_dl_d):
                # Guard: do not classify extensionless files as video
                # if they are inside a subtitle subfolder. MovieBox stores
                # metadata/thumbnail blobs in /d/ alongside real video files;
                # those blobs must not be treated as video entries.
                subtitle_folder_hints = [
                    "subtitle", "subtitles", "sub", "subs", "caption", "captions", "cc"
                ]
                path_joined = " ".join(p.lower() for p in path_stack)
                if any(hint in path_joined for hint in subtitle_folder_hints):
                    return ext, None
                return ".mp4", "video"

            if allow_shell_hints:
                type_text = _safe_shell_prop(item, "Type").lower()
                name_text = raw_name.lower()
                haystack = f"{type_text} {name_text}"
                if any(token in haystack for token in ["subtitle", "caption", "subrip", "vtt"]):
                    return ext or ".srt", "subtitle"
                if any(token in haystack for token in ["video", "media", "movie", "vlc"]):
                    return ext or ".mp4", "video"

            return ext, None

        def should_descend(name: str, depth: int, path_stack: list[str], forced: bool = False) -> bool:
            if depth >= (explicit_max_depth if forced else max_depth):
                return False
            lower_name = name.lower()
            if lower_name.startswith("."):
                return False
            if forced:
                return True

            app_hints = config.get("scan", {}).get("appPackageHints", [])
            stack_lower = " ".join(p.lower() for p in path_stack)
            if any(h in lower_name for h in app_hints):
                return True
            if any(h in stack_lower for h in app_hints):
                return True

            media_tokens = [
                "android",
                "data",
                "obb",
                "download",
                "downloads",
                "movies",
                "video",
                "mbox",
                "moviebox",
                "files",
                "cache",
            ]
            if prefer_android and any(token in lower_name for token in media_tokens):
                return True
            return depth < 4

        def record_entry(item, path_stack, allowed_exts: set[str] | None = None, allow_shell_hints: bool = False):
            nonlocal file_count

            ext, media_kind = _infer_media_type(item, path_stack, allow_shell_hints=allow_shell_hints)
            size = -1
            try:
                size = item.Size
            except Exception:
                pass

            if not media_kind:
                return
            if allowed_exts is not None and ext not in allowed_exts:
                return

            # Skip files that are too small to be real video content.
            # Partial downloads, temp files, and blobs from MovieBox
            # typically land under 500 KB. A real video is never that small.
            if media_kind == "video":
                try:
                    file_size = item.Size
                    if isinstance(file_size, (int, float)) and 0 < file_size < 512_000:
                        return
                except Exception:
                    pass

            file_count += 1
            if file_count % 3 == 0:
                log_callback(f"Found {file_count} media files... (Last: {item.Name})")

            stem = Path(item.Name).stem
            parent = path_stack[-1] if path_stack else ""
            grandparent = path_stack[-2] if len(path_stack) > 1 else ""
            language = detect_language(stem.split("_")[-1], config)
            metadata_source = choose_metadata_source(
                stem,
                parent,
                grandparent,
                ext in config["subtitleExtensions"],
                language,
                config,
            )
            cleaned = cleanup_name(remove_language_suffix(metadata_source, language))
            media = parse_media(cleaned, ext)
            cleaned_key = normalize_key(cleaned)
            virtual_path = "/".join(path_stack + [item.Name])

            seen_key = normalize_key(f"{device_name}/{virtual_path}")
            if seen_key in seen_paths:
                return
            seen_paths.add(seen_key)

            entry = {
                "name": item.Name,
                "virtual_path": virtual_path,
                "device_name": device_ref,
                "device_id": device_ref,
                "display_device_name": device_name,
                "extension": ext,
                "language": language,
                "media": media,
                "cleaned_key": cleaned_key,
                "type": "mtp",
                "size": size,
            }

            if media_kind == "video":
                videos.append(entry)
            else:
                subtitles.append(entry)

        def walk(folder, path_stack, depth, forced=False, allowed_exts: set[str] | None = None, allow_shell_hints: bool = False):
            nonlocal folder_count, file_count
            if folder_count >= max_folders or file_count >= max_files:
                return
            if should_abort and should_abort():
                return

            try:
                items = folder.Items()
            except Exception:
                return

            for item in items:
                if should_abort and should_abort():
                    return
                try:
                    if item.IsFolder:
                        folder_count += 1
                        if should_descend(item.Name, depth, path_stack, forced=forced):
                            full_path = "/".join(path_stack + [item.Name])
                            log_callback(f"__FOLDER__:{full_path}")
                            walk(
                                item.GetFolder,
                                path_stack + [item.Name],
                                depth + 1,
                                forced=forced,
                                allowed_exts=allowed_exts,
                                allow_shell_hints=allow_shell_hints,
                            )
                    else:
                        file_count += 1
                        ext, media_kind = _infer_media_type(item, path_stack, allow_shell_hints=allow_shell_hints)
                        if media_kind and (allowed_exts is None or ext in allowed_exts):
                            record_entry(
                                item,
                                path_stack,
                                allowed_exts=allowed_exts,
                                allow_shell_hints=allow_shell_hints,
                            )
                            log_callback(f"__FOUND__:{len(videos)}:{len(subtitles)}")

                        if file_count % 5 == 0:
                            log_callback(f"__INFO__:{folder_count}:{file_count}")
                except Exception:
                    continue

        def scan_known_sources(source_paths: list[str], allowed_exts: set[str]):
            any_found = False
            try:
                storage_units = list(root_folder.Items())
            except Exception as exc:
                log_callback(f"__WARN__:Could not list device storage: {exc}")
                return False

            for storage_item in storage_units:
                if should_abort and should_abort():
                    return any_found
                try:
                    if not storage_item.IsFolder:
                        continue
                except Exception:
                    continue

                log_callback(f"__PHASE__:1:1:Searching {storage_item.Name}...")

                for raw_path in source_paths:
                    if should_abort and should_abort():
                        return True

                    clean_rel = raw_path
                    prefixes = [
                        "Internal shared storage/",
                        "Internal shared storage\\",
                        "Phone/",
                        "Internal storage/",
                    ]
                    for prefix in prefixes:
                        clean_rel = clean_rel.replace(prefix, "")

                    normalized = normalize_mtp_path(clean_rel)
                    subfolder = get_mtp_subfolder(storage_item.GetFolder, normalized)
                    if not subfolder:
                        continue

                    any_found = True
                    log_callback(f"__PHASE__:1:1:Found MovieBox in {storage_item.Name}")
                    stack = [storage_item.Name] + [part for part in normalized.split("/") if part]
                    walk(subfolder, stack, 0, forced=True, allowed_exts=allowed_exts)

                if any_found:
                    continue

                try:
                    app_hints = config.get("scan", {}).get("appPackageHints", ["com.community.mbox.ke"])
                    top_items = list(storage_item.GetFolder.Items())
                    for item in top_items:
                        if item.IsFolder and any(h in item.Name.lower() for h in app_hints):
                            log_callback(f"__PHASE__:1:1:Found path via hint: {item.Name}")
                            walk(item.GetFolder, [storage_item.Name, item.Name], 0, forced=True)
                            any_found = True
                except Exception:
                    pass

            return any_found

        def resolve_target_folder(path_str: str):
            normalized = normalize_mtp_path(path_str)
            direct_item = get_mtp_item_by_path(device_ref, normalized)
            if direct_item:
                try:
                    if direct_item.IsFolder:
                        return direct_item.GetFolder, [part for part in normalized.split("/") if part]
                except Exception:
                    pass

            subfolder = get_mtp_subfolder(root_folder, normalized)
            if subfolder:
                return subfolder, [part for part in normalized.split("/") if part]

            try:
                storage_units = list(root_folder.Items())
            except Exception:
                storage_units = []

            for storage_item in storage_units:
                try:
                    if not storage_item.IsFolder:
                        continue
                except Exception:
                    continue

                storage_name = str(storage_item.Name or "").strip()
                variants = [normalized]
                if storage_name:
                    prefix = normalize_mtp_path(storage_name)
                    if normalized.startswith(prefix + "/"):
                        variants.append(normalized[len(prefix) + 1 :])

                for variant in variants:
                    candidate = get_mtp_subfolder(storage_item.GetFolder, variant)
                    if candidate:
                        stack = [storage_name] + [part for part in normalize_mtp_path(variant).split("/") if part]
                        return candidate, [part for part in stack if part]

            return None, [part for part in normalized.split("/") if part]

        generic_folder_names = {"download", "downloads", "moviebox", "mbox", "movies", "video", "videos"}

        def is_generic_target_path(value: str) -> bool:
            parts = [part for part in normalize_mtp_path(value).split("/") if part]
            tail = normalize_key(parts[-1]) if parts else ""
            return tail in generic_folder_names

        def expand_target_paths(paths: list[str]) -> list[str]:
            expanded = []
            seen = set()

            def add_path(value: str):
                normalized_value = normalize_mtp_path(value)
                if not normalized_value:
                    return
                key = normalize_key(normalized_value)
                if key in seen:
                    return
                seen.add(key)
                expanded.append(normalized_value)

            for value in paths:
                add_path(value)
                if not is_generic_target_path(value):
                    continue
                for source_path in config.get("videoSourcePaths", []):
                    add_path(source_path)
                for source_path in config.get("subtitleSourcePaths", []):
                    add_path(source_path)

            return expanded

        if target_paths:
            log_callback("__PHASE__:1:1:Scanning your chosen directory")
            generic_requested = any(is_generic_target_path(path) for path in target_paths)
            for raw_path in expand_target_paths(target_paths):
                if should_abort and should_abort():
                    return videos, subtitles
                normalized_path = normalize_mtp_path(raw_path)
                log_callback(f"__FOLDER__:{normalized_path}")
                subfolder, stack = resolve_target_folder(normalized_path)
                if subfolder:
                    before_videos = len(videos)
                    before_subtitles = len(subtitles)
                    walk(subfolder, stack, 0, forced=True, allowed_exts=None, allow_shell_hints=True)
                    found_here = (len(videos) - before_videos) + (len(subtitles) - before_subtitles)
                    if found_here == 0:
                        log_callback(f"__WARN__:Chosen folder resolved but no playable video files were recognized in {normalized_path}")
                else:
                    log_callback(f"__WARN__:Could not find: {normalized_path}")
            if generic_requested and not videos and not subtitles:
                log_callback("__WARN__:Chosen folder looked empty. Falling back to known MovieBox locations.")
                scan_known_sources(
                    config.get("videoSourcePaths", []),
                    set(config["videoExtensions"]),
                )
                scan_known_sources(
                    config.get("subtitleSourcePaths", []),
                    set(config["subtitleExtensions"]),
                )
        else:
            log_callback("__PHASE__:1:1:Searching for MovieBox downloads")
            found_video_root = scan_known_sources(
                config.get("videoSourcePaths", []),
                set(config["videoExtensions"]),
            )
            scan_known_sources(
                config.get("subtitleSourcePaths", []),
                set(config["subtitleExtensions"]),
            )
            if not found_video_root:
                log_callback("__WARN__:MovieBox download folders not found on this device. Try choosing the folder manually.")

        if should_abort and should_abort():
            return videos, subtitles

        log_callback(f"__DONE__:{len(videos)}:{len(subtitles)}")
        return videos, subtitles
    finally:
        pythoncom.CoUninitialize()


def get_mtp_item_by_path(device_ref: str, virtual_path: str):
    if not WIN32_AVAILABLE:
        return None

    root = get_device_root(device_ref)
    if not root:
        return None

    parts = [part for part in normalize_mtp_path(virtual_path).split("/") if part]
    if parts and (parts[0] == root.Name or parts[0] == str(device_ref)):
        parts = parts[1:]

    current_folder = root.GetFolder
    for index, part in enumerate(parts):
        is_last = index == len(parts) - 1
        found = False
        for item in current_folder.Items():
            if item.Name != part:
                continue
            if is_last:
                return item
            current_folder = item.GetFolder
            found = True
            break
        if not found:
            return None
    return root


def copy_mtp_file(device_ref, mtp_path, dest_path):
    if not WIN32_AVAILABLE:
        return False

    item = get_mtp_item_by_path(device_ref, mtp_path)
    if not item:
        return False

    try:
        shell = win32com.client.Dispatch("Shell.Application")
        dest_folder = shell.Namespace(os.path.dirname(dest_path))
        if not dest_folder:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            dest_folder = shell.Namespace(os.path.dirname(dest_path))
        dest_folder.CopyHere(item, 16)
        return True
    except Exception:
        return False
