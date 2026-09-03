# Bolt's Journal

## 2026-09-03 - [Tkinter Canvas IPC Optimization]
**Learning:** Querying Tkinter canvas item properties via `itemcget()` across the Tcl/Tk C-bridge inside high-frequency animation loops (e.g. 20 FPS canvas updates) incurs massive IPC overhead when called on thousands of empty cells.
**Action:** Cache canvas item text state locally in Python lists during grid creation (`_rebuild_pool`), checking Python state (`if col_texts[row_idx] != ""`) to avoid `itemcget` Tcl IPC round-trips for inactive cells while allowing dynamic attributes (such as fading colors) on active cells to update normally.
