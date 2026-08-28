## 2026-08-28 - PySide6 QPainter Inner Loop Object Allocations
**Learning:** Instantiating `QColor`, `QPen`, and `QFont` inside PySide6 `paintEvent` inner loops (such as matrix rain cell trails rendered at ~33 FPS) creates ~26,000 temporary C++ wrapper objects per second, causing significant GC pressure and frame rendering latency.
**Action:** Pre-allocate static UI fonts/colors in `__init__`, cache trail step `QColor` instances by `(step, length, r, g, b)`, pass `QColor` directly to `p.setPen()`, and inline inner-loop helper methods.
