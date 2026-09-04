## 2026-09-04 - Icon-Only Button Tooltips
**Learning:** Icon-only action buttons (like folder reveal 📁 and delete 🗑 in media cards) lack immediate visual description. Adding CTk `ToolTip` hover wrappers ensures explicit action context without cluttering tight card layouts.
**Action:** Always wrap icon-only CTk buttons with `ToolTip(btn, ("Title", "Description"))` to maintain high accessibility and user confidence.
