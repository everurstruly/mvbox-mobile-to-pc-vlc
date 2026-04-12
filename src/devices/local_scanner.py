import os
from pathlib import Path

from ..core.media_parser import detect_language, choose_metadata_source, parse_media, cleanup_name, remove_language_suffix
from ..core.config_manager import normalize_key

def build_local_entry(path_obj: Path, ext: str, config: dict):
    stem = path_obj.stem
    parent = path_obj.parent.name
    grandparent = path_obj.parent.parent.name if path_obj.parent.parent else ""
    language = detect_language(stem.split("_")[-1], config)
    metadata_source = choose_metadata_source(stem, parent, grandparent, ext in config["subtitleExtensions"], language, config)
    cleaned = cleanup_name(remove_language_suffix(metadata_source, language))
    media = parse_media(cleaned, ext)
    cleaned_key = normalize_key(cleaned)
    return {
        "source_path": str(path_obj),
        "extension": ext,
        "language": language,
        "media": media,
        "cleaned_key": cleaned_key,
        "type": "local",
    }

def scan_local(root: Path, config: dict, log_callback, should_abort=None):
    videos = []
    subtitles = []
    log_callback(f"Scanning local folder: {root}")
    for dirpath, _, filenames in os.walk(root):
        if should_abort and should_abort():
            log_callback("Local scan cancelled.")
            return videos, subtitles
        for name in filenames:
            if should_abort and should_abort():
                log_callback("Local scan cancelled.")
                return videos, subtitles
            ext = Path(name).suffix.lower()
            full = Path(dirpath) / name
            entry = build_local_entry(full, ext, config)
            if ext in config["videoExtensions"]:
                videos.append(entry)
            elif ext in config["subtitleExtensions"]:
                subtitles.append(entry)
    
    log_callback(f"Local scan complete. Found {len(videos)} videos and {len(subtitles)} subtitles.")
    return videos, subtitles
