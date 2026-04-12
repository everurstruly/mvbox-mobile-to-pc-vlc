from pathlib import Path
from .media_parser import MediaInfo, sanitize_segment

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
    )

def strip_language_key(value: str) -> str:
    parts = [part for part in str(value or "").split(".") if part]
    return parts[0] if parts else str(value or "")
