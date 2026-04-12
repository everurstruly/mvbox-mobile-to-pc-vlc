import json
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    "destinationRoot": str(Path.home() / "Videos" / "MovieBox Library"),
    "tvRootName": "TV Shows",
    "movieRootName": "Movies",
    "stagingFolderName": ".incoming-from-phone",
    "videoSourcePaths": [
        "Internal shared storage/Android/data/com.community.mbox.ke/files/Download/d",
        "Internal shared storage/Android/data/com.community.mbox.ke/files/Download",
        "Internal shared storage/Download",
        "Internal shared storage/MovieBox",
        "Android/data/com.community.mbox.ke/files/Download/d",
        "Android/data/com.community.mbox.ke/files/Download",
        "Download",
        "MovieBox",
    ],
    "subtitleSourcePaths": [
        "Internal shared storage/Android/data/com.community.mbox.ke/files/Download/subtitle",
        "Internal shared storage/Android/data/com.community.mbox.ke/files/Download",
        "Android/data/com.community.mbox.ke/files/Download/subtitle",
        "Android/data/com.community.mbox.ke/files/Download",
    ],
    "videoExtensions": [".mp4", ".mkv", ".avi", ".mov", ".m4v"],
    "subtitleExtensions": [".srt", ".ass", ".ssa", ".sub", ".vtt"],
    "languageAliases": {
        "en": "en",
        "eng": "en",
        "english": "en",
        "es": "es",
        "spa": "es",
        "spanish": "es",
        "fr": "fr",
        "fre": "fr",
        "french": "fr",
        "ar": "ar",
        "arabic": "ar",
        "hi": "hi",
        "hindi": "hi",
    },
    "subtitleFolderPatterns": ["subtitle", "subtitles", "sub", "subs", "caption", "captions", "cc"],
    "ignoredSubtitleTokens": ["forced", "sdh", "utf8", "utf", "text"],
    "metadataHints": {
        "preferSubtitleParentFolder": True,
        "preferEpisodePattern": True,
    },
    "scan": {
        "maxDepth": 6,
        "maxFiles": 4000,
        "maxFolders": 4000,
        "preferAndroidData": True,
        "appPackageHints": ["mbox", "moviebox", "com.community.mbox.ke"],
    },
}

def normalize_ext(value: str) -> str:
    value = str(value or "").strip().lower()
    return value if value.startswith(".") else f".{value}"

def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

def normalize_config(config: dict) -> dict:
    merged = {**DEFAULT_CONFIG, **(config or {})}
    merged["destinationRoot"] = str(Path(merged["destinationRoot"]).expanduser().resolve())
    merged["videoSourcePaths"] = [str(x).strip().replace("\\", "/").strip("/") for x in merged.get("videoSourcePaths", []) if str(x).strip()]
    merged["subtitleSourcePaths"] = [str(x).strip().replace("\\", "/").strip("/") for x in merged.get("subtitleSourcePaths", []) if str(x).strip()]
    merged["videoExtensions"] = [normalize_ext(x) for x in merged.get("videoExtensions", [])]
    merged["subtitleExtensions"] = [normalize_ext(x) for x in merged.get("subtitleExtensions", [])]
    merged["languageAliases"] = {
        normalize_key(k): normalize_key(v)
        for k, v in (merged.get("languageAliases", {}) or {}).items()
        if normalize_key(k) and normalize_key(v)
    }
    merged["subtitleFolderPatterns"] = [normalize_key(x) for x in merged.get("subtitleFolderPatterns", []) if normalize_key(x)]
    merged["ignoredSubtitleTokens"] = [normalize_key(x) for x in merged.get("ignoredSubtitleTokens", []) if normalize_key(x)]
    merged["metadataHints"] = {**DEFAULT_CONFIG.get("metadataHints", {}), **(merged.get("metadataHints", {}) or {})}
    merged["scan"] = {**DEFAULT_CONFIG.get("scan", {}), **(merged.get("scan", {}) or {})}
    return merged

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return normalize_config(data)
        except Exception:
            return normalize_config(DEFAULT_CONFIG)
    return normalize_config(DEFAULT_CONFIG)

def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
