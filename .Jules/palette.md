## 2026-08-30 - Recursive Event Binding for Compound Tkinter/CTk Tooltips
**Learning:** In complex CustomTkinter/Tkinter widgets containing nested child elements (labels, frames, icons), standard single-widget `<Enter>` and `<Leave>` bindings fail when the mouse hovers over child components. Furthermore, tooltips can linger if a user clicks an interactive element unless `<ButtonPress>` dismisses them.
**Action:** Always recursively traverse and bind `<Enter>`, `<Leave>`, and `<ButtonPress>` events across all child widgets when attaching tooltip behaviors to compound UI components.
