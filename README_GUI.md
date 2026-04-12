# MovieBox GUI Importer (Python)

This GUI scans your phone from the root, auto-discovers likely MovieBox folders, and imports videos + subtitles into a VLC-friendly library on your PC.

## Install

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python app.py
```

## How it works

- `Scan Phone` uses Windows shell/MTP to crawl the phone storage starting at the device root.
- It scores likely MovieBox folders by video files, subtitle folders, and episode-like names.
- It builds a preview and imports into your configured PC library.

## Config

Edit `moviebox-gui.config.json` to customize:
- `destinationRoot`
- `subtitleExtensions`
- `languageAliases`
- `subtitleFolderPatterns`
- `scan.maxDepth`, `scan.maxFiles`, `scan.maxFolders`

If MovieBox changes again, you should only need to edit this config, not the code.