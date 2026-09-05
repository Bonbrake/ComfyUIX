"""
gpu_doctor.py -- Hardware & GPU Compatibility Analyzer & Auto-Tuner
===================================================================
Automatically identifies installed GPU hardware (NVIDIA RTX/GTX, AMD Radeon,
Intel Arc/UHD/Iris Xe, Apple MPS, CPU fallback), queries total and free VRAM,
determines compute capabilities, and recommends the optimal ComfyUI launch
arguments for maximum performance without Out-Of-Memory (OOM) crashes.
"""

import os
import sys
import logging
import subprocess

logger = logging.getLogger(__name__)

_CACHED_GPU_HARDWARE = None


def detect_gpu_hardware(force_refresh: bool = False) -> dict:
    """Detect GPU hardware vendor, model, VRAM capacity, driver, and compute backend.
    
    Returns a structured dictionary with hardware specifications. Results are cached
    after the initial call to avoid repeated subprocess/WMI calls.
    """
    global _CACHED_GPU_HARDWARE
    if _CACHED_GPU_HARDWARE is not None and not force_refresh:
        res = dict(_CACHED_GPU_HARDWARE)
        # Refresh dynamic free VRAM if PyTorch CUDA is active
        try:
            import torch
            if torch.cuda.is_available():
                free_mem, _ = torch.cuda.mem_get_info()
                res["vram_free_mb"] = int(free_mem / (1024 * 1024))
        except Exception:
            pass
        return res

    info = {
        "vendor": "unknown",
        "name": "Unknown Graphics Device",
        "vram_total_mb": 0,
        "vram_free_mb": 0,
        "driver_version": "unknown",
        "cuda_available": False,
        "directml_available": False,
        "mps_available": False,
        "compute_capability": None,
        "recommended_args": ["--windows-standalone-build", "--fast", "--disable-auto-launch"],
        "recommended_mode": "normal",
        "status_note": "",
    }

    # 1. Try PyTorch native detection if available
    try:
        import torch
        if torch.cuda.is_available():
            info["vendor"] = "nvidia"
            info["cuda_available"] = True
            info["name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["vram_total_mb"] = int(props.total_memory / (1024 * 1024))
            info["compute_capability"] = f"{props.major}.{props.minor}"
            try:
                free_mem, _ = torch.cuda.mem_get_info()
                info["vram_free_mb"] = int(free_mem / (1024 * 1024))
            except Exception:
                pass
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            info["vendor"] = "apple"
            info["mps_available"] = True
            info["name"] = "Apple Silicon MPS"
    except Exception:
        pass

    # 2. Try nvidia-smi for NVIDIA GPUs if PyTorch didn't report or to get driver version
    if info["vendor"] in ("unknown", "nvidia"):
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            if r.returncode == 0 and r.stdout.strip():
                parts = [p.strip() for p in r.stdout.strip().split("\n")[0].split(",")]
                info["vendor"] = "nvidia"
                info["cuda_available"] = True
                if len(parts) > 0 and parts[0]:
                    info["name"] = parts[0]
                if len(parts) > 1 and parts[1].isdigit():
                    info["vram_total_mb"] = int(parts[1])
                if len(parts) > 2 and parts[2].isdigit():
                    info["vram_free_mb"] = int(parts[2])
                if len(parts) > 3 and parts[3]:
                    info["driver_version"] = parts[3]
        except Exception:
            pass

    # 3. Try fast Win32 EnumDisplayDevices before falling back to WMI / PowerShell
    if info["vendor"] == "unknown" and sys.platform == "win32":
        try:
            import ctypes
            if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32"):
                from ctypes import wintypes
                class DISPLAY_DEVICE(ctypes.Structure):
                    _fields_ = [
                        ("cb", wintypes.DWORD),
                        ("DeviceName", wintypes.WCHAR * 32),
                        ("DeviceString", wintypes.WCHAR * 128),
                        ("StateFlags", wintypes.DWORD),
                        ("DeviceID", wintypes.WCHAR * 128),
                        ("DeviceKey", wintypes.WCHAR * 128)
                    ]
                dd = DISPLAY_DEVICE()
                dd.cb = ctypes.sizeof(dd)
                idx = 0
                while ctypes.windll.user32.EnumDisplayDevicesW(None, idx, ctypes.byref(dd), 0):
                    d_name = dd.DeviceString
                    if d_name and "mirror" not in d_name.lower():
                        low_name = d_name.lower()
                        if any(k in low_name for k in ("nvidia", "geforce", "quadro", "rtx")):
                            info["name"] = d_name
                            info["vendor"] = "nvidia"
                            info["cuda_available"] = True
                            break
                        elif any(k in low_name for k in ("amd", "radeon")):
                            info["name"] = d_name
                            info["vendor"] = "amd"
                            info["directml_available"] = True
                            break
                        elif any(k in low_name for k in ("intel", "arc", "iris")):
                            info["name"] = d_name
                            info["vendor"] = "intel"
                            info["directml_available"] = True
                            break
                        elif "hyper-v" in low_name or "basic" in low_name or "generic" in low_name:
                            info["name"] = d_name
                            info["vendor"] = "generic"
                    idx += 1
        except Exception:
            pass

    # 4. If still unknown or non-NVIDIA, try Windows WMI (WMIC / PowerShell)
    if info["vendor"] == "unknown" and sys.platform == "win32":
        try:
            ps_cmd = 'Get-CimInstance Win32_VideoController | Select-Object -Property Name, AdapterRAM, DriverVersion | ConvertTo-Json'
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=3, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if r.returncode == 0 and r.stdout.strip():
                import json
                data = json.loads(r.stdout.strip())
                if isinstance(data, list):
                    # Pick dedicated GPU over integrated if multiple
                    devices = data
                else:
                    devices = [data]
                
                # Prioritize NVIDIA > AMD > Intel > Microsoft Basic
                sorted_devs = sorted(devices, key=lambda d: (
                    2 if "nvidia" in str(d.get("Name", "")).lower() else
                    2 if "radeon" in str(d.get("Name", "")).lower() or "amd" in str(d.get("Name", "")).lower() else
                    1 if "intel" in str(d.get("Name", "")).lower() or "arc" in str(d.get("Name", "")).lower() else 0
                ), reverse=True)
                
                if sorted_devs:
                    top = sorted_devs[0]
                    d_name = top.get("Name", "Generic GPU")
                    info["name"] = d_name
                    info["driver_version"] = str(top.get("DriverVersion", "unknown"))
                    ram_bytes = top.get("AdapterRAM", 0) or 0
                    if ram_bytes > 0:
                        info["vram_total_mb"] = int(ram_bytes / (1024 * 1024))
                    
                    low_name = d_name.lower()
                    if "nvidia" in low_name or "geforce" in low_name or "quadro" in low_name or "rtx" in low_name:
                        info["vendor"] = "nvidia"
                        info["cuda_available"] = True
                    elif "amd" in low_name or "radeon" in low_name:
                        info["vendor"] = "amd"
                        info["directml_available"] = True
                    elif "intel" in low_name or "arc" in low_name or "iris" in low_name:
                        info["vendor"] = "intel"
                        info["directml_available"] = True
                    else:
                        info["vendor"] = "generic"
        except Exception:
            pass

    # 5. Check for DirectML package availability
    try:
        import torch_directml
        info["directml_available"] = True
    except Exception:
        pass

    # 6. Compute recommended launch arguments & mode based on GPU & VRAM
    vram = info["vram_total_mb"]
    vendor = info["vendor"]
    args = ["--windows-standalone-build", "--fast", "--disable-auto-launch"]

    if vendor == "nvidia":
        if vram > 0 and vram <= 6144:  # <= 6GB VRAM
            args.append("--lowvram")
            info["recommended_mode"] = "lowvram (≤6GB)"
            info["status_note"] = f"NVIDIA {info['name']} ({vram}MB VRAM): Configured with --lowvram for stable memory management."
        elif vram > 6144 and vram <= 10240:  # 6GB - 10GB VRAM
            args.append("--medvram")
            info["recommended_mode"] = "medvram (8GB-10GB)"
            info["status_note"] = f"NVIDIA {info['name']} ({vram}MB VRAM): Configured with --medvram for optimal speed & memory balance."
        elif vram > 10240:  # > 10GB VRAM
            args.append("--highvram")
            info["recommended_mode"] = "highvram (>10GB)"
            info["status_note"] = f"NVIDIA {info['name']} ({vram}MB VRAM): Configured with --highvram for maximum speed."
        else:
            args.append("--medvram")
            info["recommended_mode"] = "medvram (Default)"
            info["status_note"] = f"NVIDIA {info['name']}: Configured with balanced --medvram."

    elif vendor in ("amd", "intel") or info.get("directml_available"):
        args.extend(["--directml", "--use-split-cross-attention"])
        info["recommended_mode"] = "DirectML (AMD / Intel)"
        info["status_note"] = f"{info['name']}: Configured for hardware-accelerated DirectML."

    elif vendor == "apple":
        args.append("--use-split-cross-attention")
        info["recommended_mode"] = "Apple Silicon MPS"
        info["status_note"] = "Apple Silicon: Configured with Metal Performance Shaders."

    else:
        # CPU Fallback
        args.append("--cpu")
        info["recommended_mode"] = "CPU Mode"
        info["status_note"] = "No supported dedicated GPU detected: Configured for CPU execution."

    info["recommended_args"] = args
    info["vram_mb"] = info["vram_total_mb"]
    info["vram_gb"] = round(info["vram_total_mb"] / 1024.0, 1) if info["vram_total_mb"] else 0.0
    _CACHED_GPU_HARDWARE = dict(info)
    return info


def list_all_gpus() -> list:
    """Enumerate all available GPU devices on the host machine."""
    devices = []
    
    # 1. PyTorch CUDA inspection
    try:
        import torch
        if torch.cuda.is_available():
            cnt = torch.cuda.device_count()
            for i in range(cnt):
                name = torch.cuda.get_device_name(i)
                props = torch.cuda.get_device_properties(i)
                vram_mb = int(props.total_memory / (1024 * 1024))
                devices.append({
                    "id": i,
                    "name": name,
                    "vram_mb": vram_mb,
                    "vram_gb": round(vram_mb / 1024.0, 1),
                    "backend": "CUDA",
                    "flag": f"--cuda-device {i}" if i > 0 else "",
                })
    except Exception:
        pass

    # 2. nvidia-smi fallback if PyTorch not found
    if not devices:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            if r.returncode == 0 and r.stdout.strip():
                for line in r.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        idx = int(parts[0]) if parts[0].isdigit() else 0
                        vram_mb = int(parts[2]) if parts[2].isdigit() else 0
                        devices.append({
                            "id": idx,
                            "name": parts[1],
                            "vram_mb": vram_mb,
                            "vram_gb": round(vram_mb / 1024.0, 1),
                            "backend": "CUDA",
                            "flag": f"--cuda-device {idx}" if idx > 0 else "",
                        })
        except Exception:
            pass

    if not devices:
        primary = detect_gpu_hardware()
        devices.append({
            "id": 0,
            "name": primary["name"],
            "vram_mb": primary["vram_total_mb"],
            "vram_gb": primary["vram_gb"],
            "backend": primary["vendor"].upper(),
            "flag": "",
        })

    return devices


def format_gpu_summary(gpu_info: dict) -> str:
    """Return a clean human-readable summary string of GPU status."""
    vram_gb = gpu_info['vram_total_mb'] / 1024.0 if gpu_info['vram_total_mb'] else 0.0
    return (
        f"{gpu_info['name']} | VRAM: {vram_gb:.1f} GB | Vendor: {gpu_info['vendor'].upper()} | "
        f"Mode: {gpu_info['recommended_mode']}"
    )


if __name__ == "__main__":
    print("=== ComfyUIX GPU Doctor ===")
    g = detect_gpu_hardware()
    import pprint
    pprint.pprint(g)
    print("\nAll GPUs:", list_all_gpus())
    print("\nSummary:", format_gpu_summary(g))
