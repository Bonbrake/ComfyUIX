## 2026-09-05 - Dismissible Tooltips for Keyboard Accessibility
**Learning:** In Tkinter/CTk desktop apps, tooltip popups created using override-redirected `Toplevel` windows can remain stuck on screen during rapid mouse clicks or keyboard navigation if they only respond to `<Leave>` events.
**Action:** Always bind `<Escape>` and `<ButtonPress>` on both the source widget and the tooltip window itself to allow immediate dismissal via keyboard or click.
