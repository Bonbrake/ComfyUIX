## 2026-08-29 - Media Directory Traversal Fast Pruning

**Learning:** `os.walk` recurses into all child subdirectories off-disk regardless of whether filtering happens later in the loop body. Also, `os.path.relpath()` calculates full relative paths via string normalizations and relative calculations on every single directory node. Converting relative paths to absolute paths (`os.path.abspath`) before string splitting `len(abs_path.split(os.sep))` allows calculating relative depth accurately while pruning subdirectories (`dirs[:] = []`) at `max_depth`.

**Action:** When scanning nested directory trees with a maximum depth constraint, always prune `dirs[:] = []` in `os.walk` at `max_depth` and calculate relative depth using canonical `os.path.abspath` component counts to achieve 3-4x speedups without edge-case bugs.
