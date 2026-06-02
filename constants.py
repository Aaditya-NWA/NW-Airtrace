"""
constants.py — Colour palette, typography, and platform font detection for NW AirTrace.
All UI colour and font values live here so every module imports from one source.
"""

import platform

# Canvas and surface colours
BG        = "#F0F2F8"      # main canvas background fill
PANEL     = "#FFFFFF"      # toolbar and card surface colour
SIDEBAR   = "#1E1F26"      # dark sidebar background (Figma-style)
SIDEBAR2  = "#2A2B35"      # sidebar secondary surface used for hover and inset rows
ACCENT    = "#6366F1"      # indigo — primary action colour (buttons, mode pill, dots)
ACCENT_LT = "#EEF2FF"      # indigo tint used for light info badges
ACCENT2   = "#F43F5E"      # rose — destructive actions and calibration markers
GREEN     = "#10B981"      # emerald — success state, insert hint dot, nudge ring
YELLOW    = "#F59E0B"      # amber — hover highlight and warning state
PURPLE    = "#8B5CF6"      # violet — secondary info labels (SolidWorks status)
TEXT      = "#1E1F26"      # near-black body text on light backgrounds
TEXT_DIM  = "#9CA3AF"      # muted label colour for secondary info
TEXT_SIDE = "#E8E9F0"      # sidebar text on dark background
TEXT_SIDE_DIM = "#6B7280"  # sidebar muted / secondary text on dark background

# Canvas drawing colours
DOT_CLR   = "#6366F1"      # normal plotted point fill
DOT_HOVER = "#F59E0B"      # point colour when the cursor is hovering over it
CAL_CLR   = "#F43F5E"      # calibration marker ring and label colour
GRID_CLR  = "#E2E5F0"      # canvas background grid line colour
LINE_CLR  = "#6366F1"      # curve line connecting all plotted points

# Menubar and layout colours
MENU_BG   = "#FFFFFF"      # top menubar background
MENU_ACT  = "#F3F4F6"      # menubar item hover state background
SEP_CLR   = "#E5E7EB"      # light separator line on panel backgrounds
SEP_DARK  = "#2E2F3A"      # dark separator line on sidebar background
CARD_BG   = "#F9FAFB"      # light card surface used inside dialogs
TRAY_BG   = "#1A1B24"      # floating toolbar tray background (reserved)

# Typography — resolved once at import based on the host operating system
_os = platform.system()
if _os == "Windows":
    FONT_UI   = "Segoe UI"    # system UI font on Windows
    FONT_MONO = "Consolas"    # monospace font for coordinate values on Windows
elif _os == "Darwin":
    FONT_UI   = "SF Pro Display"  # system UI font on macOS
    FONT_MONO = "Menlo"           # monospace font for coordinate values on macOS
else:
    FONT_UI   = "DejaVu Sans"          # fallback UI font on Linux / other
    FONT_MONO = "DejaVu Sans Mono"     # fallback monospace font on Linux / other
