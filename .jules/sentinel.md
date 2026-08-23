## 2026-08-23 - Model Downloader Path Traversal
**Vulnerability:** `DownloadTask` and `download_custom_url` in `model_downloader.py` used `model_info["filename"]` or user-supplied `custom_name` directly in `os.path.join(dest_dir, filename)` without path sanitization, allowing arbitrary file writes outside `dest_dir` via `../` sequences.
**Learning:** External model metadata and user custom names can contain path traversal sequences (`../`, `..\`) or absolute paths that break out of the target model destination directory.
**Prevention:** Always sanitize filenames using `os.path.basename(filename.replace("\\", "/"))` and validate that `dest_path.startswith(os.path.abspath(dest_dir))` before constructing download paths.
