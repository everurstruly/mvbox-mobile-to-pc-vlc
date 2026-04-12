# 🎬 MovieBox Sync

A premium desktop tool designed to seamlessly bridge your mobile media library with your PC's VLC core. MovieBox Sync automatically discovers, scores, and imports your videos and subtitles from your phone storage into a beautifully organized, VLC-ready environment.

![Header Image](https://raw.githubusercontent.com/everurstruly/mvbox-mobile-to-pc-vlc/main/assets/banner.png) *(Placeholder)*

---

## ✨ Features

- **Intuitive Discovery**: Automatically crawls phone storage via MTP to find hidden MovieBox-style media directories.
- **Intelligent Scoring**: Ranks folders based on video files, subtitle presence, and episode numbering patterns.
- **Obsidian Lens UI**: A high-end, minimalist interface built with mathematical precision and typography-first design.
- **VLC-Friendly Libraries**: Automatically organizes imports for maximum compatibility with VLC and other desktop media players.
- **Advanced Configuration**: Fine-tune scanning depth, folder patterns, and language aliases via a simple JSON config.

## 🚀 Getting Started

### Prerequisites

- **Windows 10/11** (Recommended)
- **Python 3.10+**
- USB cable for device connectivity

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/everurstruly/mvbox-mobile-to-pc-vlc.git
   cd moviebox-usb-sync
   ```

2. **Set up a virtual environment** (Optional but recommended)
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

3. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

### Running the App

```powershell
python app.py
```

## 🛠️ Configuration

MovieBox Sync is highly customizable via the `config.json` file. You can define:
- `destinationRoot`: Where your media should be synced on your PC.
- `scan`: Limits for depth, file count, and folder count to optimize performance.
- `subtitleFolderPatterns`: Custom directory names where your app looks for subtitles.

## 🤝 Contributing

We welcome contributions! If you'd like to improve the UI or add device-specific scan patterns, feel free to fork and submit a PR. 

## ⚖️ License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Crafted for users who value simplicity and design.*
