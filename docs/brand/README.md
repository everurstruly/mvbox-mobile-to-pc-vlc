# MovieBox Sync Branding Guide

This guide provides technical and design specifications for the "MovieBox Sync" brand identity, also known as the **Obsidian Lens** aesthetic.

---

## 🎨 Brand Identity: The Obsidian Lens

The MovieBox Sync brand is built on a minimalist, premium, and high-precision aesthetic. It draws inspiration from modern glassmorphism and the dark-mode environments of technical editing tools.

### Visual Values
- **Mathematical Precision**: Use of strict geometric scaling and even margins.
- **Obsidians & Glass**: Deep black backgrounds with subtle translucent overlays.
- **Neon Accents**: High-contrast blue for primary calls to action and active states.

---

## 💎 Visual Assets

All branding assets are located in [src/ui/assets/](file:///c:/Users/oGHENETEFA/Documents/Workspace-Maintain/moviebox-usb-sync/src/ui/assets/).

### 1. Primary Logo (`logo.png`)
- **Format**: PNG (Transparent)
- **Resolution**: 512x512px
- **Usage**: Used for UI splash screens and high-resolution marketing materials.
- **Location**: `src/ui/assets/logo.png`

### 2. Windows Icon (`logo.ico`)
- **Format**: ICO (Multi-resolution bundle)
- **Sizes**: 16, 32, 48, 64, 128, 256px.
- **Usage**: Hardcoded into the `.exe` binary and the application title bar.
- **Location**: `src/ui/assets/logo.ico`

---

## 🌈 Design System

### Color Palette
| Element | Hex Code | Purpose |
| :--- | :--- | :--- |
| **Obsidian Deep** | `#020202` | Main Background |
| **Obsidain Blue** | `#050818` | Gradient start point |
| **Action Blue** | `#007AFF` | Buttons, Active states, Neon glows |
| **Glass White** | `rgba(255, 255, 255, 0.05)` | Surface cards and borders |
| **Text Primary** | `#FFFFFF` | Main headings and labels |
| **Text Secondary**| `rgba(255, 255, 255, 0.4)`| Subtexts and hints |

### Typography
- **Primary Font**: `Inter` (Sans-serif)
- **Fallback**: `Segoe UI Variable`
- **Technical UI**: `Consolas` (Monospace, used for scanning logs)

---

## 🛠️ Technical Maintenance

### 1. Setting the App Icon
In Windows, simply setting the icon on the window is not enough for correct taskbar grouping. We use the `AppUserModelID` to tell Windows this is a distinct application.

**File**: [src/ui/main_window.py](file:///c:/Users/oGHENETEFA/Documents/Workspace-Maintain/moviebox-usb-sync/src/ui/main_window.py)
```python
import ctypes
# Fix taskbar icon grouping
myappid = u'moviebox.sync.desktop.v2'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# Set window icon
self.setWindowIcon(QtGui.QIcon("src/ui/assets/logo.ico"))
```

### 2. Updating Assets
If the brand logo needs to be updated:
1. Replace `src/ui/assets/logo.png`.
2. Generate a new `.ico` file. You can use the following snippet if `Pillow` is installed:
   ```python
   from PIL import Image
   img = Image.open('src/ui/assets/logo.png')
   img.save('src/ui/assets/logo.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (256,256)])
   ```
3. Run the universal build script: `powershell .\scripts\build_all.ps1`.

### 3. Build & Distribution
When distributing the application, the branding is baked into the executable. 
- The [moviebox_sync.spec](file:///c:/Users/oGHENETEFA/Documents/Workspace-Maintain/moviebox-usb-sync/moviebox_sync.spec) file includes the `icon=` parameter which sets the file icon in Windows Explorer.
- The [moviebox_sync_installer.iss](file:///c:/Users/oGHENETEFA/Documents/Workspace-Maintain/moviebox-usb-sync/moviebox_sync_installer.iss) file defines the identity for the installation wizard.

---

## ⚡ Design Principles for Stakeholders
- **Avoid Boxes**: Try to use subtle gradients or simple dividers instead of heavy borders.
- **Typography First**: Hierarchy is established through font weight (800 for titles) rather than just size.
- **Glassmorphism**: When adding new UI sections, use `rgba` background colors with a low alpha (0.03 to 0.08) to maintain the "glass" look over the obsidian gradient.
