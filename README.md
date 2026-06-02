# NW Airtrace — Airfoil Coordinate Plotter

A desktop application for digitising airfoil coordinates from images and exporting them to CSV or SolidWorks-ready XYZ curve files.

**NW Aerospace · Internal Use · v1 Beta**

---

## Requirements

- Python 3.10 or later
- Tkinter (included in the standard Python installer on Windows and macOS; on Linux install `python3-tk`)

---

## Installation

```bash
# 1. Clone or extract the project
cd NW Airtrace

# 2. (Recommended) Create a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

> `scipy` is used for the SolidWorks spline resampler. The app runs without it but falls back to linear interpolation for that feature.

---

## Running

```bash
python main.py
```

---

## Project Structure

```
NW Airtrace/
├── main.py             Entry point — creates and runs ShapePlotter
├── app.py              ShapePlotter class, __init__, _build_ui, state variables
├── constants.py        Colour palette, font constants, platform font detection
├── requirements.txt    Python package dependencies
├── ui/
│   ├── menubar.py      Top menubar (File / Edit / Calibrate / View / Settings)
│   ├── sidebar.py      Collapsible sidebar, zoom slider, coordinates table
│   └── dialogs.py      Density, settings, calibration, and SolidWorks export dialogs
├── core/
│   ├── calibration.py  Auto/manual calibration and coordinate transform methods
│   ├── autoplot.py     Automatic airfoil contour detection and point placement
│   ├── export.py       CSV, SolidWorks export, spline resampler, clipboard, file upload
│   └── canvas.py       Drawing, event handling, zoom, pan, undo, nudge, selection
└── assets/             Static assets (icons, images)
```

---

## Building a Desktop Application

The steps below produce a single self-contained executable using **PyInstaller**. Follow them in order.

### Step 1 — Install PyInstaller into your virtual environment

```bash
pip install pyinstaller
```

### Step 2 — Run PyInstaller

From inside the `NW Airtrace/` directory:

**Windows**
```bash
pyinstaller --onefile --windowed --name "NW Airtrace" --icon assets/iconNW.png main.py
```

**macOS**
```bash
pyinstaller --onefile --windowed --name "NW Airtrace" --icon assets/iconNW.png main.py
```

**Linux**
```bash
pyinstaller --onefile --name "NW Airtrace" main.py
```

Flag explanations:

| Flag | Purpose |
|---|---|
| `--onefile` | Bundles everything into a single executable |
| `--windowed` | Suppresses the terminal window on launch (Windows / macOS) |
| `--name` | Sets the output executable name |
| `--icon` | Sets the application icon (remove if you have no icon file yet) |

### Step 3 — Find your executable

PyInstaller writes output into two folders it creates:

```
NW Airtrace/
├── build/      ← intermediate build artefacts (can be deleted)
└── dist/
    └── NW Airtrace      ← your final executable (or NW Airtrace.exe on Windows)
```

The file inside `dist/` is fully self-contained and can be distributed without Python installed.

### Step 4 — Test before distributing

Run the executable directly from `dist/` on a clean machine (or a machine where Python is not installed) to confirm everything works end-to-end before sharing.

### Step 5 (macOS only) — Code signing

macOS will block unsigned executables downloaded from the internet. To allow users to open it without a warning, either:

- Right-click → Open the first time (bypasses Gatekeeper for the user), or
- Sign it with an Apple Developer certificate:

```bash
codesign --deep --force --sign "Developer ID Application: Your Name (TEAMID)" dist/NW Airtrace.app
```

### Troubleshooting common PyInstaller issues

**Hidden imports** — if the app crashes at launch with an `ImportError`, add the missing module explicitly:

```bash
pyinstaller --onefile --windowed --hidden-import=scipy.interpolate --name "NW Airtrace" main.py
```

**`cv2` not found** — OpenCV sometimes needs an explicit hidden import:

```bash
--hidden-import=cv2
```

**Large executable size** — `--onefile` is convenient but slow to start because it unpacks on each launch. Use `--onedir` instead for faster startup; it produces a folder rather than a single file.

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Left-click canvas | Place a point |
| Right-click point | Delete that point |
| Hover line segment | Shows green `+` — click to insert point there |
| Arrow keys | Nudge selected point 1 px |
| Shift + Arrow | Nudge selected point 10 px |
| Ctrl + Z | Undo |
| Ctrl + A | Select all table rows |
| Escape | Deselect all |
| Delete / Backspace | Remove hovered or last point |
| Scroll wheel | Zoom toward cursor |
| F11 | Toggle fullscreen |

---

## License

NW Aerospace · Internal Use Only
