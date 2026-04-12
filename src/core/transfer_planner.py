from pathlib import Path

from .media_parser import MediaInfo, cleanup_name, parse_media, remove_language_suffix, sanitize_segment

def build_destination(media: MediaInfo, config: dict) -> Path:
    root = Path(config.get("destinationRoot", config.get("destinationRoot", "")))
    tv_root = config.get("tvRootName", "TV Shows")
    movie_root = config.get("movieRootName", "Movies")

    if media.type == "episode":
        return root / tv_root / sanitize_segment(media.title) / f"Season {media.season:02d}" / f"{sanitize_segment(media.destination_base)}{media.extension}"
    return root / movie_root / sanitize_segment(media.destination_base) / f"{sanitize_segment(media.destination_base)}{media.extension}"

def subtitle_destination(video_path: Path, language_code: str | None, ext: str) -> Path:
    suffix = f".{language_code}" if language_code else ""
    return video_path.with_name(f"{video_path.stem}{suffix}{ext}")

def build_transfer_plan(videos, subtitles, config):
    items = []
    for video in videos:
        try:
            matched = [sub for sub in subtitles if matches(sub, video)]
            
            # Defensive destination building
            try:
                dest = build_destination(video["media"], config)
            except Exception:
                # Fallback to a flat file in the destination root
                root = Path(config.get("destinationRoot", ""))
                dest = root / f"{video['name']}{video['extension']}"

            items.append({
                "video": video,
                "subtitles": matched,
                "destination": dest,
                "media": video["media"],
            })
        except Exception:
            continue # Should not happen now with inner try
    return items

def matches(subtitle, video):
    sm = subtitle["media"]
    vm = video["media"]
    if sm.type == "episode" and vm.type == "episode":
        return sm.title == vm.title and sm.season == vm.season and sm.episode == vm.episode
    if sm.type == "movie" and vm.type == "movie":
        return sm.destination_base == vm.destination_base
    subtitle_key = strip_language_key(subtitle.get("cleaned_key", ""))
    video_key = strip_language_key(video.get("cleaned_key", ""))
    return (
        subtitle_key == video_key
        or subtitle_key.startswith(video_key)
        or video_key.startswith(subtitle_key)
        or fallback_episode_match(subtitle, video)
        or fallback_movie_match(subtitle, video)
    )

def strip_language_key(value: str) -> str:
    parts = [part for part in str(value or "").split(".") if part]
    return parts[0] if parts else str(value or "")

def fallback_episode_match(subtitle: dict, video: dict) -> bool:
    inferred_sub = infer_media_from_entry_name(subtitle)
    inferred_video = infer_media_from_entry_name(video)
    if not inferred_sub or not inferred_video:
        return False
    if inferred_sub.type != "episode" or inferred_video.type != "episode":
        return False
    return (
        inferred_sub.title == inferred_video.title
        and inferred_sub.season == inferred_video.season
        and inferred_sub.episode == inferred_video.episode
    )

def fallback_movie_match(subtitle: dict, video: dict) -> bool:
    inferred_sub = infer_media_from_entry_name(subtitle)
    inferred_video = infer_media_from_entry_name(video)
    if not inferred_sub or not inferred_video:
        return False
    if inferred_sub.type != "movie" or inferred_video.type != "movie":
        return False
    return inferred_sub.destination_base == inferred_video.destination_base

def infer_media_from_entry_name(entry: dict) -> MediaInfo | None:
    raw_candidates = []

    entry_name = str(entry.get("name") or Path(str(entry.get("source_path") or "")).name or "").strip()
    if entry_name:
        raw_candidates.append(Path(entry_name).stem)

    source_path = str(entry.get("source_path") or "").strip()
    if source_path:
        path_obj = Path(source_path)
        raw_candidates.append(path_obj.stem)
        if path_obj.parent.name:
            raw_candidates.append(f"{path_obj.parent.name} {path_obj.stem}")
        if path_obj.parent.parent and path_obj.parent.parent.name:
            raw_candidates.append(f"{path_obj.parent.parent.name} {path_obj.parent.name} {path_obj.stem}")

    virtual_path = str(entry.get("virtual_path") or "").strip()
    if virtual_path:
        parts = [part for part in virtual_path.replace("\\", "/").split("/") if part]
        if parts:
            raw_candidates.append(Path(parts[-1]).stem)
        if len(parts) >= 2:
            raw_candidates.append(f"{parts[-2]} {Path(parts[-1]).stem}")
        if len(parts) >= 3:
            raw_candidates.append(f"{parts[-3]} {parts[-2]} {Path(parts[-1]).stem}")

    seen = set()
    language = entry.get("language")
    extension = str(entry.get("extension") or ".mp4")
    for candidate in raw_candidates:
        normalized_candidate = str(candidate or "").strip()
        if not normalized_candidate or normalized_candidate in seen:
            continue
        seen.add(normalized_candidate)
        cleaned = cleanup_name(remove_language_suffix(normalized_candidate, language))
        if not cleaned:
            continue
        media = parse_media(cleaned, extension)
        if media.type == "episode":
            return media

    for candidate in raw_candidates:
        normalized_candidate = str(candidate or "").strip()
        if not normalized_candidate:
            continue
        cleaned = cleanup_name(remove_language_suffix(normalized_candidate, language))
        if not cleaned:
            continue
        return parse_media(cleaned, extension)

    return None
