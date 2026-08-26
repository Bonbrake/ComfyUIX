## 2026-08-26 - Parameterized List Arguments for OS File Explorer Subprocess Execution
**Vulnerability:** Constructing system shell commands via string interpolation (e.g. `f'explorer /select,"{fpath}"'`) allows potential argument and command injection if file paths contain shell metacharacters or quotes, and crashes on non-Windows platforms.
**Learning:** `subprocess.Popen` without `shell=True` expects list arguments to avoid shell string parsing, but on non-Windows OSes calling `explorer` will fail.
**Prevention:** Use list arguments (e.g. `["explorer", "/select,", norm_path]`) and platform checks (`_pf.system() == "Windows"` vs `"Darwin"` vs `"Linux"`) in file reveal helpers.
