## 2026-08-25 - Desktop GUI ToolTip Keyboard Navigation Accessibility
**Learning:** In Tkinter / CustomTkinter desktop applications, binding tooltips only to `<Enter>` and `<Leave>` mouse hover events excludes keyboard users tabbing through interactive controls.
**Action:** Always bind `<FocusIn>` to show and `<FocusOut>` to hide tooltips alongside `<Enter>`/`<Leave>`, and ensure tooltip positioning falls back to widget coordinates (`winfo_rootx()`, `winfo_rooty()`) when mouse pointer coordinates fall outside the widget bounds.
