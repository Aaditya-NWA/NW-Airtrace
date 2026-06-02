"""
ui/dialogs.py — Modal dialog windows for NW AirTrace.

Provides:
  show_density_dialog(app)    — slider for auto-plot point density
  show_settings_dialog(app)   — toggles for normalize, flip-Y, auto-cal, auto-plot
  ask_real_point(app, index)  — prompts the user to enter real (X, Y) calibration coordinates
  show_export_dialog(app, pts, removed) — SolidWorks export format picker
"""

import tkinter as tk
from tkinter import messagebox, filedialog

from constants import (
    PANEL, BG, TEXT, TEXT_DIM, ACCENT, ACCENT2, ACCENT_LT,
    GREEN, YELLOW, PURPLE, SEP_CLR, CARD_BG, FONT_UI
)

def show_density_dialog(app):
    """
    Opens a small dialog with a slider that lets the user set the number of
    points the auto-plot algorithm will place around the detected airfoil outline.
    Clicking Apply re-runs auto-plot immediately.
    """
    dlg = tk.Toplevel(app)
    dlg.title("Point Density")
    dlg.configure(bg=PANEL)
    dlg.resizable(False, False)
    dlg.grab_set()       # blocks interaction with the main window while the dialog is open
    dlg.geometry("320x180")

    tk.Label(dlg, text="Point Density", bg=PANEL, fg=ACCENT,
             font=(FONT_UI, 11, "bold")).pack(pady=(18, 4))  # dialog heading
    tk.Label(dlg, text="Number of points for auto-plot",
             bg=BG, fg=TEXT_DIM, font=(FONT_UI, 8)).pack()   # sub-label explaining what the slider controls

    sv = tk.IntVar(value=app.density_var.get() if app.density_var else 60)  # current density value shown in slider
    if not app.density_var:
        app.density_var = sv  # initialise density_var if it was never set

    fr = tk.Frame(dlg, bg=BG)
    fr.pack(pady=10)
    tk.Scale(fr, from_=10, to=200, orient=tk.HORIZONTAL,
             variable=sv, bg=BG, fg=TEXT,
             troughcolor=PANEL, highlightthickness=0,
             length=200).pack(side=tk.LEFT)  # drag slider to choose between 10 and 200 auto-plot points

    def _apply():
        app.density_var = sv        # commits the chosen density back to the app state
        dlg.destroy()
        app._auto_plot()            # immediately re-runs auto-plot with the new density

    tk.Button(dlg, text="Apply & Re-Plot", command=_apply,
              bg=ACCENT, fg=BG, font=(FONT_UI, 9, "bold"),
              relief=tk.FLAT, padx=16, pady=6).pack(pady=4)  # applies density and triggers a new auto-plot pass

def show_settings_dialog(app):
    """
    Opens the Settings dialog with four checkboxes that control global
    export and display behaviour (auto-calibrate, auto-plot, normalise, flip-Y).
    """
    dlg = tk.Toplevel(app)
    dlg.title("Settings")
    dlg.configure(bg=PANEL)
    dlg.resizable(False, False)
    dlg.grab_set()       # modal — blocks the main window until closed
    dlg.geometry("340x260")

    tk.Label(dlg, text="Settings", bg=BG, fg=ACCENT,
             font=(FONT_UI, 12, "bold")).pack(pady=(18, 4))  # dialog heading
    tk.Frame(dlg, bg=SEP_CLR, height=1).pack(fill=tk.X, padx=20, pady=4)

    checks = [
        ("⚡  Auto-Calibrate on Upload", app.auto_cal_var,  GREEN),   # automatically runs calibration when an image is opened
        ("🤖  Auto-Plot on Upload",      app.auto_plot_var, GREEN),   # automatically runs auto-plot when an image is opened
        ("⇳   Normalize to Unit (0–1)", app.normalize_var, ACCENT),  # scales all exported coordinates to a 0–1 range
        ("↕   Flip Y (aerodynamic)",    app.flip_y_var,    YELLOW),  # inverts the Y axis so positive Y points upward
    ]
    for text, var, color in checks:
        tk.Checkbutton(
            dlg, text=text, variable=var,
            command=app._refresh_table,
            bg=BG, fg=color, selectcolor=PANEL,
            activebackground=PANEL, activeforeground=color,
            font=(FONT_UI, 9)
        ).pack(anchor=tk.W, padx=24, pady=3)  # each checkbox updates the coordinates table immediately on toggle

    tk.Frame(dlg, bg=SEP_CLR, height=1).pack(fill=tk.X, padx=20, pady=8)
    tk.Button(dlg, text="Close", command=dlg.destroy,
              bg=BG, fg=TEXT, font=(FONT_UI, 9),
              relief=tk.FLAT, padx=20, pady=5).pack()  # closes the dialog and returns focus to the main window

def ask_real_point(app, index):
    """
    Prompts the user to type in the real-world (X, Y) coordinates for a
    calibration point they just clicked on the canvas.
    Returns (x_float, y_float) or (None, None) if the user cancelled.
    """
    dlg = tk.Toplevel(app)
    dlg.title(f"Calibration Point {index}")
    dlg.configure(bg=PANEL)
    dlg.resizable(False, False)
    dlg.grab_set()       # modal — prevents clicking elsewhere while entering coordinates

    tk.Label(dlg, text=f"Real coordinates for point {index}:",
             bg=BG, fg=TEXT, font=(FONT_UI, 10)).pack(padx=20, pady=(16, 8))  # prompt heading showing point number

    f = tk.Frame(dlg, bg=BG)
    f.pack(padx=20, pady=4)
    tk.Label(f, text="X:", bg=BG, fg=ACCENT, font=(FONT_UI, 10)).grid(row=0, column=0, sticky=tk.W)
    xv = tk.StringVar(value="0")
    tk.Entry(f, textvariable=xv, bg=PANEL, fg=TEXT, insertbackground=TEXT,
             font=(FONT_UI, 10), width=10).grid(row=0, column=1, padx=8)  # text field for the real-world X coordinate
    tk.Label(f, text="Y:", bg=BG, fg=ACCENT, font=(FONT_UI, 10)).grid(row=1, column=0, sticky=tk.W, pady=4)
    yv = tk.StringVar(value="0")
    tk.Entry(f, textvariable=yv, bg=PANEL, fg=TEXT, insertbackground=TEXT,
             font=(FONT_UI, 10), width=10).grid(row=1, column=1, padx=8)  # text field for the real-world Y coordinate

    result = {}

    def ok():
        try:
            result["x"] = float(xv.get())   # validates and stores the entered X value
            result["y"] = float(yv.get())   # validates and stores the entered Y value
            dlg.destroy()
        except ValueError:
            messagebox.showerror("Error", "Enter valid numbers.", parent=dlg)  # rejects non-numeric input

    tk.Button(dlg, text="OK", command=ok, bg=ACCENT, fg=BG,
              font=(FONT_UI, 10, "bold"), padx=20, pady=6,
              relief=tk.FLAT).pack(pady=12)  # confirms the entered coordinates

    app.wait_window(dlg)     # suspends execution until the dialog is dismissed
    return result.get("x"), result.get("y")  # returns None, None if user cancelled without clicking OK

def show_export_dialog(app, pts, removed):
    """
    Popup that lets the user choose export file format (.txt / .dat),
    units suffix (mm), and which axes (X, Y, Z) to include, then save.
    *pts* is the final list of (x, y) tuples ready to write.
    *removed* is the number of inflection points stripped during cleanup.
    """
    dlg = tk.Toplevel(app)
    dlg.title("Export for SolidWorks")
    dlg.configure(bg=PANEL)
    dlg.resizable(False, False)
    dlg.grab_set()       # modal while the user confirms export options
    dlg.geometry("480x500")

    # Header row: title + point count badge
    hdr = tk.Frame(dlg, bg=PANEL)
    hdr.pack(fill=tk.X, padx=20, pady=(18, 2))
    tk.Label(hdr, text="EXPORT FORMAT", bg=PANEL, fg=ACCENT,
             font=(FONT_UI, 12, "bold")).pack(side=tk.LEFT)  # dialog title
    raw_count    = len(app.coords)    # original number of plotted points before processing
    export_count = len(pts)           # number of points that will actually be written to file
    tk.Label(
        hdr,
        text=f"  {raw_count} raw  →  {export_count} export pts  ",
        bg=ACCENT_LT, fg=ACCENT, font=(FONT_UI, 8, "bold"), padx=6, pady=2
    ).pack(side=tk.RIGHT)  # badge comparing the raw point count to the export-ready count
    tk.Frame(dlg, bg=SEP_CLR, height=1).pack(fill=tk.X, padx=20, pady=(0, 12))

    # File format checkboxes
    tk.Label(dlg, text="File Format", bg=BG, fg=TEXT_DIM,
             font=(FONT_UI, 8, "bold")).pack(anchor=tk.W, padx=24)
    fmt_frame = tk.Frame(dlg, bg=BG)
    fmt_frame.pack(anchor=tk.W, padx=32, pady=(2, 10))
    var_txt = tk.BooleanVar(value=True)   # .txt format is the default SolidWorks input format
    var_dat = tk.BooleanVar(value=False)  # .dat is an optional alternative format
    for var, label in [(var_txt, ".txt"), (var_dat, ".dat")]:
        tk.Checkbutton(fmt_frame, text=label, variable=var,
                       bg=BG, fg=ACCENT, selectcolor=PANEL,
                       activebackground=PANEL, activeforeground=ACCENT,
                       font=(FONT_UI, 10)).pack(side=tk.LEFT, padx=10)  # select which file extensions to save

    tk.Frame(dlg, bg=SEP_CLR, height=1).pack(fill=tk.X, padx=20, pady=4)

    # Units suffix
    tk.Label(dlg, text="Units Suffix", bg=BG, fg=TEXT_DIM,
             font=(FONT_UI, 8, "bold")).pack(anchor=tk.W, padx=24)
    var_mm = tk.BooleanVar(value=True)  # appends "mm" to every value for SolidWorks unit recognition
    tk.Checkbutton(dlg, text='Append "mm" to each value',
                   variable=var_mm,
                   bg=BG, fg=YELLOW, selectcolor=PANEL,
                   activebackground=BG, activeforeground=YELLOW,
                   font=(FONT_UI, 10)).pack(anchor=tk.W, padx=32, pady=(2, 10))

    tk.Frame(dlg, bg=SEP_CLR, height=1).pack(fill=tk.X, padx=20, pady=4)

    # Axis checkboxes
    tk.Label(dlg, text="Include Axes", bg=BG, fg=TEXT_DIM,
             font=(FONT_UI, 8, "bold")).pack(anchor=tk.W, padx=24)
    ax_frame = tk.Frame(dlg, bg=BG)
    ax_frame.pack(anchor=tk.W, padx=32, pady=(2, 10))
    var_x = tk.BooleanVar(value=True)    # include X column (chord-wise position)
    var_y = tk.BooleanVar(value=True)    # include Y column (thickness)
    var_z = tk.BooleanVar(value=False)   # include Z column of zeros (SolidWorks 3-D curve requirement)
    for var, label, color in [
        (var_x, "X-axis",       ACCENT),
        (var_y, "Y-axis",       GREEN),
        (var_z, "Z-axis (zeros)", TEXT_DIM),
    ]:
        tk.Checkbutton(ax_frame, text=label, variable=var,
                       bg=BG, fg=color, selectcolor=PANEL,
                       activebackground=PANEL, activeforeground=color,
                       font=(FONT_UI, 10)).pack(side=tk.LEFT, padx=8)

    tk.Frame(dlg, bg=SEP_CLR, height=1).pack(fill=tk.X, padx=20, pady=4)

    # Live preview of first 4 output lines
    tk.Label(dlg, text="Preview (first 4 lines)", bg=BG, fg=TEXT_DIM,
             font=(FONT_UI, 8, "bold")).pack(anchor=tk.W, padx=24)
    preview_lbl = tk.Label(dlg, text="", bg=CARD_BG, fg=TEXT,
                           font=(FONT_UI, 9), justify=tk.LEFT,
                           anchor=tk.W, relief=tk.FLAT, padx=10, pady=6)
    preview_lbl.pack(fill=tk.X, padx=24, pady=(2, 12))  # shows a sample of how the output file will look

    def _build_line(x, y):
        suf   = "mm" if var_mm.get() else ""
        parts = []
        if var_x.get(): parts.append(str(round(x, 6)) + suf)  # adds X value with optional "mm"
        if var_y.get(): parts.append(str(round(y, 6)) + suf)  # adds Y value with optional "mm"
        if var_z.get(): parts.append("0" + suf)               # adds Z=0 with optional "mm"
        return " ".join(parts)

    def _update_preview(*_):
        lines = [_build_line(x, y) for x, y in pts[:4]]
        if not (var_x.get() or var_y.get() or var_z.get()):
            preview_lbl.config(text="(no axes selected)", fg=ACCENT2)   # warns when no column is chosen
        else:
            preview_lbl.config(text="\n".join(lines) or "(empty)", fg=GREEN)

    for v in (var_txt, var_dat, var_mm, var_x, var_y, var_z):
        v.trace_add("write", _update_preview)   # refreshes the preview whenever any option changes
    _update_preview()

    def _do_save():
        if not var_txt.get() and not var_dat.get():
            messagebox.showwarning("Export", "Select at least one format.", parent=dlg)
            return
        if not (var_x.get() or var_y.get() or var_z.get()):
            messagebox.showwarning("Export", "Select at least one axis.", parent=dlg)
            return

        saved = []
        ext   = ".txt"  # default extension for status message; overwritten in loop
        for use_fmt, ext in [(var_txt.get(), ".txt"), (var_dat.get(), ".dat")]:
            if not use_fmt:
                continue
            path = filedialog.asksaveasfilename(
                defaultextension=ext,
                filetypes=[(f"SolidWorks Curve (*{ext})", f"*{ext}"), ("All files", "*.*")],
                initialfile="airfoil_solidworks" + ext,
                title=f"Save {ext} file",
                parent=dlg
            )  # file-save dialog scoped to the supported SolidWorks curve formats
            if not path:
                continue
            try:
                with open(path, "w") as f:
                    for x, y in pts:
                        f.write(_build_line(x, y) + "\n")  # writes each point as one space-separated line
                saved.append(path)
            except Exception as e:
                messagebox.showerror("Export Failed",
                                     f"Could not write {ext} file:\n{e}", parent=dlg)
                continue

        if saved:
            dlg.destroy()
            status = (str(len(pts)) + " pts saved"
                      + ("  |  " + str(removed) + " inflection(s) removed"
                         if removed else "  |  curve clean"))
            if hasattr(app, "sw_lbl"):
                app.sw_lbl.config(text=status)  # updates the sidebar SolidWorks status label
            msg = f"Saved {len(pts)} points to:\n" + "\n".join(saved)
            if ext == ".txt":
                msg += ("\n\nIn SolidWorks:\n"
                        "  Insert > Curve > Curve Through XYZ Points\n"
                        "  Select the .txt file")
            messagebox.showinfo("Export for SolidWorks", msg)  # confirms the saved file paths to the user

    tk.Button(dlg, text="Save File(s)", command=_do_save,
              bg=ACCENT, fg=PANEL, font=(FONT_UI, 10, "bold"),
              relief=tk.FLAT, padx=20, pady=8,
              cursor="hand2").pack(pady=4)   # triggers the file-save dialog and writes the selected formats
    tk.Button(dlg, text="Cancel", command=dlg.destroy,
              bg=SEP_CLR, fg=TEXT_DIM, font=(FONT_UI, 9),
              relief=tk.FLAT, padx=16, pady=5,
              cursor="hand2").pack(pady=(0, 12))  # cancels the export and closes the dialog
