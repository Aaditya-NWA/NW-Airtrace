"""
app.py — ShapePlotter: the root Tk window for NW Airtrace.

Owns all application state, builds the UI by delegating to ui/ modules,
and exposes thin wrapper methods so Tkinter callbacks (which bind to self.*)
can dispatch cleanly to the stateless functions in core/ and ui/.
"""

import tkinter as tk
from tkinter import ttk
import os

from constants import (
    BG, PANEL, ACCENT, ACCENT2, SIDEBAR, TEXT_DIM,
    SEP_CLR, FONT_UI, FONT_MONO
)

# UI builders
from ui.menubar import build_menubar
from ui.sidebar import build_sidebar, toggle_sidebar

# Dialogs (thin wrappers below call these)
from ui.dialogs import (
    show_density_dialog,
    show_settings_dialog,
    ask_real_point,
    show_export_dialog,
)

# Core: calibration
from core.calibration import (
    auto_calibrate,
    detect_airfoil_endpoints,
    start_calibration,
    handle_cal_click,
    finish_calibration,
    reset_calibration,
    img_px_to_real,
    px_to_real,
    real_to_canvas,
    real_to_img_px,
)

# Core: auto-plot
from core.autoplot import auto_plot

# Core: export / import
from core.export import (
    maybe_normalize,
    export_csv,
    export_solidworks,
    preview_export_curve,
    download_image,
    copy_to_clipboard,
    upload_curve_file,
)

# Core: canvas drawing and interaction
from core.canvas import (
    draw_grid, draw_dots, draw_lines, redraw_all, redraw_cal_marks,
    hit_test, hit_test_segment,
    on_click, on_right_click, on_motion, on_drag, on_release,
    on_resize, on_zoom, on_scroll, on_nudge, on_canvas_delete,
    toggle_pan_mode,
    close_shape, rotate_to_horizontal,
    push_undo, undo_point,
    select_all, clear_selection,
    delete_selected_from_table, table_right_click,
    on_tree_select, jump_to_selected_point,
    render_image, fit_image_to_canvas, fit_image_to_canvas_and_render,
    render_or_redraw, refit_and_redraw,
    zoom_step, toggle_fullscreen,
    refresh_table, refresh_status,
    clear_image, clear_all,
)

class ShapePlotter(tk.Tk):
    """
    Root application window for NW Airtrace — Airfoil Coordinate Plotter.

    All mutable application state lives here as instance attributes.
    UI construction is delegated to ui/ modules; all interaction logic
    is delegated to core/ modules via thin wrapper methods below.
    """

    def __init__(self):
        super().__init__()
        self.title("NW Airtrace  —  Airfoil Coordinate Plotter")  # sets the window title shown in the OS taskbar
        self.configure(bg=BG)
        self.minsize(1100, 680)  # prevents the window from being resized smaller than a usable layout

        self.image_orig   = None    # holds the original PIL Image object after File > Open Image
        self.image_tk     = None    # holds the Tkinter-compatible ImageTk.PhotoImage shown on canvas
        self.scale_factor = 1.0     # current pixel-to-canvas scale factor (zoom level × fit factor)
        self.img_offset   = (0, 0)  # (ox, oy) canvas pixel position of the image top-left corner

        self.mode             = "plot"   # current interaction mode: "plot" or "calibrate"
        self.cal_points_px    = []       # list of (img_x, img_y) image-pixel positions for calibration reference points
        self.cal_points_real  = []       # list of (rx, ry) real-world coordinates corresponding to cal_points_px
        self.calibrated       = False    # True once a valid calibration transform has been computed
        self.transform        = None     # dict with keys px_origin, r_origin, x_scale, y_scale

        self.coords      = []            # ordered list of (rx, ry) real-world coordinate pairs placed by the user
        self.hovered_idx = None          # index of the point currently under the mouse cursor (or None)
        self.drag_idx    = None          # index of the point currently being dragged (or None)
        self.nudge_idx   = None          # index of the point that receives keyboard arrow-key nudge (or None)
        self._selected   = set()         # set of selected point indices (mirrors tree selection)

        self._undo_stack = []            # list of deep-copied coord lists; pop to undo; capped at 50 entries

        self.flip_y_var    = None        # BooleanVar: flip Y axis for aerodynamic convention
        self.normalize_var = None        # BooleanVar: normalise all coordinates to 0–1 range
        self.auto_cal_var  = None        # BooleanVar: run auto-calibrate when an image is opened
        self.auto_plot_var = None        # BooleanVar: run auto-plot when an image is opened
        self.density_var   = None        # IntVar: number of points for auto-plot

        self._upload_y_flip = False      # True when the curve was loaded from a file (no image) so Y is inverted
        self._upload_y_max  = 0.0        # maximum Y value of the uploaded curve (used for Y-flip rendering)
        self._upload_y_min  = 0.0        # minimum Y value of the uploaded curve (used for Y-flip rendering)
        self.pan_mode       = False      # True when Pan / Zoom Mode checkbox is active
        self._pan_start_x   = 0          # canvas X position where the current pan drag began
        self._pan_start_y   = 0          # canvas Y position where the current pan drag began
        self._pan_offset_x  = 0          # cumulative horizontal pan displacement from the image centre
        self._pan_offset_y  = 0          # cumulative vertical pan displacement from the image centre

        self._last_image_path = None     # full file path of the last opened image (used for auto-save CSV naming)
        self._preview_visible = False    # True while the export preview curve is drawn on the canvas

        self._build_ui()
        self._bind_events()

    # =========================================================================
    # UI construction
    # =========================================================================

    def _build_ui(self):
        """
        Builds the full application UI in order:
        1. Top menubar
        2. Left sidebar (collapsible)
        3. Right canvas area (mode pill, canvas, status bar)
        """
        build_menubar(self)   # creates the top menu bar with File / Edit / Calibrate / View / Settings menus
        build_sidebar(self)   # creates the dark left sidebar with canvas controls, coordinate table, and calibration status

        right = tk.Frame(self, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)  # fills all remaining horizontal space to the right of the sidebar

        # Slim top bar: mode pill + coordinate readout
        toolbar = tk.Frame(right, bg=PANEL, height=40)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        tk.Frame(toolbar, bg=SEP_CLR, height=1).place(relx=0, rely=1.0,
                                                       relwidth=1.0, anchor="sw")  # 1px bottom border on the toolbar

        mode_pill = tk.Frame(toolbar, bg=ACCENT)
        mode_pill.pack(side=tk.LEFT, padx=(16, 0), pady=10)
        self.mode_lbl = tk.Label(mode_pill, text=" PLOT ",
                                 bg=ACCENT, fg=PANEL,
                                 font=(FONT_UI, 8, "bold"), pady=2, padx=8)
        self.mode_lbl.pack()  # coloured pill showing the current interaction mode (PLOT / PAN / CALIBRATE)

        tk.Frame(toolbar, bg=SEP_CLR, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8, padx=12)

        self.coord_lbl = tk.Label(toolbar, text="x: —        y: —",
                                  bg=PANEL, fg=TEXT_DIM, font=(FONT_MONO, 9))
        self.coord_lbl.pack(side=tk.LEFT)  # live coordinate readout that follows the mouse cursor over the canvas

        # Main drawing canvas
        self.canvas = tk.Canvas(right, bg="#ECEEF5", cursor="crosshair",
                                highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)  # fills the full area below the toolbar and above the status bar

        # Status bar at the bottom
        tk.Frame(right, bg=SEP_CLR, height=1).pack(side=tk.BOTTOM, fill=tk.X)
        self._status_bar = tk.Label(right,
                                    text="✦  Ready  —  Open an image or upload a curve to begin",
                                    bg=PANEL, fg=TEXT_DIM,
                                    font=(FONT_UI, 9), anchor=tk.W, padx=16)
        self._status_bar.pack(side=tk.BOTTOM, fill=tk.X, ipady=5)  # one-line bar at the bottom confirming the last user action

        draw_grid(self)  # draws the initial background grid before any image is loaded

    # =========================================================================
    # Event binding
    # =========================================================================

    def _bind_events(self):
        """
        Wires all canvas mouse events, keyboard shortcuts, and initialises
        the settings BooleanVar / IntVar instances used by the dialogs.
        """
        self.canvas.bind("<Button-1>",        self._on_click)           # left-click: place point or start drag
        self.canvas.bind("<Motion>",          self._on_motion)          # mouse move: update coordinate readout and hover
        self.canvas.bind("<B1-Motion>",       self._on_drag)            # drag with button held: move point or pan
        self.canvas.bind("<ButtonRelease-1>", self._on_release)         # release: end drag
        self.canvas.bind("<Configure>",       self._on_resize)          # canvas resize: redraw grid and re-render
        self.canvas.bind("<Button-3>",        self._on_right_click)     # right-click: delete hovered point
        self.canvas.bind("<MouseWheel>",      self._on_scroll)          # scroll wheel (Windows / macOS): zoom
        self.canvas.bind("<Button-4>",        self._on_scroll)          # scroll up (Linux): zoom in
        self.canvas.bind("<Button-5>",        self._on_scroll)          # scroll down (Linux): zoom out

        self.bind("<Control-z>", lambda e: self._undo_point())          # Ctrl+Z: undo last action
        self.bind("<Control-Z>", lambda e: self._undo_point())          # Ctrl+Shift+Z: also undo (case-insensitive)
        self.bind("<Delete>",    self._on_canvas_delete)                # Delete key: remove hovered or last point
        self.bind("<BackSpace>", self._on_canvas_delete)                # Backspace: same as Delete
        self.bind("<Control-a>", lambda e: self._select_all())          # Ctrl+A: select all table rows
        self.bind("<Escape>",    lambda e: self._clear_selection())     # Escape: deselect all
        self.bind("<F11>",       lambda e: self._toggle_fullscreen())   # F11: toggle fullscreen

        for key in ("<Left>", "<Right>", "<Up>", "<Down>",
                    "<Shift-Left>", "<Shift-Right>", "<Shift-Up>", "<Shift-Down>"):
            self.bind(key, self._on_nudge)   # arrow keys nudge the selected point; Shift gives a 10× step

        # Initialise all settings variables here so dialogs can reference them immediately
        self.density_var   = tk.IntVar(value=60)         # default auto-plot point density
        self.auto_cal_var  = tk.BooleanVar(value=True)   # auto-calibrate when image opens
        self.auto_plot_var = tk.BooleanVar(value=True)   # auto-plot when image opens
        self.normalize_var = tk.BooleanVar(value=True)   # normalise coordinates to 0–1 on export and display
        self.flip_y_var    = tk.BooleanVar(value=True)   # flip Y for aerodynamic positive-up convention

    # =========================================================================
    # Status bar helper
    # =========================================================================

    def _set_status(self, msg):
        """Updates the bottom status bar with the given message."""
        self._status_bar.config(text="  " + msg)  # two-space indent keeps text away from the left edge

    # =========================================================================
    # Image open
    # =========================================================================

    def _open_image(self):
        """
        Prompts the user to choose an image file, loads it, resets all state,
        and optionally runs auto-calibration and auto-plot based on settings.
        """
        from tkinter import filedialog, messagebox
        from PIL import Image

        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif")]
        )  # restricts the file picker to supported image formats
        if not path:
            return

        try:
            self.image_orig = Image.open(path).convert("RGBA")   # loads and converts to RGBA for consistent compositing
        except Exception as e:
            messagebox.showerror("Open Image", f"Could not open image:\n{e}")
            return

        self._last_image_path = path
        self._pan_offset_x    = 0
        self._pan_offset_y    = 0
        self._upload_y_flip   = False
        self.zoom_var.set(1.0)
        if hasattr(self, "zoom_lbl"):
            self.zoom_lbl.config(text="1.00×")   # resets the sidebar zoom readout to 100%

        # Clear previous session data
        self.calibrated       = False
        self.transform        = None
        self.cal_points_px    = []
        self.cal_points_real  = []
        self.coords           = []
        self.canvas.delete("dot", "line", "cal_mark")
        self.cal_status.config(text="Not calibrated", fg=ACCENT2)   # resets calibration status in sidebar

        self.update_idletasks()   # ensures the canvas geometry is resolved before fitting
        fit_image_to_canvas(self)
        render_image(self)

        if self.auto_cal_var.get():
            auto_calibrate(self)   # automatically detects LE and TE endpoints and sets the transform
        if self.auto_plot_var.get():
            self.after(120, lambda: auto_plot(self))   # slight delay ensures the image is fully rendered first

    # =========================================================================
    # Thin wrapper methods
    # All public methods called by Tkinter event bindings or menu commands
    # must live on self so Python can resolve them via the lambda/bind syntax.
    # Each one delegates immediately to the corresponding core/ or ui/ function.
    # =========================================================================

    def _toggle_sidebar(self):
        toggle_sidebar(self)   # collapses or expands the left sidebar

    def _show_density_dialog(self):
        show_density_dialog(self)   # opens the point-density slider dialog

    def _show_settings_dialog(self):
        show_settings_dialog(self)  # opens the settings dialog with normalize / flip-Y / auto toggles

    def _ask_real_point(self, index):
        return ask_real_point(self, index)   # prompts for the real-world coordinates of a calibration point

    def _auto_calibrate(self):
        auto_calibrate(self)   # detects airfoil endpoints and sets LE=(0,0) TE=(1,0) automatically

    def _detect_airfoil_endpoints(self):
        return detect_airfoil_endpoints(self)   # returns (le_px, te_px) image-pixel tuples

    def _start_calibration(self):
        start_calibration(self)   # enters manual calibration mode (next two clicks set reference points)

    def _handle_cal_click(self, cx, cy):
        handle_cal_click(self, cx, cy)   # records one calibration click and prompts for its real coordinate

    def _finish_calibration(self, silent=False):
        finish_calibration(self, silent)   # computes the pixel-to-real transform from two reference points

    def _reset_calibration(self):
        reset_calibration(self)   # clears all calibration data and marks

    def _img_px_to_real(self, img_x, img_y):
        return img_px_to_real(self, img_x, img_y)   # converts image-pixel position to real-world coordinates

    def _px_to_real(self, cx, cy):
        return px_to_real(self, cx, cy)   # converts canvas-pixel position to real-world coordinates

    def _real_to_canvas(self, rx, ry):
        return real_to_canvas(self, rx, ry)   # converts real-world coordinates to canvas-pixel position

    def _real_to_img_px(self, rx, ry):
        return real_to_img_px(self, rx, ry)   # converts real-world coordinates back to image-pixel position

    def _auto_plot(self):
        auto_plot(self)   # detects the airfoil outline and places points along it automatically

    def _maybe_normalize(self, pts):
        return maybe_normalize(self, pts)   # applies normalize and flip-Y settings to a point list

    def _export_csv(self):
        export_csv(self)   # saves all coordinates to a CSV file chosen by the user

    def _export_solidworks(self):
        export_solidworks(self)   # processes and saves a SolidWorks-ready XYZ curve file

    def _preview_export_curve(self):
        preview_export_curve(self)   # draws the smoothed export curve on canvas for review

    def _download_image(self):
        download_image(self)   # saves the annotated image (with dots and lines) to disk

    def _copy_to_clipboard(self):
        copy_to_clipboard(self)   # copies all coordinates to the OS clipboard as tab-separated X Y pairs

    def _upload_curve_file(self):
        upload_curve_file(self)   # loads a .dat / .txt coordinate file directly onto the canvas

    def _draw_grid(self):
        draw_grid(self)   # redraws the background grid at 60px intervals

    def _draw_dots(self):
        draw_dots(self)   # redraws all plotted point circles on the canvas

    def _draw_lines(self):
        draw_lines(self)   # redraws the connecting curve through all plotted points

    def _redraw_all(self):
        redraw_all(self)   # redraws dots, lines, and calibration markers in the correct z-order

    def _redraw_cal_marks(self):
        redraw_cal_marks(self)   # redraws calibration rings and labels at their current canvas positions

    def _on_click(self, event):
        on_click(self, event)   # left-click: place point, start drag, or record calibration point

    def _on_right_click(self, event):
        on_right_click(self, event)   # right-click: delete hovered point

    def _on_motion(self, event):
        on_motion(self, event)   # mouse move: update coordinate readout and hover highlight

    def _on_drag(self, event):
        on_drag(self, event)   # drag: move a point or pan the view

    def _on_release(self, event):
        on_release(self, event)   # mouse release: end drag

    def _on_resize(self, event):
        on_resize(self, event)   # canvas resize: redraw grid and re-render

    def _on_zoom(self, _=None):
        on_zoom(self)   # zoom slider moved: refit viewport or re-render image

    def _on_scroll(self, event):
        on_scroll(self, event)   # scroll wheel: zoom toward the cursor

    def _on_nudge(self, event):
        return on_nudge(self, event)   # arrow key: nudge the selected point by 1 or 10 pixels

    def _on_canvas_delete(self, event=None):
        on_canvas_delete(self, event)   # Delete / Backspace: remove hovered or last point

    def _hit_test(self, cx, cy, radius=9):
        return hit_test(self, cx, cy, radius)   # returns index of the point under the cursor

    def _hit_test_segment(self, cx, cy, threshold=8):
        return hit_test_segment(self, cx, cy, threshold)   # returns insert position and midpoint of a hovered segment

    def _toggle_pan_mode(self):
        toggle_pan_mode(self)   # switches between pan/zoom mode and plot mode

    def _close_shape(self):
        close_shape(self)   # connects the last point back to the first to close the shape

    def _rotate_to_horizontal(self):
        rotate_to_horizontal(self)   # rotates the chord line to horizontal (0°)

    def _push_undo(self):
        push_undo(self)   # saves the current coordinate list to the undo stack

    def _undo_point(self):
        undo_point(self)   # restores the previous coordinate state

    def _select_all(self):
        select_all(self)   # selects all rows in the coordinates table

    def _clear_selection(self):
        clear_selection(self)   # clears all table row selections

    def _delete_selected_from_table(self, event=None):
        delete_selected_from_table(self, event)   # deletes the points corresponding to selected table rows

    def _table_right_click(self, event):
        table_right_click(self, event)   # shows a context menu on right-click in the coordinates table

    def _on_tree_select(self, event=None):
        on_tree_select(self, event)   # highlights the selected table row's point on the canvas

    def _jump_to_selected_point(self):
        jump_to_selected_point(self)   # pans canvas to centre on the selected point

    def _render_image(self):
        render_image(self)   # resizes and draws the loaded image on the canvas

    def _fit_image_to_canvas(self):
        fit_image_to_canvas(self)   # sets zoom so the image fills 90% of the canvas

    def _fit_image_to_canvas_and_render(self):
        fit_image_to_canvas_and_render(self)   # fits and re-renders the image, or refits uploaded coordinates

    def _render_or_redraw(self):
        render_or_redraw(self)   # re-renders the image if loaded, else redraws the vector overlay

    def _refit_and_redraw(self):
        refit_and_redraw(self)   # refits the viewport to uploaded coordinate extents and redraws

    def _zoom_step(self, factor):
        zoom_step(self, factor)   # applies a multiplicative zoom step and re-renders

    def _toggle_fullscreen(self):
        toggle_fullscreen(self)   # toggles fullscreen mode

    def _refresh_table(self):
        refresh_table(self)   # rebuilds the coordinates table and auto-saves the CSV

    def _refresh_status(self):
        refresh_status(self)   # updates the status bar with point count and calibration state

    def _clear_image(self):
        clear_image(self)   # removes the loaded image and keeps plotted points

    def _clear_all(self):
        clear_all(self)   # deletes all plotted points after confirmation
