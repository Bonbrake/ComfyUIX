## 2026-08-25 - Pruning `os.walk` Subtrees and Eliminating `os.path.relpath` in Gallery Scanning

**Learning:** `os.path.relpath()` calls `os.path.abspath()` on both arguments for every directory in `os.walk()`, adding significant filesystem overhead. In addition, continuing `os.walk()` when exceeding `max_depth` traverses deeper directory trees unnecessarily unless `dirs` is modified in-place (`dirs.clear()`).

**Action:** Calculate directory depth using fast string slicing on normalized paths (`root[base_len:].strip(os.sep).count(os.sep)`), and prune `dirs` in-place (`dirs.clear()`) at `max_depth` to prevent `os.walk()` from descending into deep subdirectories.
