"""
ui/sidebar.py — Builds the collapsible left sidebar for NW Airtrace.

Contains the canvas controls section, zoom slider, coordinates table,
copy button, calibration status row, and sidebar toggle logic.
Called once from ShapePlotter._build_ui via build_sidebar(app).

Logo loading: loaded from assets/iconNW.png relative to the package root.
The loader scales it to 28×28 and falls back to the ✈ text badge
if the file is missing or cannot be read.
"""

import os
import tkinter as tk
from tkinter import ttk

from constants import (
    SIDEBAR, SIDEBAR2, ACCENT, ACCENT2, GREEN, YELLOW, PURPLE,
    PANEL, TEXT_SIDE, TEXT_SIDE_DIM, SEP_DARK, FONT_UI, FONT_MONO
)

# Resolve the assets directory relative to this file so paths survive PyInstaller packaging
_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_LOGO_PATH  = os.path.join(_ASSETS_DIR, "iconNW.png")  # logo image used in the sidebar header badge


def _load_logo(size=28):
    """
    Attempts to load assets/logo.png and return a Tkinter PhotoImage scaled to *size*×*size*.
    Returns None if the file is missing or Pillow cannot open it, so the caller
    can fall back to the text badge without crashing.
    """
    if not os.path.isfile(_LOGO_PATH):
        return None  # logo file not present yet — caller will use the text fallback
    try:
        from PIL import Image, ImageTk
        img = Image.open(_LOGO_PATH).convert("RGBA")  # converts to RGBA so transparency is preserved
        img = img.resize((size, size), Image.LANCZOS)  # scales to exact badge size with high-quality resampling
        return ImageTk.PhotoImage(img)  # wraps in a Tkinter-compatible image object
    except Exception:
        return None  # silently falls back if Pillow fails for any reason (corrupt file, wrong format, etc.)


def build_sidebar(app):
    """
    Creates the full sidebar (collapsible) and the collapsed stub strip.
    Wires up the toggle button, scrollable inner frame, all sections,
    and stores widget references on *app* so other modules can update them.
    """
    app._sidebar_visible = True  # tracks whether the full sidebar is currently shown

    # Collapsed stub: 36px strip that stays visible when sidebar is hidden
    app._sidebar_stub = tk.Frame(app, bg=SIDEBAR, width=36)   # narrow strip replacing the sidebar when collapsed
    app._sidebar_stub.pack(side=tk.LEFT, fill=tk.Y)
    app._sidebar_stub.pack_propagate(False)
    app._stub_expand_btn = tk.Label(
        app._sidebar_stub, text="›",
        bg=SIDEBAR, fg=TEXT_SIDE_DIM, font=(FONT_UI, 16), cursor="hand2"
    )  # arrow button in the stub that expands the sidebar again
    app._stub_expand_btn.place(relx=0.5, rely=0.07, anchor=tk.CENTER)
    app._stub_expand_btn.bind("<Button-1>", lambda e: toggle_sidebar(app))
    app._sidebar_stub.pack_forget()  # hidden on launch because the full sidebar is open

    # Full sidebar outer frame
    app._sidebar_outer = tk.Frame(app, bg=SIDEBAR, width=268)   # fixed-width dark panel on the left
    app._sidebar_outer.pack(side=tk.LEFT, fill=tk.Y)
    app._sidebar_outer.pack_propagate(False)

    # Scrollable canvas inside the outer frame allows the sidebar to scroll
    _sc = tk.Canvas(app._sidebar_outer, bg=SIDEBAR, highlightthickness=0, width=250)
    _sc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Custom scrollbar style matching the dark sidebar theme
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(
        "Sidebar.Vertical.TScrollbar",
        background=SIDEBAR2, troughcolor=SIDEBAR,
        bordercolor=SIDEBAR, arrowcolor=TEXT_SIDE_DIM,
        relief="flat", width=3
    )  # thin dark scrollbar that blends into the sidebar background
    _ssb = ttk.Scrollbar(
        app._sidebar_outer, orient=tk.VERTICAL,
        command=_sc.yview, style="Sidebar.Vertical.TScrollbar"
    )  # vertical scrollbar for the sidebar content area
    _ssb.pack(side=tk.RIGHT, fill=tk.Y)
    _sc.configure(yscrollcommand=_ssb.set)

    app.left = tk.Frame(_sc, bg=SIDEBAR)       # inner content frame that holds all sidebar sections
    _win = _sc.create_window((0, 0), window=app.left, anchor=tk.NW)

    def _cfg_w(e): _sc.itemconfig(_win, width=e.width)   # keeps inner frame width in sync with scrollable canvas
    def _cfg_h(e): _sc.configure(scrollregion=_sc.bbox("all"))  # updates scroll region when content height changes
    _sc.bind("<Configure>", _cfg_w)
    app.left.bind("<Configure>", _cfg_h)

    def _scroll(e):
        d = int(-1 * (e.delta / 120)) if e.delta else (-1 if e.num == 4 else 1)
        _sc.yview_scroll(d, "units")  # converts mouse-wheel delta to sidebar scroll units
    for w in (_sc, app.left):
        w.bind("<MouseWheel>", _scroll)   # Windows / macOS scroll
        w.bind("<Button-4>",   _scroll)   # Linux scroll-up
        w.bind("<Button-5>",   _scroll)   # Linux scroll-down

    # Sidebar header: logo badge + app name + collapse button
    hdr = tk.Frame(app.left, bg=SIDEBAR)
    hdr.pack(fill=tk.X)
    title_row = tk.Frame(hdr, bg=SIDEBAR)
    title_row.pack(fill=tk.X, padx=14, pady=(20, 14))

    # Try to load the PNG logo; fall back to the ✈ text badge if unavailable
    logo_image = _load_logo(size=28)  # returns a PhotoImage or None

    logo_badge = tk.Frame(title_row, bg=ACCENT, width=28, height=28)  # indigo square container for the logo
    logo_badge.pack(side=tk.LEFT)
    logo_badge.pack_propagate(False)

    if logo_image:
        # Keep a reference on app so Tkinter's GC doesn't destroy the image
        app._logo_image = logo_image  # must be stored on app (not a local var) or Tkinter drops it immediately
        tk.Label(logo_badge, image=logo_image, bg=ACCENT,
                 bd=0, highlightthickness=0).place(relx=0.5, rely=0.5, anchor=tk.CENTER)  # PNG logo centred in badge
    else:
        tk.Label(logo_badge, text="✈", bg=ACCENT, fg=PANEL,
                 font=(FONT_UI, 11)).place(relx=0.5, rely=0.5, anchor=tk.CENTER)  # fallback plane icon when no logo file found

    name_col = tk.Frame(title_row, bg=SIDEBAR)
    name_col.pack(side=tk.LEFT, padx=(10, 0))
    tk.Label(name_col, text="NW Airtrace", bg=SIDEBAR, fg=TEXT_SIDE,
             font=(FONT_UI, 12, "bold")).pack(anchor=tk.W)   # application name in sidebar header
    tk.Label(name_col, text="Airfoil Plotter", bg=SIDEBAR, fg=TEXT_SIDE_DIM,
             font=(FONT_UI, 8)).pack(anchor=tk.W)            # subtitle below the app name

    app._toggle_btn = tk.Label(
        title_row, text="‹", bg=SIDEBAR, fg=TEXT_SIDE_DIM,
        font=(FONT_UI, 18), cursor="hand2"
    )  # left-arrow button that collapses the sidebar
    app._toggle_btn.pack(side=tk.RIGHT)
    app._toggle_btn.bind("<Button-1>", lambda e: toggle_sidebar(app))
    app._toggle_btn.bind("<Enter>", lambda e: app._toggle_btn.config(fg=TEXT_SIDE))
    app._toggle_btn.bind("<Leave>", lambda e: app._toggle_btn.config(fg=TEXT_SIDE_DIM))

    tk.Frame(app.left, bg=SEP_DARK, height=1).pack(fill=tk.X)  # separator line below the header

    # Canvas section
    _section(app.left, "CANVAS")
    cc = tk.Frame(app.left, bg=SIDEBAR)
    cc.pack(fill=tk.X, padx=14, pady=(2, 10))

    app.pan_var = tk.BooleanVar(value=False)  # tracks whether Pan / Zoom Mode is currently active
    _mkcheck(cc, "Pan / Zoom Mode", app.pan_var,
             app._toggle_pan_mode, ACCENT).pack(anchor=tk.W, pady=(0, 2))  # checkbox to enable pan/drag mode
    tk.Label(cc, text="Drag to pan  ·  Scroll to zoom",
             bg=SIDEBAR, fg=TEXT_SIDE_DIM, font=(FONT_UI, 8)).pack(anchor=tk.W, padx=4)  # usage hint below the checkbox

    # Zoom label + slider row
    zf = tk.Frame(cc, bg=SIDEBAR)
    zf.pack(fill=tk.X, pady=(10, 0))
    tk.Label(zf, text="Zoom", bg=SIDEBAR, fg=TEXT_SIDE_DIM,
             font=(FONT_UI, 8)).pack(side=tk.LEFT)          # static "Zoom" label
    app.zoom_lbl = tk.Label(zf, text="1.00×", bg=SIDEBAR, fg=ACCENT,
                             font=(FONT_MONO, 8))
    app.zoom_lbl.pack(side=tk.LEFT, padx=(6, 0))            # live zoom level readout updated on each zoom change
    app.zoom_var = tk.DoubleVar(value=1.0)                   # current zoom multiplier shared with canvas rendering
    tk.Scale(
        zf, from_=0.2, to=8.0, resolution=0.05,
        orient=tk.HORIZONTAL, variable=app.zoom_var,
        bg=SIDEBAR, fg=TEXT_SIDE, troughcolor=SEP_DARK,
        highlightthickness=0, length=130, showvalue=False,
        command=app._on_zoom
    ).pack(side=tk.RIGHT)  # drag slider that adjusts the canvas zoom level

    _mkbtn(cc, "Close Shape", app._close_shape,
           ACCENT).pack(fill=tk.X, pady=(12, 0))  # button that connects the last point back to the first

    # Keyboard nudge hint box
    nh = tk.Frame(app.left, bg=SIDEBAR2)
    nh.pack(fill=tk.X, padx=14, pady=(0, 12))
    tk.Label(nh, text="⌨",
             bg=SIDEBAR2, fg=ACCENT, font=(FONT_UI, 10)).pack(side=tk.LEFT, padx=(10, 4), pady=6)
    tk.Label(nh, text="Arrow keys nudge point\nShift+Arrow = 10× step",
             bg=SIDEBAR2, fg=TEXT_SIDE_DIM, font=(FONT_UI, 8),
             justify=tk.LEFT).pack(side=tk.LEFT, pady=6)  # keyboard shortcut reminder for fine point adjustment

    tk.Frame(app.left, bg=SEP_DARK, height=1).pack(fill=tk.X)  # separator between canvas and coordinates sections

    # Coordinates section
    _section(app.left, "COORDINATES")

    cnt_row = tk.Frame(app.left, bg=SIDEBAR)
    cnt_row.pack(fill=tk.X, padx=14, pady=(4, 8))
    app.pt_count_lbl = tk.Label(
        cnt_row, text="0 points",
        bg=ACCENT, fg=PANEL, font=(FONT_UI, 8, "bold"), padx=10, pady=3
    )  # badge showing the total number of plotted points; updates after every add/delete
    app.pt_count_lbl.pack(side=tk.LEFT)

    # Treeview table styles
    style.configure("Treeview", background=SIDEBAR2, fieldbackground=SIDEBAR2,
                    foreground=TEXT_SIDE, rowheight=20, font=(FONT_MONO, 8))
    style.configure("Treeview.Heading", background=SIDEBAR,
                    foreground=TEXT_SIDE_DIM, font=(FONT_UI, 8, "bold"), relief="flat")
    style.map("Treeview", background=[("selected", ACCENT)],
              foreground=[("selected", PANEL)])

    tf = tk.Frame(app.left, bg=SIDEBAR)
    tf.pack(fill=tk.X, padx=14, pady=(0, 8))
    app.tree = ttk.Treeview(tf, columns=("i", "x", "y"),
                             show="headings", height=9,
                             selectmode="extended")  # scrollable table listing every plotted point's index, X, and Y
    for c, w, lbl in [("i", 28, "#"), ("x", 90, "X"), ("y", 90, "Y")]:
        app.tree.heading(c, text=lbl)
        app.tree.column(c, width=w, anchor=tk.CENTER)   # column widths: narrow index, wider X and Y values
    tsb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=app.tree.yview)
    app.tree.configure(yscroll=tsb.set)
    app.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    tsb.pack(side=tk.RIGHT, fill=tk.Y)
    app.tree.bind("<Delete>",            app._delete_selected_from_table)   # Delete key removes selected rows
    app.tree.bind("<Button-3>",          app._table_right_click)            # right-click opens a context menu
    app.tree.bind("<<TreeviewSelect>>",  app._on_tree_select)               # row click highlights point on canvas

    # Copy button and table usage hint
    tbl_actions = tk.Frame(app.left, bg=SIDEBAR)
    tbl_actions.pack(fill=tk.X, padx=14, pady=(4, 2))
    copy_btn = tk.Label(tbl_actions, text="⎘  Copy all to clipboard",
                        bg=SIDEBAR2, fg=TEXT_SIDE, font=(FONT_UI, 8),
                        cursor="hand2", padx=8, pady=4)
    copy_btn.pack(side=tk.LEFT)
    copy_btn.bind("<Button-1>", lambda e: app._copy_to_clipboard())  # copies all coordinates to the OS clipboard
    copy_btn.bind("<Enter>", lambda e: copy_btn.config(fg=ACCENT))
    copy_btn.bind("<Leave>", lambda e: copy_btn.config(fg=TEXT_SIDE))

    tk.Label(app.left, text="  ↵ Click row to highlight  ·  Right-click for options",
             bg=SIDEBAR, fg=TEXT_SIDE_DIM, font=(FONT_UI, 7)).pack(
        anchor=tk.W, padx=14, pady=(2, 4))  # hint text below the table explaining row interactions

    # Status labels for auto-save and SolidWorks export confirmation
    app.csv_lbl = tk.Label(app.left, text="", bg=SIDEBAR, fg=GREEN, font=(FONT_UI, 8))
    app.csv_lbl.pack(padx=14, anchor=tk.W, pady=(0, 2))   # shows "CSV auto-saved" after each point change
    app.sw_lbl = tk.Label(app.left, text="", bg=SIDEBAR, fg=PURPLE, font=(FONT_UI, 8))
    app.sw_lbl.pack(padx=14, anchor=tk.W, pady=(0, 8))    # shows point count after a SolidWorks export

    tk.Frame(app.left, bg=SEP_DARK, height=1).pack(fill=tk.X)  # separator before the calibration section

    # Calibration section
    _section(app.left, "CALIBRATION")

    cal_row = tk.Frame(app.left, bg=SIDEBAR2)
    cal_row.pack(fill=tk.X, padx=14, pady=(0, 16))
    app.cal_status = tk.Label(
        cal_row, text="Not calibrated",
        bg=SIDEBAR2, fg=ACCENT2, font=(FONT_UI, 8, "bold")
    )  # shows calibration state (Not calibrated / Auto-cal / ✓ Calibrated)
    app.cal_status.pack(padx=10, pady=(6, 2), anchor=tk.W)
    app.angle_lbl = tk.Label(cal_row, text="", bg=SIDEBAR2, fg=PURPLE, font=(FONT_UI, 8))
    app.angle_lbl.pack(padx=10, pady=(0, 6), anchor=tk.W)  # shows rotation angle after Rotate to 0° is applied


def toggle_sidebar(app):
    """Collapses the full sidebar to a stub strip, or expands it back."""
    if app._sidebar_visible:
        app._sidebar_outer.pack_forget()    # hide the full 268px sidebar
        app._sidebar_stub.pack(side=tk.LEFT, fill=tk.Y, before=app.canvas.master)  # show the 36px stub
        app._sidebar_visible = False
    else:
        app._sidebar_stub.pack_forget()     # hide the stub
        app._sidebar_outer.pack(side=tk.LEFT, fill=tk.Y, before=app.canvas.master)  # restore full sidebar
        app._sidebar_visible = True


def _section(parent, title):
    """Renders a small all-caps section heading inside the sidebar."""
    f = tk.Frame(parent, bg=SIDEBAR)
    f.pack(fill=tk.X, pady=(16, 4))
    tk.Label(f, text=title.upper(), bg=SIDEBAR, fg=TEXT_SIDE_DIM,
             font=(FONT_UI, 7, "bold"), padx=14).pack(anchor=tk.W)  # all-caps section label used as a visual separator


def _mkcheck(parent, text, var, cmd, color=ACCENT):
    """Creates a styled Checkbutton for the dark sidebar."""
    return tk.Checkbutton(
        parent, text=text, variable=var, command=cmd,
        bg=SIDEBAR, fg=TEXT_SIDE, selectcolor=SIDEBAR2,
        activebackground=SIDEBAR, activeforeground=ACCENT,
        font=(FONT_UI, 10), cursor="hand2", highlightthickness=0
    )  # dark-themed checkbox used for toggle options in the sidebar


def _mkbtn(parent, text, cmd, color=ACCENT):
    """Creates a styled full-width Button for the dark sidebar."""
    f = tk.Frame(parent, bg=SIDEBAR)
    b = tk.Button(
        f, text=text, command=cmd,
        bg=color, fg=PANEL,
        activebackground=PURPLE, activeforeground=PANEL,
        relief=tk.FLAT, font=(FONT_UI, 9, "bold"),
        cursor="hand2", pady=7, bd=0, highlightthickness=0
    )  # flat dark button used for primary actions in sidebar sections
    b.pack(fill=tk.X)
    b.bind("<Enter>", lambda e: b.config(bg=PURPLE))  # hover turns button violet
    b.bind("<Leave>", lambda e: b.config(bg=color))   # leave restores original accent colour
    return f