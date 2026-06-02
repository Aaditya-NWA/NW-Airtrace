"""
core/canvas.py — Canvas drawing, event handling, image rendering, and interaction logic.

All methods receive the ShapePlotter instance as *app* and operate on
app.canvas, app.coords, app.image_orig, app.scale_factor, app.img_offset,
and the other state attributes defined in app.py.

Provides:
  draw_grid, draw_dots, draw_lines, redraw_all, redraw_cal_marks
  hit_test, hit_test_segment
  on_click, on_right_click, on_motion, on_drag, on_release
  on_resize, on_zoom, on_scroll, on_nudge, on_canvas_delete
  toggle_pan_mode
  close_shape, rotate_to_horizontal
  undo_point, push_undo
  select_all, clear_selection, delete_selected_from_table, table_right_click
  on_tree_select, jump_to_selected_point
  render_image, fit_image_to_canvas, fit_image_to_canvas_and_render
  render_or_redraw, refit_and_redraw
  zoom_step, toggle_fullscreen
  refresh_table, refresh_status
  clear_image, clear_all
"""

import math
import copy
import csv
import os
import tkinter as tk
from tkinter import messagebox

import numpy as np
from PIL import Image, ImageTk

from constants import (
    ACCENT, ACCENT2, GREEN, YELLOW, TEXT_DIM, DOT_CLR, DOT_HOVER,
    LINE_CLR, GRID_CLR, CAL_CLR, PANEL, FONT_UI, FONT_MONO
)
from core.calibration import px_to_real, real_to_canvas
from core.export import maybe_normalize

def draw_grid(app):
    """Draws a light background grid on the canvas at 60px intervals."""
    app.canvas.delete("grid")
    w = app.canvas.winfo_width()  or 800
    h = app.canvas.winfo_height() or 600
    for x in range(0, w, 60):
        app.canvas.create_line(x, 0, x, h, fill=GRID_CLR, tags="grid")   # vertical grid line
    for y in range(0, h, 60):
        app.canvas.create_line(0, y, w, y, fill=GRID_CLR, tags="grid")   # horizontal grid line
    app.canvas.tag_lower("grid")   # sends the grid behind all other canvas items

def draw_dots(app):
    """
    Redraws all plotted points as circles on the canvas.
    Point 0 is drawn in gold; hovered points in amber; all others in indigo.
    The currently selected (nudge) point gets a green ring.
    Duplicate closing point (first == last in a closed shape) is skipped.
    """
    app.canvas.delete("dot")
    if not app.coords:
        return

    indices = list(range(1, len(app.coords))) + [0]   # draws point 0 last so it renders on top
    for i in indices:
        rx, ry = app.coords[i]
        if (i == len(app.coords) - 1
                and app.coords[0] == app.coords[-1]
                and len(app.coords) > 1):
            continue   # skips the closing duplicate so the first dot is not obscured

        px, py = real_to_canvas(app, rx, ry)
        r      = 6 if i == 0 else 5
        color  = DOT_HOVER if i == app.hovered_idx else ("#f9c74f" if i == 0 else DOT_CLR)

        app.canvas.create_oval(px - r, py - r, px + r, py + r,
                               fill=color, outline="white", width=1, tags="dot")  # filled circle for the point

        if i == app.nudge_idx:
            nr = r + 5
            app.canvas.create_oval(px - nr, py - nr, px + nr, py + nr,
                                   outline=GREEN, fill="", width=2, tags="dot")   # green ring marks the keyboard-nudgeable point

        app.canvas.create_text(px + 8, py - 8, text=str(i + 1),
                               fill=TEXT_DIM, font=(FONT_UI, 7), tags="dot")     # small index number next to each dot

def draw_lines(app):
    """
    Draws the connecting curve through all plotted points.
    Uses create_polygon for a closed shape (no gap at the last segment),
    and create_line for an open curve (preserves exact point positions).
    """
    app.canvas.delete("line", "seg_hint")
    if len(app.coords) < 2:
        return

    closed = len(app.coords) > 2 and app.coords[0] == app.coords[-1]  # shape is closed when first == last

    pts = []
    for rx, ry in app.coords:
        px, py = real_to_canvas(app, rx, ry)
        pts.extend([px, py])

    if closed:
        app.canvas.create_polygon(*pts, outline=LINE_CLR, fill="",
                                  width=1.5, smooth=False, tags="line")  # polygon gives a true closed loop without a gap
    else:
        app.canvas.create_line(*pts, fill=LINE_CLR, width=1.5,
                               smooth=False, tags="line")   # smooth=False ensures the line passes exactly through every point

    app.canvas.tag_lower("line")
    app.canvas.tag_lower("image")
    app.canvas.tag_lower("grid")

def redraw_all(app):
    """Redraws dots, lines, and calibration markers in the correct z-order."""
    draw_dots(app)
    draw_lines(app)
    redraw_cal_marks(app)

def redraw_cal_marks(app):
    """
    Redraws calibration rings and labels at their current canvas positions.
    Called after zoom/pan changes move the image so marks stay aligned.
    """
    app.canvas.delete("cal_mark")
    labels = ["LE (0,0)", "TE (1,0)"]
    for (px, py), lbl in zip(app.cal_points_px, labels):
        cx_ = px * app.scale_factor + app.img_offset[0]   # converts stored image pixel to current canvas position
        cy_ = py * app.scale_factor + app.img_offset[1]
        r   = 7
        app.canvas.create_oval(cx_ - r, cy_ - r, cx_ + r, cy_ + r,
                               outline=CAL_CLR, fill="", width=2, tags="cal_mark")  # rose ring at the cal point
        app.canvas.create_text(cx_, cy_ - 14, text=lbl,
                               fill=CAL_CLR, font=(FONT_UI, 8, "bold"), tags="cal_mark")  # label above the ring

def hit_test(app, cx, cy, radius=9):
    """
    Returns the index of the plotted point within *radius* canvas pixels of (cx, cy),
    or None if no point is close enough. Used to detect hover and click targets.
    """
    for i, (rx, ry) in enumerate(app.coords):
        px, py = real_to_canvas(app, rx, ry)
        if math.hypot(cx - px, cy - py) < radius:
            return i
    return None

def hit_test_segment(app, cx, cy, threshold=8):
    """
    Returns (insert_index, mid_px, mid_py) if the cursor is within *threshold*
    pixels of a line segment between two consecutive points, else None.
    Used to show the green + insert-point indicator on segment hover.
    """
    if len(app.coords) < 2:
        return None

    best_dist = threshold
    best      = None
    n         = len(app.coords)
    closed    = n > 2 and app.coords[0] == app.coords[-1]
    pairs     = [(i, (i + 1) % n) for i in range(n - 1)]
    if closed:
        pairs.append((n - 1, 0))

    for i, j in pairs:
        ax, ay = real_to_canvas(app, *app.coords[i])
        bx, by = real_to_canvas(app, *app.coords[j])
        dx, dy  = bx - ax, by - ay
        seg_len2 = dx * dx + dy * dy
        if seg_len2 < 1e-9:
            continue
        t  = max(0.0, min(1.0, ((cx - ax) * dx + (cy - ay) * dy) / seg_len2))
        nx_, ny_ = ax + t * dx, ay + t * dy
        dist = math.hypot(cx - nx_, cy - ny_)
        if dist < best_dist:
            best_dist = dist
            mid_px    = (ax + bx) / 2.0
            mid_py    = (ay + by) / 2.0
            best      = (j, mid_px, mid_py)   # insert before index j (after index i)

    return best

def on_click(app, event):
    """
    Left-click handler:
    - In pan mode: records pan start position.
    - In calibrate mode: delegates to calibration click handler.
    - If clicking an existing point: begins a drag.
    - If clicking a line segment: inserts a new point at that position.
    - Otherwise: appends a new point at the clicked canvas position.
    """
    cx, cy = event.x, event.y
    if app.pan_mode:
        app._pan_start_x, app._pan_start_y = cx, cy
        return
    if app.mode == "calibrate":
        from core.calibration import handle_cal_click
        handle_cal_click(app, cx, cy)
        return

    idx = hit_test(app, cx, cy)
    if idx is not None:
        app.drag_idx  = idx       # records which point is being dragged
        app.nudge_idx = idx       # also selects it for keyboard nudge
        draw_dots(app)
        return

    seg = hit_test_segment(app, cx, cy)
    if seg is not None:
        insert_at, _, _ = seg
        push_undo(app)
        rx, ry = px_to_real(app, cx, cy)
        app.coords.insert(insert_at, (rx, ry))   # inserts point between the two nearest neighbours
        app.nudge_idx = insert_at
        draw_dots(app)
        draw_lines(app)
        refresh_table(app)
        app._set_status(f"Point inserted at position {insert_at + 1}")
        return

    push_undo(app)
    rx, ry = px_to_real(app, cx, cy)
    app.coords.append((rx, ry))     # appends a new point at the clicked location
    app.nudge_idx = len(app.coords) - 1
    draw_dots(app)
    draw_lines(app)
    refresh_table(app)

def on_right_click(app, event):
    """
    Right-click on an existing point removes it and adjusts nudge_idx to stay valid.
    Right-click on empty canvas space is ignored.
    """
    if app.pan_mode:
        return
    idx = hit_test(app, event.x, event.y)
    if idx is not None:
        push_undo(app)
        app.coords.pop(idx)
        if app.nudge_idx == idx:
            app.nudge_idx = None
        elif app.nudge_idx is not None and app.nudge_idx > idx:
            app.nudge_idx -= 1
        draw_dots(app)
        draw_lines(app)
        refresh_table(app)
        app._set_status(f"Point {idx + 1} deleted")

def on_motion(app, event):
    """
    Mouse-move handler: updates the coordinate readout in the toolbar,
    highlights the hovered point, and shows a green + hint when hovering
    over a line segment (indicating a point can be inserted there).
    """
    cx, cy = event.x, event.y
    rx, ry = px_to_real(app, cx, cy)
    norm   = maybe_normalize(app, [(rx, ry)])
    nx, ny = norm[0] if norm else (rx, ry)
    app.coord_lbl.config(text=f"x: {nx:.4f}   y: {ny:.4f}")   # live coordinate readout follows the cursor

    if app.pan_mode:
        return

    prev_hovered  = app.hovered_idx
    app.hovered_idx = hit_test(app, cx, cy)

    app.canvas.delete("seg_hint")
    if app.hovered_idx is None and not app.pan_mode:
        seg = hit_test_segment(app, cx, cy)
        if seg is not None:
            _, mx, my = seg
            r = 5
            app.canvas.create_oval(mx - r, my - r, mx + r, my + r,
                                   fill=GREEN, outline="white",
                                   width=1, tags="seg_hint")   # green dot shows where the new point will be inserted
            app.canvas.create_text(mx + 10, my - 10, text="+",
                                   fill=GREEN, font=(FONT_UI, 10, "bold"),
                                   tags="seg_hint")            # plus sign indicates a point can be added here
            app.canvas.configure(cursor="plus")
        else:
            app.canvas.configure(cursor="crosshair")   # default plotting cursor
    elif app.hovered_idx is not None:
        app.canvas.configure(cursor="fleur")   # move cursor when hovering over a draggable point

    if prev_hovered != app.hovered_idx:
        draw_dots(app)   # redraws dots to update the hover highlight colour

def on_drag(app, event):
    """
    B1-Motion handler: pans the view in pan mode, or moves the dragged point
    to the cursor position in plot mode.
    """
    if app.pan_mode:
        dx = event.x - app._pan_start_x
        dy = event.y - app._pan_start_y
        app._pan_start_x, app._pan_start_y = event.x, event.y
        if app.image_orig:
            app._pan_offset_x += dx   # accumulates pan displacement for image rendering
            app._pan_offset_y += dy
        else:
            ox, oy = app.img_offset
            app.img_offset = (ox + dx, oy + dy)   # directly shifts the coordinate viewport when no image is loaded
        render_or_redraw(app)
        return
    if app.drag_idx is None:
        return
    app.coords[app.drag_idx] = px_to_real(app, event.x, event.y)   # updates the dragged point to follow the cursor
    draw_dots(app)
    draw_lines(app)
    refresh_table(app)

def on_release(app, event):
    """Mouse button release clears the active drag index."""
    app.drag_idx = None

def on_resize(app, event):
    """Canvas resize redraws the grid and re-renders everything at the new size."""
    draw_grid(app)
    render_or_redraw(app)

def on_scroll(app, event):
    """
    Scroll-wheel zoom: zooms the canvas toward the cursor position so the
    point under the cursor stays fixed while the rest of the view scales.
    Adjusts the pan offset to compensate for the zoom centre shift.
    """
    delta  = 1 if (event.num == 4 or getattr(event, "delta", 0) > 0) else -1
    cx, cy = event.x, event.y
    old_z  = app.zoom_var.get()
    new_z  = max(0.2, min(8.0, old_z * (1.12 if delta > 0 else 0.89)))  # 12% zoom-in or 11% zoom-out per scroll step
    app.zoom_var.set(round(new_z, 3))
    if hasattr(app, "zoom_lbl"):
        app.zoom_lbl.config(text=f"{new_z:.2f}×")   # updates the sidebar zoom label

    ratio  = new_z / old_z
    ox, oy = app.img_offset
    app._pan_offset_x += cx - ratio * (cx - ox) - ox   # shifts pan offset so the cursor-point stays fixed
    app._pan_offset_y += cy - ratio * (cy - oy) - oy

    if not app.image_orig:
        app.scale_factor = app.scale_factor * ratio
        app.img_offset   = (cx - ratio * (cx - ox), cy - ratio * (cy - oy))  # for upload-only mode, update offset directly
        app._pan_offset_x = 0
        app._pan_offset_y = 0

    render_or_redraw(app)

def on_zoom(app, _=None):
    """
    Called when the zoom slider moves. Refits the coordinate viewport around
    the canvas centre at the new zoom level (upload mode), or re-renders the
    image at the new scale (image mode).
    """
    if hasattr(app, "zoom_lbl"):
        app.zoom_lbl.config(text=f"{app.zoom_var.get():.2f}×")   # keeps the sidebar label in sync with the slider

    if not app.image_orig and app.coords:
        xs = [p[0] for p in app.coords]
        ys = [p[1] for p in app.coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = (max_x - min_x) or 1.0
        span_y = (max_y - min_y) or 1.0
        cw = app.canvas.winfo_width()  or 800
        ch = app.canvas.winfo_height() or 600
        base_sf = min(cw * 0.85 / span_x, ch * 0.85 / span_y)
        sf  = base_sf * app.zoom_var.get()   # applies the slider multiplier on top of the fit scale
        cx  = (cw - span_x * sf) / 2.0
        cy  = (ch - span_y * sf) / 2.0
        app.scale_factor  = sf
        app.img_offset    = (cx - min_x * sf, cy - min_y * sf)
        redraw_all(app)
    else:
        render_or_redraw(app)

def toggle_pan_mode(app):
    """
    Switches between pan/zoom mode and plot mode.
    Pan mode changes the cursor and mode pill; plot mode restores them.
    """
    app.pan_mode = app.pan_var.get()
    if app.pan_mode:
        app.canvas.configure(cursor="fleur")
        app.mode_lbl.config(text=" PAN ", bg=YELLOW, fg="#1E1F26")   # amber pill indicates pan mode is active
    else:
        cursor = "tcross" if app.mode == "calibrate" else "crosshair"
        app.canvas.configure(cursor=cursor)
        app.mode_lbl.config(text=" PLOT ", bg=ACCENT, fg=PANEL)      # returns to the normal indigo PLOT pill

def close_shape(app):
    """
    Appends a duplicate of the first point to the end of the coordinate list,
    creating a closed polygon. Skipped if the shape is already closed.
    """
    if app.coords and app.coords[0] != app.coords[-1]:
        app.coords.append(app.coords[0])   # closing point is the same real-world coordinate as point 0
        draw_dots(app)
        draw_lines(app)
        refresh_table(app)

def rotate_to_horizontal(app):
    """
    Rotates all coordinates so the chord line (LE→TE, i.e. min-x to max-x) is
    horizontal. Uses the angle from the leftmost to the rightmost point as the
    rotation angle and rotates everything by its negative around the LE.
    """
    if len(app.coords) < 2:
        messagebox.showinfo("Rotate", "Need at least 2 points.")
        return

    le = min(app.coords, key=lambda p: p[0])   # leading edge: leftmost point
    te = max(app.coords, key=lambda p: p[0])   # trailing edge: rightmost point

    x1, y1 = le
    x2, y2 = te
    angle_rad = math.atan2(y2 - y1, x2 - x1)
    angle_deg = math.degrees(angle_rad)

    cos_a, sin_a = math.cos(-angle_rad), math.sin(-angle_rad)
    rotated = []
    for rx, ry in app.coords:
        dx, dy = rx - x1, ry - y1
        rotated.append((cos_a * dx - sin_a * dy + x1,
                        sin_a * dx + cos_a * dy + y1))  # rotates each point around the LE by the negative chord angle
    app.coords = rotated
    app.angle_lbl.config(text=f"Rotated {angle_deg:+.2f}° → 0°")   # shows the applied rotation angle in the sidebar
    draw_dots(app)
    draw_lines(app)
    refresh_table(app)

def push_undo(app):
    """Saves a deep copy of the current coordinate list to the undo stack (max 50 entries)."""
    app._undo_stack.append(copy.deepcopy(app.coords))
    if len(app._undo_stack) > 50:
        app._undo_stack.pop(0)   # drops the oldest entry to cap memory usage

def undo_point(app):
    """
    Restores the previous coordinate state from the undo stack.
    Falls back to removing the last point when the stack is empty.
    """
    if app._undo_stack:
        app.coords = app._undo_stack.pop()   # restores the last saved state
    elif app.coords:
        app.coords.pop()   # fallback: just removes the most recently added point

    if app.nudge_idx is not None:
        if not app.coords:
            app.nudge_idx = None
        else:
            app.nudge_idx = min(app.nudge_idx, len(app.coords) - 1)   # clamps nudge index to valid range

    draw_dots(app)
    draw_lines(app)
    refresh_table(app)
    app._set_status("Undo")

def on_nudge(app, event):
    """
    Arrow-key nudge: moves the selected (nudge_idx) point by 1 or 10 canvas
    pixels depending on whether Shift is held. Converts the pixel offset back
    to real-world coordinates so the stored coordinate stays accurate.
    """
    if app.nudge_idx is None or not (0 <= app.nudge_idx < len(app.coords)):
        return

    step_px = 10 if "Shift" in event.keysym else 1   # Shift key gives a coarser 10-pixel step
    dx_px, dy_px = 0, 0
    if   "Left"  in event.keysym: dx_px = -step_px
    elif "Right" in event.keysym: dx_px =  step_px
    elif "Up"    in event.keysym: dy_px = -step_px
    elif "Down"  in event.keysym: dy_px =  step_px

    rx, ry = app.coords[app.nudge_idx]
    cx, cy = real_to_canvas(app, rx, ry)
    new_rx, new_ry = px_to_real(app, cx + dx_px, cy + dy_px)   # converts the pixel nudge back to real-world delta

    push_undo(app)
    app.coords[app.nudge_idx] = (new_rx, new_ry)
    draw_dots(app)
    draw_lines(app)
    refresh_table(app)

    direction = next((k for k in ("Left", "Right", "Up", "Down") if k in event.keysym), "")
    arrow     = {"Left": "←", "Right": "→", "Up": "↑", "Down": "↓"}.get(direction, "")
    prefix    = "Shift+" if step_px == 10 else ""
    app._set_status(
        f"Nudged pt {app.nudge_idx + 1}  "
        f"x:{new_rx:.5f}  y:{new_ry:.5f}  [{prefix}{arrow}]"
    )
    return "break"   # prevents arrow keys from scrolling the window while nudging

def on_canvas_delete(app, event=None):
    """
    Delete / Backspace key handler on the canvas:
    - Removes the hovered point if one is highlighted.
    - Otherwise removes the last plotted point.
    """
    if not app.coords and app.hovered_idx is None:
        return

    push_undo(app)
    if app.hovered_idx is not None and 0 <= app.hovered_idx < len(app.coords):
        removed = app.hovered_idx
        app.coords.pop(removed)
        app.hovered_idx = None
        if app.nudge_idx == removed:
            app.nudge_idx = None
        elif app.nudge_idx is not None and app.nudge_idx > removed:
            app.nudge_idx -= 1
        app._set_status("Point deleted")
    elif app.coords:
        app.coords.pop()
        if app.nudge_idx is not None and app.nudge_idx >= len(app.coords):
            app.nudge_idx = len(app.coords) - 1 if app.coords else None
        app._set_status("Last point removed")

    draw_dots(app)
    draw_lines(app)
    refresh_table(app)

def select_all(app):
    """Selects all rows in the coordinates table (Ctrl+A)."""
    for item in app.tree.get_children():
        app.tree.selection_add(item)   # adds every table row to the current selection

def clear_selection(app):
    """Clears all table row selections (Escape)."""
    app.tree.selection_remove(app.tree.get_children())
    app._selected.clear()

def delete_selected_from_table(app, event=None):
    """
    Deletes all points corresponding to the currently selected table rows.
    Adjusts nudge_idx so it remains valid after deletion. Removes in reverse
    index order so earlier indices are not invalidated by earlier deletions.
    """
    selected_items = app.tree.selection()
    if not selected_items:
        return

    push_undo(app)
    indices = sorted([app.tree.index(i) for i in selected_items], reverse=True)
    for idx in indices:
        if 0 <= idx < len(app.coords):
            app.coords.pop(idx)
            if app.nudge_idx is not None:
                if app.nudge_idx == idx:
                    app.nudge_idx = None
                elif app.nudge_idx > idx:
                    app.nudge_idx -= 1

    draw_dots(app)
    draw_lines(app)
    refresh_table(app)
    app._set_status(
        f"Deleted {len(indices)} point(s)  —  gap preserved, add a point or Close Shape to fill"
    )

def table_right_click(app, event):
    """Shows a context menu when the user right-clicks a row in the coordinates table."""
    row = app.tree.identify_row(event.y)
    if row:
        app.tree.selection_set(row)   # ensures the clicked row is selected before showing the menu

    sel = app.tree.selection()
    if not sel:
        return

    menu  = tk.Menu(app, tearoff=0, bg=PANEL, fg="#1E1F26",
                    activebackground=ACCENT, activeforeground=PANEL,
                    font=(FONT_UI, 10), relief=tk.FLAT, bd=0)
    count = len(sel)
    label = "Delete point" if count == 1 else f"Delete {count} points"
    menu.add_command(label=f"  {label}  ",
                     command=lambda: delete_selected_from_table(app))   # removes the selected points
    menu.add_separator()
    menu.add_command(label="  Jump to point on canvas  ",
                     command=lambda: jump_to_selected_point(app))       # pans canvas to centre on the selected point
    menu.add_separator()
    menu.add_command(label="  Copy to clipboard  ",
                     command=lambda: app._copy_to_clipboard())          # copies all coordinates to the clipboard
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()

def on_tree_select(app, event=None):
    """When a row is selected in the coordinates table, puts a nudge ring on that point."""
    sel = app.tree.selection()
    if not sel:
        return
    idx = app.tree.index(sel[0])
    if 0 <= idx < len(app.coords):
        app.nudge_idx = idx   # selects the corresponding point for keyboard nudge
        draw_dots(app)

def jump_to_selected_point(app):
    """
    Pans the canvas so the selected table row's point is centred in the viewport.
    Also activates the nudge ring on that point.
    """
    sel = app.tree.selection()
    if not sel:
        return
    idx = app.tree.index(sel[0])
    if not (0 <= idx < len(app.coords)):
        return

    rx, ry = app.coords[idx]
    cw = app.canvas.winfo_width()  or 800
    ch = app.canvas.winfo_height() or 600
    target_cx, target_cy = cw / 2, ch / 2   # desired canvas position: canvas centre
    px, py = real_to_canvas(app, rx, ry)     # current canvas position of the point

    ox, oy = app.img_offset
    app.img_offset     = (ox + target_cx - px, oy + target_cy - py)  # shifts offset so the point lands at centre
    app._pan_offset_x  = 0
    app._pan_offset_y  = 0
    app.nudge_idx      = idx   # activates the green nudge ring on the jumped-to point

    render_or_redraw(app)
    draw_dots(app)
    app._set_status(f"Jumped to point {idx + 1}  —  x:{rx:.5f}  y:{ry:.5f}")

def refresh_table(app):
    """
    Rebuilds the coordinates table from the current app.coords list.
    Applies the Normalize and Flip-Y settings before display.
    Also auto-saves a CSV beside the loaded image when one is open.
    """
    for row in app.tree.get_children():
        app.tree.delete(row)   # clears the existing table rows before repopulating

    display = maybe_normalize(app, app.coords) if app.coords else []
    for i, (x, y) in enumerate(display):
        app.tree.insert("", tk.END, values=(i + 1, f"{x:.5f}", f"{y:.5f}"))  # one row per point

    app.pt_count_lbl.config(text=f"{len(app.coords)} points")   # updates the point-count badge in the sidebar

    # Auto-save CSV beside the source image whenever coordinates change
    if getattr(app, "_last_image_path", None) and app.coords:
        base = os.path.splitext(app._last_image_path)[0]
        try:
            with open(base + "_coords.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["index", "x", "y"])
                for i, (x, y) in enumerate(display):
                    w.writerow([i + 1, f"{x:.6f}", f"{y:.6f}"])   # writes all coordinates at 6 decimal places
            if hasattr(app, "csv_lbl"):
                app.csv_lbl.config(text="CSV auto-saved", fg=GREEN)  # confirms the auto-save in the sidebar
        except Exception:
            pass   # silently ignores auto-save failures (e.g. read-only directory)

def refresh_status(app):
    """Updates the status bar with the current point count and calibration state."""
    n   = len(app.coords)
    cal = "Calibrated" if app.calibrated else "Not calibrated"
    app._set_status(f"{n} point(s)  |  {cal}")

def fit_image_to_canvas(app):
    """
    Sets the zoom slider so the loaded image fills 90% of the canvas at best fit.
    Does not render — call render_image afterwards.
    """
    cw = app.canvas.winfo_width()  or 800
    ch = app.canvas.winfo_height() or 600
    iw, ih = app.image_orig.size
    sf = min(cw / iw, ch / ih) * 0.90   # 90% fit leaves a small margin around the image
    app.zoom_var.set(max(0.2, min(8.0, round(sf, 2))))

def render_image(app):
    """
    Resizes the loaded image to the current zoom level, draws it centred on
    the canvas (adjusted for pan offset), and redraws all overlaid items.
    """
    if not app.image_orig:
        return

    cw = app.canvas.winfo_width()  or 800
    ch = app.canvas.winfo_height() or 600
    iw, ih = app.image_orig.size
    sf    = app.zoom_var.get()
    new_w = max(1, int(iw * sf))
    new_h = max(1, int(ih * sf))

    resized       = app.image_orig.resize((new_w, new_h), Image.LANCZOS)   # high-quality Lanczos downsampling
    app.image_tk  = ImageTk.PhotoImage(resized)

    base_ox = max(0, (cw - new_w) // 2)
    base_oy = max(0, (ch - new_h) // 2)
    ox      = int(base_ox + app._pan_offset_x)   # applies pan offset on top of the centring position
    oy      = int(base_oy + app._pan_offset_y)
    app.img_offset   = (ox, oy)
    app.scale_factor = sf

    app.canvas.delete("image")
    app.canvas.create_image(ox, oy, anchor=tk.NW,
                            image=app.image_tk, tags="image")  # places the resized image on the canvas
    app.canvas.tag_lower("image")
    app.canvas.tag_lower("grid")
    redraw_all(app)

def render_or_redraw(app):
    """Re-renders the image if one is loaded, or redraws the vector overlay only."""
    if app.image_orig:
        render_image(app)
    else:
        redraw_all(app)

def refit_and_redraw(app):
    """
    Recalculates the viewport so all uploaded coordinates fit in 85% of the canvas,
    then redraws the grid and all overlaid items.
    """
    if app.coords:
        xs = [p[0] for p in app.coords]
        ys = [p[1] for p in app.coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = (max_x - min_x) or 1.0
        span_y = (max_y - min_y) or 1.0
        cw = app.canvas.winfo_width()  or 800
        ch = app.canvas.winfo_height() or 600
        sf = min(cw * 0.85 / span_x, ch * 0.85 / span_y)   # fits the full coordinate extents inside 85% of the canvas
        cx = (cw - span_x * sf) / 2.0
        cy = (ch - span_y * sf) / 2.0
        app.scale_factor   = sf
        app.img_offset     = (cx - min_x * sf, cy - min_y * sf)
        app._pan_offset_x  = 0
        app._pan_offset_y  = 0
    draw_grid(app)
    redraw_all(app)

def fit_image_to_canvas_and_render(app):
    """Fits the image (if loaded) and re-renders, or refits uploaded coordinates."""
    if app.image_orig:
        fit_image_to_canvas(app)
        render_image(app)
    else:
        refit_and_redraw(app)

def zoom_step(app, factor):
    """Applies a multiplicative zoom step and re-renders the canvas."""
    new_z = max(0.2, min(8.0, app.zoom_var.get() * factor))
    app.zoom_var.set(round(new_z, 3))
    if hasattr(app, "zoom_lbl"):
        app.zoom_lbl.config(text=f"{new_z:.2f}×")   # updates the sidebar zoom readout immediately
    render_or_redraw(app)

def toggle_fullscreen(app):
    """Toggles the application window between fullscreen and normal modes."""
    state = app.attributes("-fullscreen")
    app.attributes("-fullscreen", not state)   # F11 shortcut or View > Full Screen

def clear_image(app):
    """
    Removes the loaded image from the canvas (keeps plotted points).
    Asks for confirmation if an image is currently loaded.
    """
    if app.image_orig is not None:
        if not messagebox.askyesno(
                "Clear Image",
                "Remove the loaded image from the canvas?\n\nPlotted points will be kept.",
                icon="question"):
            return

    app.image_orig       = None
    app.image_tk         = None
    app._last_image_path = None
    app.calibrated       = False
    app.transform        = None
    app._upload_y_flip   = False
    app.canvas.delete("image")   # removes only the image canvas item

    if app.coords:
        refit_and_redraw(app)   # refits the viewport around the remaining coordinate points
    else:
        app.scale_factor   = 1.0
        app.img_offset     = (0, 0)
        app._pan_offset_x  = 0
        app._pan_offset_y  = 0
        draw_grid(app)

    app._set_status("Image cleared")

def clear_all(app):
    """
    Deletes all plotted points after asking for confirmation.
    This action cannot be undone.
    """
    if app.coords:
        if not messagebox.askyesno(
                "Clear All Points",
                f"Delete all {len(app.coords)} plotted points?\n\nThis cannot be undone.",
                icon="warning"):
            return

    app.coords.clear()
    app.nudge_idx = None
    app.canvas.delete("dot", "line", "seg_hint")   # removes all point and line canvas items
    refresh_table(app)
    app._set_status("All points cleared")
