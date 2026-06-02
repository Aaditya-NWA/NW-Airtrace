"""
core/calibration.py — Calibration logic and coordinate-transform methods for NW AirTrace.

Provides:
  auto_calibrate(app)            — detects LE/TE endpoints and sets transform automatically
  detect_airfoil_endpoints(app)  — image analysis to find leftmost/rightmost airfoil edge pixels
  start_calibration(app)         — enters manual calibration mode
  handle_cal_click(app, cx, cy)  — records a calibration click on the canvas
  finish_calibration(app)        — computes and stores the pixel-to-real transform
  reset_calibration(app)         — clears all calibration data
  img_px_to_real(app, ix, iy)    — converts image-space pixels to real-world coordinates
  px_to_real(app, cx, cy)        — converts canvas pixels to real-world coordinates
  real_to_canvas(app, rx, ry)    — converts real-world coordinates to canvas pixels
  real_to_img_px(app, rx, ry)    — converts real-world coordinates back to image pixels
"""

import math
import tkinter as tk
from tkinter import messagebox
from PIL import ImageFilter
import numpy as np

from constants import ACCENT, ACCENT2, CAL_CLR, GREEN, FONT_UI, PANEL
from ui.dialogs import ask_real_point

def auto_calibrate(app):
    """
    Automatically detects the leading-edge (LE) and trailing-edge (TE) pixel
    positions from the loaded image, assigns them to real coordinates (0,0)
    and (1,0), then draws calibration markers on the canvas.
    Falls back to image corners when detection finds no airfoil pixels.
    """
    le_px, te_px = detect_airfoil_endpoints(app)
    iw, ih = app.image_orig.size
    if le_px is None:
        le_px = (0.0, float(ih - 1))    # fallback: left edge of image
        te_px = (float(iw - 1), float(ih - 1))  # fallback: right edge of image

    app.cal_points_px   = [le_px, te_px]         # stores the two calibration pixel locations
    app.cal_points_real = [(0.0, 0.0), (1.0, 0.0)]  # assigns LE = (0,0) and TE = (1,0) in real space
    finish_calibration(app, silent=True)          # computes the transform without showing a confirmation dialog

    for (px, py), lbl in zip(app.cal_points_px, ["LE (0,0)", "TE (1,0)"]):
        cx_ = px * app.scale_factor + app.img_offset[0]  # converts the calibration image pixel to a canvas x position
        cy_ = py * app.scale_factor + app.img_offset[1]  # converts the calibration image pixel to a canvas y position
        r = 7
        app.canvas.create_oval(cx_ - r, cy_ - r, cx_ + r, cy_ + r,
                               outline=CAL_CLR, fill="", width=2, tags="cal_mark")  # draws the calibration ring on canvas
        app.canvas.create_text(cx_, cy_ - 14, text=lbl,
                               fill=CAL_CLR, font=(FONT_UI, 8, "bold"), tags="cal_mark")  # labels LE and TE above each ring

    app.cal_status.config(text="Auto-cal: LE(0,0)  TE(1,0)", fg=GREEN)  # updates sidebar status to confirm auto-cal succeeded

def detect_airfoil_endpoints(app):
    """
    Analyses the loaded image to find the leftmost (LE) and rightmost (TE)
    column positions where the airfoil silhouette appears.
    Uses Gaussian blur contrast to isolate the dark wing shape from the background.
    Returns ((le_x, le_y), (te_x, te_y)) image-space pixel tuples, or (None, None).
    """
    gray    = app.image_orig.convert("L")                  # converts image to greyscale for edge analysis
    blurred = gray.filter(ImageFilter.GaussianBlur(radius=20))  # blurs to separate the airfoil from fine texture
    arr     = np.array(gray).astype(float)
    bg      = np.array(blurred).astype(float)
    lc      = bg - arr                                      # local contrast: high where dark shape sits on light bg
    thresh  = max(15.0, lc.max() * 0.15)                   # adaptive threshold: 15% of peak contrast, minimum 15
    mask    = lc > thresh                                   # boolean mask of pixels that are part of the airfoil
    ys, xs  = np.where(mask)

    if len(xs) == 0:
        return None, None   # no airfoil pixels detected — caller will use image-corner fallback

    col_top, col_bot = {}, {}
    for x, y in zip(xs.tolist(), ys.tolist()):
        if x not in col_top or y < col_top[x]: col_top[x] = y  # top-most airfoil pixel in each column
        if x not in col_bot or y > col_bot[x]: col_bot[x] = y  # bottom-most airfoil pixel in each column

    x_cols = sorted(col_top.keys())
    le_x = x_cols[0];  le_y = (col_top[le_x] + col_bot[le_x]) / 2.0   # LE: leftmost column, midpoint between top/bottom
    te_x = x_cols[-1]; te_y = (col_top[te_x] + col_bot[te_x]) / 2.0   # TE: rightmost column, midpoint between top/bottom
    return (float(le_x), float(le_y)), (float(te_x), float(te_y))

def start_calibration(app):
    """
    Switches the app into manual calibration mode. The next two clicks on
    the canvas will be treated as calibration reference points. The user
    will be prompted for the real-world coordinates of each click.
    """
    if not app.image_orig:
        messagebox.showinfo("No Image", "Open an image first.")
        return
    app.mode = "calibrate"                     # tells the click handler to route clicks to handle_cal_click
    app.cal_points_px   = []
    app.cal_points_real = []
    app.canvas.delete("cal_mark")
    app.mode_lbl.config(text="MODE: CALIBRATE — click point 1", fg=ACCENT2)  # mode pill shows calibration state
    app.canvas.configure(cursor="tcross")      # crosshair cursor signals to the user that clicks are for calibration
    app.cal_status.config(text="Click point 1 on image…", fg=ACCENT2)

def handle_cal_click(app, cx, cy):
    """
    Called when the user clicks on the canvas in calibration mode.
    Records the clicked pixel and prompts for the corresponding real coordinate.
    After two clicks, finishes the calibration.
    """
    n = len(app.cal_points_px) + 1   # which calibration point is being placed (1 or 2)
    ox, oy = app.img_offset
    sf     = app.scale_factor

    if app.image_orig:
        iw, ih = app.image_orig.size
        if not (ox <= cx <= ox + iw * sf and oy <= cy <= oy + ih * sf):
            return   # ignores clicks that land outside the image boundary

    rx, ry = ask_real_point(app, n)   # asks the user to type the real-world coordinates for this point
    if rx is None:
        return   # user cancelled the dialog

    img_x = (cx - ox) / sf   # converts the canvas click to an image-space X pixel
    img_y = (cy - oy) / sf   # converts the canvas click to an image-space Y pixel
    app.cal_points_px.append((img_x, img_y))
    app.cal_points_real.append((rx, ry))

    r = 6
    app.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                           outline=CAL_CLR, fill="", width=2, tags="cal_mark")  # draws a ring at the clicked location
    app.canvas.create_text(cx + 12, cy - 12,
                           text=f"P{n} ({rx:.3f},{ry:.3f})",
                           fill=CAL_CLR, font=(FONT_UI, 8), tags="cal_mark")   # labels the point with its real coordinates

    if len(app.cal_points_px) == 2:
        finish_calibration(app)    # both reference points collected — compute the transform
    else:
        app.mode_lbl.config(text="MODE: CALIBRATE — click point 2", fg=ACCENT2)  # prompts for the second point
        app.cal_status.config(text="Click point 2 on image…", fg=ACCENT2)

def finish_calibration(app, silent=False):
    """
    Computes the pixel-to-real-world affine scale transform from the two
    recorded calibration reference points and stores it in app.transform.
    *silent=True* suppresses the confirmation dialog (used by auto_calibrate).
    """
    app.mode = "plot"                             # returns to normal point-plotting mode
    app.mode_lbl.config(text=" PLOT ", bg=ACCENT, fg=PANEL)
    app.canvas.configure(cursor="crosshair")

    (px1, py1), (px2, py2) = app.cal_points_px
    (rx1, ry1), (rx2, ry2) = app.cal_points_real
    dpx = px2 - px1;  dpy = py2 - py1
    drx = rx2 - rx1;  dry = ry2 - ry1
    dist_px = math.hypot(dpx, dpy)
    dist_r  = math.hypot(drx, dry)

    if dist_px < 1e-6:
        if not silent:
            messagebox.showerror("Calibration Error", "Points are too close.")
        return

    xs = drx / dpx if abs(dpx) > 1e-6 else dist_r / dist_px  # X scale: real units per pixel on the X axis
    ys = dry / dpy if abs(dpy) > 1e-6 else dist_r / dist_px  # Y scale: real units per pixel on the Y axis

    app.transform = {
        "px_origin": (px1, py1),  # image-pixel position of the first calibration point
        "r_origin":  (rx1, ry1),  # real-world position of the first calibration point
        "x_scale":   xs if abs(xs) > 1e-9 else dist_r / dist_px,  # pixel-to-real scale along X
        "y_scale":   ys if abs(ys) > 1e-9 else dist_r / dist_px,  # pixel-to-real scale along Y
    }
    app.calibrated = True   # enables coordinate conversion from pixel to real-world units

    if not silent:
        app.cal_status.config(text="✓ Calibrated!", fg=GREEN)  # updates sidebar to confirm successful calibration
    app._refresh_table()   # recalculates all displayed coordinates using the new transform

def reset_calibration(app):
    """Clears all calibration data and returns the app to uncalibrated state."""
    app.calibrated      = False    # disables real-world coordinate conversion
    app.transform       = None
    app.cal_points_px   = []
    app.cal_points_real = []
    app.canvas.delete("cal_mark")  # removes all calibration marker rings and labels from the canvas
    app.cal_status.config(text="Calibration reset", fg="#F59E0B")  # shows amber warning in sidebar
    app._refresh_table()           # recalculates coordinates without the old transform

def img_px_to_real(app, img_x, img_y):
    """
    Converts image-space pixel coordinates (img_x, img_y) to real-world
    coordinates using the stored calibration transform.
    Returns (img_x, img_y) unchanged when not calibrated.
    """
    if not app.calibrated:
        return img_x, img_y   # no transform available — return raw pixel coordinates
    t    = app.transform
    px0, py0 = t["px_origin"]
    rx0, ry0 = t["r_origin"]
    return (rx0 + (img_x - px0) * t["x_scale"],   # applies X offset + scale to get real-world X
            ry0 + (img_y - py0) * t["y_scale"])    # applies Y offset + scale to get real-world Y

def px_to_real(app, cx, cy):
    """
    Converts canvas pixel coordinates (cx, cy) to real-world coordinates
    by first removing the image offset and scale, then applying the calibration.
    """
    ox, oy = app.img_offset
    sf     = app.scale_factor
    return img_px_to_real(app, (cx - ox) / sf, (cy - oy) / sf)  # undoes canvas scaling before calibration transform

def real_to_canvas(app, rx, ry):
    """
    Converts real-world coordinates (rx, ry) to canvas pixel coordinates
    for drawing dots, lines, and calibration markers on screen.
    Handles the Y-flip needed when a file was uploaded without an image.
    """
    ox, oy = app.img_offset
    sf     = app.scale_factor

    if not app.calibrated:
        if getattr(app, "_upload_y_flip", False):
            y_max = app._upload_y_max
            y_min = app._upload_y_min
            return rx * sf + ox, (y_max - ry + y_min) * sf + oy  # inverts Y so uploaded curves display right-side up
        return rx * sf + ox, ry * sf + oy   # direct scaling when no calibration and no flip

    t    = app.transform
    px0, py0 = t["px_origin"]
    rx0, ry0 = t["r_origin"]
    img_x = px0 + (rx - rx0) / t["x_scale"]   # reverses the X calibration to get image-pixel X
    img_y = py0 + (ry - ry0) / t["y_scale"]   # reverses the Y calibration to get image-pixel Y
    return img_x * sf + ox, img_y * sf + oy    # scales image pixels to canvas pixels including pan offset

def real_to_img_px(app, rx, ry):
    """
    Converts real-world coordinates (rx, ry) back to image-space pixel
    coordinates, used when annotating the downloaded image.
    Returns (rx, ry) unchanged when not calibrated.
    """
    if not app.calibrated:
        return rx, ry   # no transform — pixel and real coordinates are the same
    t    = app.transform
    px0, py0 = t["px_origin"]
    rx0, ry0 = t["r_origin"]
    return (px0 + (rx - rx0) / t["x_scale"],   # reverses X scale to get image-pixel column
            py0 + (ry - ry0) / t["y_scale"])    # reverses Y scale to get image-pixel row
