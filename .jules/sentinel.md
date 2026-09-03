## 2026-09-03 - Command Injection in Explorer Subprocess Calls
**Vulnerability:** String-formatted user file paths passed directly to `subprocess.Popen(f'explorer /select,"{fpath}"')` allowing command injection/msparse flags if paths contain special characters or quotes.
**Learning:** Windows Explorer reveals via `subprocess.Popen` must pass arguments as an explicit vector list `["explorer", f"/select,{os.path.normpath(fpath)}"]`.
**Prevention:** Always use argument lists/vectors for `subprocess.Popen` and `subprocess.run` calls rather than formatted command strings.
