"""
core/autoplot.py — Automatic airfoil contour detection and point placement.

Provides:
  auto_plot(app)               — main entry point; dispatches to cv2 or PIL detector
  detect_contour_cv2(app, n)   — OpenCV-based contour detection (preferred)
  detect_contour_pil(app, n)   — Pillow-based fallback contour detection
  outline_from_mask(app, mask, n) — converts a boolean silhouette mask to sampled (x,y) points
"""

import numpy as np
from tkinter import messagebox
from PIL import ImageFilter

from core.calibration import img_px_to_real

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

def auto_plot(app):
    """
    Detects the airfoil outline in the loaded image and places points along it.
    Uses the OpenCV detector when available, falls back to the PIL detector otherwise.
    Point count is taken from app.density_var.
    """
    if not app.image_orig:
        return   # nothing to do if no image is loaded

    n_pts = app.density_var.get()   # number of points the user requested via the density slider
    pts   = (detect_contour_cv2(app, n_pts)
             if CV2_AVAILABLE
             else detect_contour_pil(app, n_pts))  # picks the better detector based on available libraries

    if not pts:
        messagebox.showinfo(
            "Auto Plot",
            "Could not detect a clear shape outline.\n"
            "Try adjusting density or plot manually."
        )  # informs the user when the image contrast is too low for automatic detection
        return

    app.coords = pts       # replaces any existing points with the newly detected outline
    app._draw_dots()
    app._draw_lines()
    app._refresh_table()

def detect_contour_cv2(app, n_pts):
    """
    Uses OpenCV Gaussian blur to compute local contrast and isolate the
    airfoil silhouette, then delegates to outline_from_mask for sampling.
    """
    arr  = np.array(app.image_orig.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY).astype(float)
    blur = cv2.GaussianBlur(gray.astype(np.float32), (41, 41), 0)
    lc   = blur - gray   # local contrast: high where dark airfoil pixels sit against a light background
    return outline_from_mask(app, lc > max(15.0, float(lc.max()) * 0.15), n_pts)

def detect_contour_pil(app, n_pts):
    """
    Pillow-based fallback contour detector used when OpenCV is not installed.
    Applies the same blur-contrast method as the cv2 version using PIL filters.
    """
    gray    = app.image_orig.convert("L")
    blurred = gray.filter(ImageFilter.GaussianBlur(radius=20))
    arr     = np.array(gray).astype(float)
    lc      = np.array(blurred).astype(float) - arr   # local contrast mask (same logic as cv2 version)
    thresh  = max(15.0, lc.max() * 0.15)
    mask    = lc > thresh
    if not mask.any():
        mask = lc > 10.0   # lower fallback threshold when normal threshold finds nothing
    return outline_from_mask(app, mask, n_pts)

def outline_from_mask(app, mask, n_pts):
    """
    Converts a boolean 2-D silhouette mask into a list of (x, y) real-world
    coordinate pairs sampled around the airfoil outline.

    For each image column within the detected span, records the top and bottom
    airfoil pixel. Fills gaps via linear interpolation, then separates the
    resulting contour into upper and lower surfaces. Points are sampled using a
    curvature-weighted distribution so the leading edge and trailing edge receive
    denser coverage.
    """
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return []   # mask is empty — no airfoil detected

    col_top, col_bot = {}, {}
    for x, y in zip(xs.tolist(), ys.tolist()):
        if x not in col_top or y < col_top[x]: col_top[x] = y   # highest (smallest Y) airfoil pixel per column
        if x not in col_bot or y > col_bot[x]: col_bot[x] = y   # lowest (largest Y) airfoil pixel per column

    x_cols = sorted(col_top.keys())
    x_min, x_max = x_cols[0], x_cols[-1]

    ft, fb = dict(col_top), dict(col_bot)
    # Fill columns that were entirely skipped by linearly interpolating from neighbours
    for x in range(x_min, x_max + 1):
        if x not in ft:
            p = max((xx for xx in x_cols if xx < x), default=None)
            n = min((xx for xx in x_cols if xx > x), default=None)
            if p and n:
                t = (x - p) / (n - p)
                ft[x] = col_top[p] + t * (col_top[n] - col_top[p])   # interpolated top pixel
                fb[x] = col_bot[p] + t * (col_bot[n] - col_bot[p])   # interpolated bottom pixel

    xa    = sorted(ft.keys())
    upper = [(float(x), float(ft[x])) for x in xa]           # upper surface: leftmost to rightmost
    lower = [(float(x), float(fb[x])) for x in reversed(xa)] # lower surface: rightmost to leftmost (closes loop)

    def _curvature_sample(curve, n_want):
        """
        Samples *n_want* points from *curve* weighted by local curvature.
        High-curvature regions (like the leading edge nose) receive more points;
        flat mid-chord regions receive fewer. Gaussian boosts at both endpoints
        ensure the leading edge and trailing edge are always well-sampled.
        """
        if len(curve) <= n_want:
            return curve   # nothing to downsample

        arr = np.array(curve)
        dx  = np.gradient(arr[:, 0])
        dy  = np.gradient(arr[:, 1])
        ddx = np.gradient(dx)
        ddy = np.gradient(dy)
        denom = (dx ** 2 + dy ** 2) ** 1.5
        denom[denom < 1e-8] = 1e-8
        kappa = np.abs(dx * ddy - dy * ddx) / denom   # curvature magnitude at each point

        # Endpoint boost: forces dense sampling at LE (index 0) and TE (index -1)
        n  = len(kappa)
        t_arr = np.linspace(0, 1, n)
        sigma  = 0.05
        ep_boost = (np.exp(-t_arr ** 2 / (2 * sigma ** 2)) +
                    np.exp(-(1 - t_arr) ** 2 / (2 * sigma ** 2)))  # bell curves centred on each endpoint
        weight = 1.0 + 20.0 * kappa / (kappa.max() + 1e-8) + 15.0 * ep_boost  # combines curvature and endpoint weight

        arc     = np.cumsum(weight)
        arc     = (arc - arc[0]) / (arc[-1] - arc[0])   # normalised cumulative weight used as a sampling grid
        targets = np.linspace(0, 1, n_want)
        indices = np.clip(np.searchsorted(arc, targets), 0, len(curve) - 1)

        seen = set(); result = []
        for i in indices:
            if i not in seen:
                seen.add(i); result.append(curve[i])
        return result

    # 55/45 split gives the upper surface (including the nose) slightly more points
    h_upper = max(3, (n_pts * 55) // 100)
    h_lower = max(3, n_pts - h_upper)

    sampled = _curvature_sample(upper, h_upper) + _curvature_sample(lower, h_lower)
    return [img_px_to_real(app, float(px), float(py)) for px, py in sampled]  # converts all sampled pixels to real-world coordinates
