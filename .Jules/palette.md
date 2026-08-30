## 2026-08-30 - Instant Tooltip Dismissal on Control Click
**Learning:** Tooltip popups in desktop applications can persist and obscure newly opened modals, dropdown menus, or active UI elements when a user clicks an interactive control. Furthermore, global application settings require a unified toggle flag across all ToolTip instances.
**Action:** Bind `<ButtonPress>` on controls to instantly unschedule pending tooltip timers and destroy active tooltip windows upon click, and support global `ToolTip.enabled` class toggles.
