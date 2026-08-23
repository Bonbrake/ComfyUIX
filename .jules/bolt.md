# Bolt's Journal - Critical Learnings

## 2026-08-23 - Eliminating Redundant Syscalls and Path Parsing in File Walkers
**Learning:** In Python media gallery scanners and file discovery logic using `os.walk`, invoking `os.path.isfile()` on every returned file item causes thousands of unnecessary `os.stat` system calls. Furthermore, repeatedly parsing path strings with `os.path.splitext()`, `os.path.basename()`, and `os.path.dirname()` inside tight file-scanning loops introduces noticeable CPU and string parsing overhead.
**Action:** When walking directory trees with `os.walk`, treat `files` items as regular files directly without redundant `os.path.isfile()` checks. Extract extension and directory context once per file/directory, and pass pre-parsed string parameters (`ext`, `base`, `parent`) to downstream filtering helper functions.
