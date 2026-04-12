import re
from dataclasses import dataclass
from .config_manager import normalize_key

VIDEO_PAT = re.compile(r"(.+?)[ ._-]+s(\d{1,2})[ ._-]*e(\d{1,3})(?:\b|[ ._-])", re.I)
ALT_EP_PAT = re.compile(r"(.+?)[ ._-]+(\d{1,2})x(\d{1,3})(?:\b|[ ._-])", re.I)
YEAR_PAT = re.compile(r"\b(19\d{2}|20\d{2})\b")

@dataclass
class MediaInfo:
    type: str
    title: str
    season: int | None
    episode: int | None
    year: int | None
    destination_base: str
    extension: str

def cleanup_name(value: str) -> str:
    value = re.sub(r"\b(480p|720p|1080p|2160p|4k)\b", " ", value, flags=re.I)
    value = re.sub(r"\b(x264|x265|h264|h265|hevc|hdr|webrip|webdl|web-dl|bluray|brrip|dvdrip)\b", " ", value, flags=re.I)
    value = re.sub(r"\b(aac2?\.?0|aac|dts|ac3|eac3|ddp5?\.?1|atmos)\b", " ", value, flags=re.I)
    value = re.sub(r"\[[^\]]+\]", " ", value)
    value = re.sub(r"[._]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value

def cleanup_title(value: str) -> str:
    value = re.sub(r"[._]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    parts = [p.capitalize() for p in value.split(" ") if p]
    title = " ".join(parts).strip()
    return sanitize_segment(title) or "Unknown"

def sanitize_segment(value: str) -> str:
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"[. ]+$", "", value)
    return value

def parse_media(name: str, extension: str) -> MediaInfo:
    match = VIDEO_PAT.search(name) or ALT_EP_PAT.search(name)
    if match:
        title = cleanup_title(match.group(1))
        season = int(match.group(2))
        episode = int(match.group(3))
        destination_base = f"{title} - S{season:02d}E{episode:02d}"
        return MediaInfo("episode", title, season, episode, None, destination_base, extension)

    year_match = YEAR_PAT.search(name)
    raw_title = name[: year_match.start()].strip() if year_match else name.strip()
    title = cleanup_title(raw_title)
    year = int(year_match.group(1)) if year_match else None
    destination_base = f"{title} ({year})" if year else title
    return MediaInfo("movie", title, None, None, year, destination_base, extension)

def detect_language(token: str, config: dict) -> str | None:
    token = normalize_key(token)
    if not token:
        return None
    return config["languageAliases"].get(token)

def remove_language_suffix(stem: str, token: str | None) -> str:
    if not token:
        return stem
    return re.sub(rf"[ ._-]+{re.escape(token)}$", "", stem, flags=re.I)

def is_subtitle_tree(path_str: str, config: dict) -> bool:
    normalized = normalize_key(path_str)
    return any(pattern in normalized for pattern in config["subtitleFolderPatterns"])

def is_generic_subtitle_token(normalized: str, config: dict) -> bool:
    return (
        normalized in config["subtitleFolderPatterns"]
        or normalized in config["ignoredSubtitleTokens"]
        or normalized in config["languageAliases"]
    )

def choose_metadata_source(stem: str, parent: str, grandparent: str, is_subtitle: bool, language_token: str | None, config: dict) -> str:
    inside_subtree = is_subtitle_tree(parent, config) or is_subtitle_tree(grandparent, config)
    if is_subtitle:
        candidates = [parent, grandparent, stem] if inside_subtree else [stem, parent, grandparent]
    else:
        candidates = [stem, parent, grandparent]

    # Detect hash-like filenames (MovieBox stores files as UUID/hex in the /d/ subfolder)
    stem_looks_like_hash = bool(re.match(r'^[a-f0-9]{8,}$', stem, re.I)) or (len(stem) > 12 and re.match(r'^[a-zA-Z0-9]+$', stem) and ' ' not in stem and '.' not in stem)

    best = stem
    best_score = -1
    for candidate in [c for c in candidates if c]:
        cleaned = cleanup_name(remove_language_suffix(candidate, language_token))
        if not cleaned:
            continue
        media = parse_media(cleaned, ".")
        normalized = normalize_key(cleaned)
        score = 0
        if media.type == "episode":
            score += 100 if config["metadataHints"].get("preferEpisodePattern", True) else 70
        else:
            score += 60 if media.year else 30
            if len(cleaned.split()) >= 2:
                score += 10
        if inside_subtree and candidate == parent and config["metadataHints"].get("preferSubtitleParentFolder", True):
            score += 25
        if candidate == stem:
            score += 3  # slight preference for stem, but less than before
        if candidate == grandparent:
            score += 8  # prefer grandparent for context-rich names
        if is_generic_subtitle_token(normalized, config):
            score -= 80
        if len(normalized) <= 1:
            score -= 60  # single-char folders like 'd' are useless
        elif len(normalized) <= 3:
            score -= 20
        # Heavy penalty if this is the hash-like stem
        if candidate == stem and stem_looks_like_hash:
            score -= 150
        if score > best_score:
            best_score = score
            best = candidate
    return best
