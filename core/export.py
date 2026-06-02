"""
core/export.py — All data export and import operations for NW Airtrace.

Provides:
  export_csv(app)              — saves coordinates to a standard CSV file
  export_solidworks(app)       — cleans, resamples, and saves a SolidWorks XYZ curve file
  smooth_spline_resample(pts)  — per-surface smoothing spline + curvature-adaptive walk
  preview_export_curve(app)    — draws the export curve and sample points on the canvas
  download_image(app)          — saves the image annotated with plotted points
  copy_to_clipboard(app)       — copies all coordinate pairs to the OS clipboard
  upload_curve_file(app)       — loads a .dat / .txt coordinate file onto the canvas
  maybe_normalize(app, pts)    — applies normalise and flip-Y settings to a point list
"""

import csv
import os
import math
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np
from PIL import ImageDraw

from constants import (
    ACCENT, ACCENT2, GREEN, YELLOW, PURPLE, LINE_CLR,
    FONT_UI, TEXT_DIM, PANEL
)
from core.calibration import real_to_canvas, real_to_img_px
from ui.dialogs import show_export_dialog

def maybe_normalize(app, pts):
    """
    Applies the Normalize (0–1) and Flip-Y settings to *pts*.
    Normalise scales all coordinates so the largest axis span maps to 0–1.
    Flip-Y inverts the Y axis so aerodynamic positive-up convention is used.
    Returns a new list; the originals in app.coords are never modified here.
    """
    if not pts:
        return pts

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    scale = max((max_x - min_x) or 1, (max_y - min_y) or 1)   # uniform scale preserves aspect ratio

    if app.normalize_var.get():
        result = [((x - min_x) / scale, (y - min_y) / scale) for x, y in pts]  # shifts and scales to 0–1 range
    else:
        result = list(pts)   # no normalisation — return a copy of the raw coordinates

    flip = app.flip_y_var is not None and app.flip_y_var.get()
    if flip:
        out_ys     = [p[1] for p in result]
        y_min_r, y_max_r = min(out_ys), max(out_ys)
        result = [(x, y_max_r - y + y_min_r) for x, y in result]  # mirrors Y values so up is positive
    return result

def export_csv(app):
    """
    Prompts the user for a file path and writes all plotted coordinates to a
    standard CSV with columns: index, x, y.
    Normalise and Flip-Y settings are applied before writing.
    """
    if not app.coords:
        messagebox.showinfo("Export", "No points to export.")
        return

    path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        initialfile="shape_coords.csv"
    )  # save-as dialog so the user can choose a filename and location
    if not path:
        return

    display = (maybe_normalize(app, app.coords)
               if app.normalize_var and app.normalize_var.get()
               else app.coords)  # apply display settings before writing

    try:
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["index", "x", "y"])   # header row
            for i, (x, y) in enumerate(display):
                w.writerow([i + 1, f"{x:.6f}", f"{y:.6f}"])   # one row per point with 6 decimal places
        messagebox.showinfo("Export", f"Saved {len(display)} points to:\n{path}")
    except Exception as e:
        messagebox.showerror("Export Failed", f"Could not write file:\n{e}")

def copy_to_clipboard(app):
    """
    Copies all coordinates to the OS clipboard as tab-separated X\\tY pairs,
    one point per line. Ready to paste into Excel, a text editor, or another tool.
    """
    if not app.coords:
        messagebox.showinfo("Copy", "No points to copy.")
        return

    display = (maybe_normalize(app, app.coords)
               if app.normalize_var and app.normalize_var.get()
               else app.coords)
    lines = [f"{x:.6f}\t{y:.6f}" for x, y in display]
    text  = "\n".join(lines)
    app.clipboard_clear()
    app.clipboard_append(text)   # writes to the OS clipboard
    app._set_status(f"Copied {len(lines)} points to clipboard  (tab-separated X  Y)")

def download_image(app):
    """
    Saves the loaded image to disk with calibration markers, the connecting
    curve, and numbered dots drawn at their original image resolution.
    """
    if not app.image_orig:
        messagebox.showinfo("Download", "No image loaded.")
        return

    path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG image", "*.png")],
        initialfile="annotated_shape.png"
    )
    if not path:
        return

    out  = app.image_orig.copy().convert("RGB")   # working copy so the original is not modified
    draw = ImageDraw.Draw(out)
    iw, ih = out.size

    # Calibration rings with coordinate labels
    for (px, py), (rx, ry) in zip(app.cal_points_px, app.cal_points_real):
        r = max(6, iw // 120)
        x0, y0 = int(px) - r, int(py) - r
        x1, y1 = int(px) + r, int(py) + r
        draw.ellipse([x0, y0, x1, y1], outline="#f95f4f",
                     width=max(2, iw // 300))   # draws a rose ring at each calibration point
        draw.text((int(px) + r + 2, int(py) - r),
                  f"({rx:.2f},{ry:.2f})", fill="#f95f4f")   # labels the ring with real-world coordinates

    # Connecting line through all plotted points
    if len(app.coords) >= 2:
        line_pts = [
            (int(ix), int(iy))
            for ix, iy in (real_to_img_px(app, rx, ry) for rx, ry in app.coords)
        ]
        draw.line(line_pts, fill="#4f9cf9", width=max(2, iw // 400))   # blue curve connecting all points

    # Numbered dots at each point
    dot_r = max(4, iw // 160)
    for i, (rx, ry) in enumerate(app.coords):
        px_, py_ = real_to_img_px(app, rx, ry)
        px_, py_ = int(px_), int(py_)
        draw.ellipse([px_ - dot_r, py_ - dot_r, px_ + dot_r, py_ + dot_r],
                     fill="#4f9cf9", outline="white")   # blue filled dot with white border at each point
        draw.text((px_ + dot_r + 2, py_ - dot_r), str(i + 1), fill="#e8eaf0")  # index label beside each dot

    try:
        out.save(path, "PNG")
        messagebox.showinfo("Download", f"Annotated image saved to:\n{path}")
    except Exception as e:
        messagebox.showerror("Download Failed", f"Could not save image:\n{e}")

def upload_curve_file(app):
    """
    Opens a .dat or .txt coordinate file and loads the (X, Y) pairs directly
    onto the canvas, bypassing the image and calibration workflow.
    Handles the 'mm' suffix written by the SolidWorks exporter.
    """
    path = filedialog.askopenfilename(
        title="Upload Curve File",
        filetypes=[("Curve files", "*.dat *.txt"), ("All files", "*.*")]
    )
    if not path:
        return

    pts    = []
    errors = []
    try:
        with open(path, "r") as f:
            for lineno, raw in enumerate(f, 1):
                line   = raw.strip()
                if not line:
                    continue
                tokens = [t.replace("mm", "").strip() for t in line.split()]  # strips 'mm' unit suffix
                nums   = []
                for t in tokens:
                    try:
                        nums.append(float(t))
                    except ValueError:
                        pass   # skips non-numeric tokens (e.g. header lines)
                if len(nums) >= 2:
                    pts.append((nums[0], nums[1]))   # takes the first two numbers as X and Y
                elif len(nums) == 1:
                    errors.append(lineno)            # line with only one number is incomplete
    except Exception as e:
        messagebox.showerror("Upload Failed", f"Could not read file:\n{e}")
        return

    if not pts:
        messagebox.showerror(
            "Upload Failed",
            "No valid coordinate pairs found.\nExpected format: X Y  or  Xmm Ymm"
        )
        return

    if errors:
        messagebox.showwarning("Upload Warning",
                               f"Skipped {len(errors)} line(s) with incomplete data.")

    # Clear current image and calibration, then load the file points
    app.image_orig       = None
    app.image_tk         = None
    app._last_image_path = None
    app.calibrated       = False
    app.transform        = None
    app.cal_points_px    = []
    app.cal_points_real  = []
    app.zoom_var.set(1.0)
    app._pan_offset_x    = 0
    app._pan_offset_y    = 0
    app.canvas.delete("image", "cal_mark")
    app.cal_status.config(text="Not calibrated (file upload)", fg=TEXT_DIM)

    app.coords = pts   # loads the parsed points directly into the coordinate store
    app.update_idletasks()
    _fit_uploaded_curve(app)    # fits the coordinate extents to the visible canvas area
    app._draw_dots()
    app._draw_lines()
    app._refresh_table()
    app._set_status(f"Loaded {len(pts)} points from {os.path.basename(path)}")

def _fit_uploaded_curve(app):
    """
    Scales and centres the coordinate viewport so an uploaded curve fills
    85% of the canvas. Sets the Y-flip flag so aerodynamic coordinates
    (positive-up) display correctly on the downward-Y canvas.
    """
    if not app.coords:
        return

    xs = [p[0] for p in app.coords]
    ys = [p[1] for p in app.coords]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = (max_x - min_x) or 1.0
    span_y = (max_y - min_y) or 1.0

    cw = app.canvas.winfo_width()  or 800
    ch = app.canvas.winfo_height() or 600
    margin = 0.85
    sf = min(cw * margin / span_x, ch * margin / span_y)   # scale so the larger axis fits within 85% of canvas

    cx = (cw - span_x * sf) / 2.0   # centres the curve horizontally
    cy = (ch - span_y * sf) / 2.0   # centres the curve vertically

    app.scale_factor   = sf
    app._upload_y_flip = True     # tells real_to_canvas to invert Y for uploaded files
    app._upload_y_max  = max_y
    app._upload_y_min  = min_y
    app.img_offset     = (cx - min_x * sf, cy - min_y * sf)  # offset so min_x maps to left margin
    app._pan_offset_x  = 0
    app._pan_offset_y  = 0
    app.calibrated     = False

def preview_export_curve(app):
    """
    Draws the smoothed export curve (green line) and the actual export sample
    points (yellow squares) on the canvas so the user can verify quality before saving.
    Calling again clears the preview.
    """
    if getattr(app, "_preview_visible", False):
        app.canvas.delete("preview_curve")
        app.canvas.delete("preview_dot")
        app.canvas.delete("preview_label")
        app._preview_visible = False
        app._set_status("Export preview cleared.")
        return

    if not app.coords:
        messagebox.showinfo("Preview", "No points to preview.")
        return

    # Run the same Step 1 cleanup as export_solidworks to get the cleaned point list
    pts = list(maybe_normalize(app, app.coords))
    max_x = max(p[0] for p in pts)
    if max_x > 1e-9:
        pts = [(x / max_x, y / max_x) for x, y in pts]  # normalises chord to exactly 1.0

    te_idx = max(range(len(pts)), key=lambda i: pts[i][0])
    pts = pts[te_idx:] + pts[:te_idx]   # rotates the list so it starts at the trailing edge
    pts.append(pts[0])
    pts[0]  = (1.0, pts[0][1])
    pts[-1] = (1.0, pts[-1][1])   # anchors both endpoints to exactly x = 1.0

    seen = set(); tmp = []
    for p in pts:
        k = (round(p[0], 8), round(p[1], 8))
        if k not in seen:
            seen.add(k); tmp.append(p)
    if tmp[0] != tmp[-1]:
        tmp.append(tmp[0])
    pts = tmp

    cleaned = []; i = 0
    while i < len(pts) - 1:
        p = pts[i]
        if abs(p[1]) <= 1e-8:
            cleaned.append(p); i += 1
            while i < len(pts) - 1 and abs(pts[i][1]) <= 1e-8:
                i += 1
        else:
            cleaned.append(p); i += 1
    cleaned.append(pts[-1])
    pts = cleaned

    body = pts[1:-1]
    body = [p for p in body if abs(p[0] - 1.0) > 1e-8]   # removes extra x=1 points from the body
    x0_pts = [p for p in body if abs(p[0]) < 1e-8]
    if len(x0_pts) > 1:
        keep_y = max(p[1] for p in x0_pts)
        body = [p for p in body if not (abs(p[0]) < 1e-8 and abs(p[1] - keep_y) > 1e-8)]
    pts = [pts[0]] + body + [pts[-1]]

    # Run the smooth spline resampler to get both the fine curve and the export sample points
    pts_a    = np.array(pts, dtype=float)
    le_idx_a = int(np.argmin(pts_a[:, 0]))
    lower_raw = pts_a[:le_idx_a + 1]
    upper_raw = pts_a[le_idx_a:]

    def _dedup_x(arr):
        seen = {}
        for row in arr:
            k = round(row[0], 8)
            if k not in seen: seen[k] = row[1]
        xs = sorted(seen.keys())
        return np.array([[x, seen[x]] for x in xs])

    lower = _dedup_x(lower_raw[np.argsort(lower_raw[:, 0])])
    upper = _dedup_x(upper_raw[np.argsort(upper_raw[:, 0])])

    def _make_x_grid(x_min, x_max, n, le_frac=0.15, w=8):
        le_end = x_min + (x_max - x_min) * le_frac
        n_le   = int(n * w / (w + 1))
        n_rest = n - n_le
        return np.concatenate([
            np.linspace(x_min, le_end, n_le,   endpoint=False),
            np.linspace(le_end, x_max, n_rest)
        ])  # denser grid near the leading edge where curvature is highest

    FINE_N = 2000
    try:
        from scipy.interpolate import UnivariateSpline
        HAS_SCIPY = True
    except ImportError:
        HAS_SCIPY = False

    if HAS_SCIPY and len(lower) >= 4 and len(upper) >= 4:
        spl_l = UnivariateSpline(lower[:, 0], lower[:, 1], k=3, s=1e-5, ext=3)
        spl_u = UnivariateSpline(upper[:, 0], upper[:, 1], k=3, s=1e-5, ext=3)
        xl = _make_x_grid(lower[0, 0], lower[-1, 0], FINE_N)
        xu = _make_x_grid(upper[0, 0], upper[-1, 0], FINE_N)
        lower_fine = np.stack([xl[::-1], spl_l(xl)[::-1]], axis=1)
        upper_fine = np.stack([xu,        spl_u(xu)],       axis=1)
    else:
        xl = _make_x_grid(lower[0, 0], lower[-1, 0], FINE_N)
        xu = _make_x_grid(upper[0, 0], upper[-1, 0], FINE_N)
        lower_fine = np.stack([xl[::-1], np.interp(xl, lower[:, 0], lower[:, 1])[::-1]], axis=1)
        upper_fine = np.stack([xu,        np.interp(xu, upper[:, 0], upper[:, 1])],       axis=1)

    fine = np.vstack([lower_fine, upper_fine[1:]])   # joins lower and upper into a single fine contour

    dx  = np.gradient(fine[:, 0]);  dy  = np.gradient(fine[:, 1])
    ddx = np.gradient(dx);           ddy = np.gradient(dy)
    denom  = (dx ** 2 + dy ** 2) ** 1.5
    denom  = np.where(denom < 1e-12, 1e-12, denom)
    kappa  = np.abs(dx * ddy - dy * ddx) / denom   # curvature at each fine point
    kn     = kappa / (kappa.max() + 1e-12)
    MIN_D  = 0.005; MAX_D = 0.025
    desired = MIN_D + (MAX_D - MIN_D) * (1.0 - kn)  # tighter spacing in high-curvature regions

    sampled = [tuple(fine[0])]; last_i = 0; arc_acc = 0.0
    for i in range(1, len(fine)):
        step = np.hypot(fine[i, 0] - fine[i - 1, 0], fine[i, 1] - fine[i - 1, 1])
        arc_acc += step
        if arc_acc >= min(desired[last_i], desired[i]):
            sampled.append(tuple(fine[i])); last_i = i; arc_acc = 0.0
    if sampled[-1] != tuple(fine[-1]):
        sampled.append(tuple(fine[-1]))   # ensures the last point is always included

    raw_pts     = list(maybe_normalize(app, app.coords))
    chord_scale = max(p[0] for p in raw_pts) if raw_pts else 1.0  # maps preview back to real-world scale

    app.canvas.delete("preview_curve")
    app.canvas.delete("preview_dot")
    app.canvas.delete("preview_label")

    # Green smooth curve from the 2000-point fine contour
    canvas_fine = []
    for fx, fy in fine:
        cx, cy = real_to_canvas(app, fx * chord_scale, fy * chord_scale)
        canvas_fine.extend([cx, cy])
    if len(canvas_fine) >= 4:
        app.canvas.create_line(
            *canvas_fine, fill="#4caf82", width=2,
            smooth=False, tags="preview_curve"
        )  # smooth green curve showing the interpolated export shape

    # Yellow squares at the actual export sample positions
    for sx, sy in sampled:
        cx, cy = real_to_canvas(app, sx * chord_scale, sy * chord_scale)
        app.canvas.create_rectangle(
            cx - 3, cy - 3, cx + 3, cy + 3,
            fill=YELLOW, outline="", tags="preview_dot"
        )  # yellow dot at each point that will appear in the export file

    cw = app.canvas.winfo_width() or 800
    app.canvas.create_text(
        cw - 12, 14, anchor=tk.NE,
        text=f"  EXPORT PREVIEW  {len(sampled)} pts  |  run again to clear  ",
        fill="#4caf82", font=(FONT_UI, 9, "bold"),
        tags="preview_label"
    )  # legend in top-right corner of the canvas

    app._preview_visible = True
    app._set_status(
        f"Export preview  |  {len(sampled)} export pts  |  "
        "Green = smooth curve  ·  Yellow = export points  |  "
        "File > Preview again to clear"
    )

def export_solidworks(app):
    """
    Processes the plotted coordinates into a SolidWorks-ready XYZ curve file.

    Step 1 — Normalises and cleans the coordinate list:
      - Scales chord to exactly x=1 at the trailing edge.
      - Reorders the sequence to start/end at the TE (x=1).
      - Removes exact duplicates, collapses consecutive near-zero-y runs,
        and strips extra x=0 points that would cause spline overshoot at the LE.

    Step 2 — Smooth per-surface spline resampling:
      - Fits a smoothing B-spline on each surface separately.
      - Uses a parametric arc for the nose to avoid Runge oscillations.
      - Applies a curvature-adaptive greedy walk to place export points
        densely at corners and sparsely on flat mid-chord regions.

    Step 3 — Shows the export dialog so the user can choose format and save.
    """
    if not app.coords:
        messagebox.showinfo("Export", "No points to export.")
        return

    pts = list(maybe_normalize(app, app.coords))

    max_x = max(p[0] for p in pts)
    if max_x > 1e-9:
        pts = [(x / max_x, y / max_x) for x, y in pts]   # chord normalised to x=1 at TE

    te_idx = max(range(len(pts)), key=lambda i: pts[i][0])
    pts = pts[te_idx:] + pts[:te_idx]   # rotates list so TE comes first
    pts.append(pts[0])
    pts[0]  = (1.0, pts[0][1])
    pts[-1] = (1.0, pts[-1][1])   # forces both endpoints to exactly x=1.0

    # A: deduplicate by (x, y) rounded to 8 decimal places
    seen = set(); tmp = []
    for p in pts:
        k = (round(p[0], 8), round(p[1], 8))
        if k not in seen:
            seen.add(k); tmp.append(p)
    if tmp[0] != tmp[-1]:
        tmp.append(tmp[0])
    pts = tmp

    # B: collapse consecutive near-y=0 runs (flat lower-surface cluster near TE)
    cleaned = []; i = 0
    while i < len(pts) - 1:
        p = pts[i]
        if abs(p[1]) <= 1e-8:
            cleaned.append(p); i += 1
            while i < len(pts) - 1 and abs(pts[i][1]) <= 1e-8:
                i += 1
        else:
            cleaned.append(p); i += 1
    cleaned.append(pts[-1])
    pts = cleaned

    # C: remove extra x=1 points from the body, and all x=0 (LE calibration) points
    body = pts[1:-1]
    body = [p for p in body if abs(p[0] - 1.0) > 1e-8]   # drops extra TE duplicates in the body
    body = [p for p in body if abs(p[0]) > 1e-8]          # drops all x=0 calibration artefacts
    pts  = [pts[0]] + body + [pts[-1]]
    before_inflect = len(pts)

    if len(pts) < 4:
        messagebox.showerror(
            "Export",
            "Too few unique points after cleanup (need at least 4).\n"
            "Add more points or check your curve."
        )
        return

    pts = smooth_spline_resample(pts)

    # Enforce minimum point spacing so SolidWorks does not reject the file
    MIN_DIST = 0.005
    filtered = [pts[0]]
    for p in pts[1:-1]:
        d = math.hypot(p[0] - filtered[-1][0], p[1] - filtered[-1][1])
        if d >= MIN_DIST:
            filtered.append(p)   # only keeps points that are far enough apart
    last_d = math.hypot(pts[-1][0] - filtered[-1][0], pts[-1][1] - filtered[-1][1])
    if last_d >= MIN_DIST:
        filtered.append(pts[-1])
    pts = filtered

    removed = before_inflect - len(pts)   # number of points removed during cleanup

    if pts[-1] != pts[0]:
        pts[-1] = pts[0]   # force-close the loop so TE start and end are identical

    show_export_dialog(app, pts, removed)  # opens the format picker and saves the file on confirm

def smooth_spline_resample(raw_pts):
    """
    Fits a smoothing cubic B-spline on the lower and upper surfaces separately,
    builds a dense parametric arc through the leading-edge nose region, then
    applies a curvature-adaptive greedy walk to select export sample points.

    Per-surface fitting avoids oscillations at the LE/TE junctions that occur
    when a single spline is fit around the full closed curve.
    Falls back to linear interpolation if scipy is unavailable.

    Returns a list of (x, y) tuples ready to write to the export file.
    """
    try:
        from scipy.interpolate import UnivariateSpline, CubicSpline
        HAS_SCIPY = True
    except ImportError:
        HAS_SCIPY = False

    pts_a  = np.array(raw_pts, dtype=float)
    le_idx = int(np.argmin(pts_a[:, 0]))   # LE is the point with the smallest x (leftmost)

    lower_raw = pts_a[:le_idx + 1]   # lower surface: from TE to LE
    upper_raw = pts_a[le_idx:]       # upper surface: from LE to TE

    def dedup_x(arr):
        """Sorts by x and removes duplicate x values, keeping the first occurrence."""
        arr_s = arr[np.argsort(arr[:, 0])]
        seen = {}
        for row in arr_s:
            k = round(row[0], 8)
            if k not in seen: seen[k] = row[1]
        xs = sorted(seen.keys())
        return np.array([[x, seen[x]] for x in xs])

    lower = dedup_x(lower_raw)
    upper = dedup_x(upper_raw)

    FINE_N    = 2000    # number of evaluation points per surface on the flat region
    NOSE_N    = 800     # number of evaluation points on the parametric nose arc
    chord     = float(lower[-1, 0] - lower[0, 0])
    LE_CUT    = max(lower[1, 0] * 2.0, chord * 0.06)  # chord fraction where x-parameterisation hands off to nose arc

    if HAS_SCIPY and len(lower) >= 4 and len(upper) >= 4:
        s     = 1e-5
        spl_l = UnivariateSpline(lower[:, 0], lower[:, 1], k=3, s=s, ext=3)  # smoothing cubic spline for lower surface
        spl_u = UnivariateSpline(upper[:, 0], upper[:, 1], k=3, s=s, ext=3)  # smoothing cubic spline for upper surface

        # Flat regions: dense x-parameterised evaluation from LE_CUT to TE
        xl_flat = np.linspace(LE_CUT, lower[-1, 0], FINE_N)
        xu_flat = np.linspace(LE_CUT, upper[-1, 0], FINE_N)
        lower_flat = np.stack([xl_flat[::-1], spl_l(xl_flat)[::-1]], axis=1)   # reversed so it runs TE→LE_CUT
        upper_flat = np.stack([xu_flat,        spl_u(xu_flat)],       axis=1)   # forward: LE_CUT→TE

        # Nose arc: parametric cubic spline through the LE region to handle high curvature
        n_nose_ctrl = max(8, int(len(lower[lower[:, 0] <= LE_CUT]) * 3))
        xl_nose = np.linspace(lower[0, 0], LE_CUT, n_nose_ctrl)
        xu_nose = np.linspace(upper[0, 0], LE_CUT, n_nose_ctrl)
        nose_x  = np.concatenate([xl_nose[::-1], xu_nose[1:]])   # arc goes LE_CUT(lower) → tip → LE_CUT(upper)
        nose_y  = np.concatenate([spl_l(xl_nose)[::-1], spl_u(xu_nose)[1:]])
        nose_ctrl = np.stack([nose_x, nose_y], axis=1)

        segs  = np.hypot(np.diff(nose_ctrl[:, 0]), np.diff(nose_ctrl[:, 1]))
        segs  = np.where(segs < 1e-10, 1e-10, segs)
        t_arc = np.concatenate([[0.0], np.cumsum(segs)])
        t_arc /= t_arc[-1]   # arc-length parameter runs 0→1 along the nose arc

        cs_x      = CubicSpline(t_arc, nose_ctrl[:, 0])
        cs_y      = CubicSpline(t_arc, nose_ctrl[:, 1])
        t_fine    = np.linspace(0.0, 1.0, NOSE_N)
        nose_fine = np.stack([cs_x(t_fine), cs_y(t_fine)], axis=1)  # densely evaluated parametric nose

        fine = np.vstack([lower_flat, nose_fine, upper_flat])  # joins lower flat + nose + upper flat

    else:
        # Fallback: simple linear interpolation without scipy
        xl = np.linspace(lower[0, 0], lower[-1, 0], FINE_N)
        xu = np.linspace(upper[0, 0], upper[-1, 0], FINE_N)
        lower_fine = np.stack([xl[::-1], np.interp(xl, lower[:, 0], lower[:, 1])[::-1]], axis=1)
        upper_fine = np.stack([xu,        np.interp(xu, upper[:, 0], upper[:, 1])],       axis=1)
        fine = np.vstack([lower_fine, upper_fine[1:]])

    # Curvature-adaptive greedy walk: selects export points from the fine contour
    dx  = np.gradient(fine[:, 0])
    dy  = np.gradient(fine[:, 1])
    ddx = np.gradient(dx)
    ddy = np.gradient(dy)
    denom = (dx ** 2 + dy ** 2) ** 1.5
    denom = np.where(denom < 1e-12, 1e-12, denom)
    kappa = np.abs(dx * ddy - dy * ddx) / denom    # local curvature at each fine point
    kn    = kappa / (kappa.max() + 1e-12)

    MIN_D   = 0.003   # minimum allowed arc-length step — safely above SolidWorks' floor
    MAX_D   = 0.025   # maximum step on flat mid-chord sections
    desired = MIN_D + (MAX_D - MIN_D) * (1.0 - kn)  # step inversely proportional to curvature

    result  = [tuple(fine[0])]
    last_i  = 0
    arc_acc = 0.0
    for i in range(1, len(fine)):
        step    = np.hypot(fine[i, 0] - fine[i - 1, 0], fine[i, 1] - fine[i - 1, 1])
        arc_acc += step
        thr     = min(desired[last_i], desired[i])
        if arc_acc >= thr:
            result.append(tuple(fine[i]))
            last_i  = i
            arc_acc = 0.0

    if result[-1] != tuple(fine[-1]):
        result.append(tuple(fine[-1]))   # always ends at the exact last fine point

    return result
