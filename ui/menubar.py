"""
ui/menubar.py — Builds the top menubar for NW Airtrace.

Provides _build_menubar and _make_menu_btn which are mixed into ShapePlotter via app.py.
"""

import tkinter as tk
from constants import (
    MENU_BG, MENU_ACT, PANEL, TEXT, TEXT_DIM, ACCENT, SEP_CLR, FONT_UI
)

def build_menubar(app, parent=None):
    """
    Constructs the top menubar and packs it into *parent* (defaults to app).
    Each menu label opens a popup with its command list.
    """
    if parent is None:
        parent = app  # attach directly to the root window when no parent specified

    bar = tk.Frame(parent, bg=MENU_BG, height=36)  # fixed-height horizontal bar at the top of the window
    bar.pack(side=tk.TOP, fill=tk.X)               # stretches the full window width
    bar.pack_propagate(False)                       # prevents child widgets from shrinking the bar below 36px
    tk.Frame(bar, bg=SEP_CLR, height=1).place(
        relx=0, rely=1.0, relwidth=1.0, anchor="sw"
    )  # draws a 1px bottom border separating the bar from canvas content


    # Menu definitions — label mapped to list of (display name, callback) pairs
    menus = [
        ("File", [
            ("Open Image",               app._open_image),
            ("Upload Curve File",        app._upload_curve_file),
            ("─", None),
            ("Export CSV",               app._export_csv),
            ("Export for SolidWorks",    app._export_solidworks),
            ("─", None),
            ("Download Annotated Image", app._download_image),
            ("─", None),
            ("Copy Coordinates to Clipboard", app._copy_to_clipboard),
        ]),
        ("Edit", [
            ("Undo",                     app._undo_point),
            ("─", None),
            ("Rotate to 0°",             app._rotate_to_horizontal),
            ("Close Shape",              app._close_shape),
            ("─", None),
            ("Clear Image",              app._clear_image),
            ("Clear All Points",         app._clear_all),
        ]),
        ("Calibrate", [
            ("Manual Calibration",       app._start_calibration),
            ("Reset Calibration",        app._reset_calibration),
            ("─", None),
            ("Re-Run Auto Plot",         app._auto_plot),
            ("Point Density…",           app._show_density_dialog),
        ]),
        ("View", [
            ("Zoom In",                  lambda: app._zoom_step(1.2)),
            ("Zoom Out",                 lambda: app._zoom_step(1 / 1.2)),
            ("Fit to Window",            app._fit_image_to_canvas_and_render),
            ("─", None),
            ("Full Screen",              app._toggle_fullscreen),
        ]),
        ("Settings", [
            ("Open Settings…",           app._show_settings_dialog),
        ]),
    ]

    for label, items in menus:
        _make_menu_btn(app, bar, label, items)  # creates one labelled dropdown for each menu group

def _make_menu_btn(app, bar, label, items):
    """
    Creates a single menu label in *bar* that opens a popup when clicked.
    Each item in *items* is either a (label, command) pair or a separator ("─", None).
    """
    btn = tk.Label(bar, text=label, bg=MENU_BG, fg=TEXT_DIM,
                   font=(FONT_UI, 10), padx=10, cursor="hand2")  # clickable menu label in the bar
    btn.pack(side=tk.LEFT)

    popup = tk.Menu(app, tearoff=0, bg=PANEL, fg=TEXT,
                    activebackground=ACCENT, activeforeground=PANEL,
                    bd=0, relief=tk.FLAT, font=(FONT_UI, 10))  # floating dropdown menu attached to root
    for item_label, cmd in items:
        if item_label == "─":
            popup.add_separator()                                          # visual divider between groups
        else:
            popup.add_command(label="  " + item_label + "  ", command=cmd)  # padded menu item with its action

    def _show(e, b=btn, p=popup):
        b.config(bg=MENU_ACT, fg=TEXT)   # highlights the menu label while the dropdown is open
        try:
            p.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())  # positions dropdown directly below label
        finally:
            p.grab_release()             # releases grab so other widgets can respond after menu closes

    def _hide(e=None, b=btn):
        b.config(bg=MENU_BG, fg=TEXT_DIM)  # restores the label's normal colour when dropdown closes

    btn.bind("<Button-1>", _show)         # left-click opens the dropdown
    btn.bind("<Enter>", lambda e, b=btn: b.config(fg=TEXT))  # hover darkens the label text
    btn.bind("<Leave>", lambda e, b=btn: b.config(fg=TEXT_DIM) if b.cget("bg") == MENU_BG else None)  # leave restores dim text only when not active
    popup.bind("<Unmap>", _hide)          # fires _hide when the popup is dismissed
