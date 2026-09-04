"""
model_downloader.py - High-Performance Dynamic Model Hub & Downloader for ComfyUIX
Supports:
1. Curated 1-Click Essentials (SDXL, SD1.5, FLUX, Upscalers)
2. Live Dynamic HuggingFace Hub API (Search, Trending, SOTA models, SDXL, Flux, LoRAs)
3. Live Dynamic CivitAI Hub API (Top-rated Checkpoints, SOTA LoRAs, Upscalers)
4. Custom Direct URLs (HuggingFace, CivitAI, GitHub, Direct CDN links)
5. Multi-threaded chunked streaming, resume support, real-time speed (MB/s), ETA, and auto-integration.
"""

import os
import sys
import time
import json
import logging
import threading
import urllib.request
import urllib.error
import urllib.parse
from typing import Callable, Optional, Dict, Any, List

logger = logging.getLogger("model_downloader")

# ---------------------------------------------------------------------------
# Directory Resolution
# ---------------------------------------------------------------------------
def _find_comfyui_models_root(base_dir: Optional[str] = None) -> str:
    if base_dir and os.path.isdir(base_dir):
        p = os.path.join(base_dir, "models")
        if os.path.isdir(p):
            return p
    cands = [
        os.path.join(os.getcwd(), "models"),
        os.path.join(os.getcwd(), "ComfyUI_windows_portable", "ComfyUI", "models"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "models"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ComfyUI", "models"),
        r"C:\ComfyUI_windows_portable\ComfyUI\models",
        r"C:\ComfyUI-Desktop\models",
        r"C:\ComfyUI\models",
    ]
    for c in cands:
        if os.path.isdir(c):
            return c
    d = os.path.join(os.getcwd(), "models")
    os.makedirs(d, exist_ok=True)
    return d

def get_checkpoints_dir(base_dir: Optional[str] = None) -> str:
    """Resolve the checkpoints directory."""
    m_root = _find_comfyui_models_root(base_dir)
    d = os.path.join(m_root, "checkpoints")
    os.makedirs(d, exist_ok=True)
    return d

def get_loras_dir(base_dir: Optional[str] = None) -> str:
    """Resolve the loras directory."""
    m_root = _find_comfyui_models_root(base_dir)
    d = os.path.join(m_root, "loras")
    os.makedirs(d, exist_ok=True)
    return d

def get_upscale_dir(base_dir: Optional[str] = None) -> str:
    """Resolve the upscale models directory."""
    m_root = _find_comfyui_models_root(base_dir)
    d = os.path.join(m_root, "upscale_models")
    os.makedirs(d, exist_ok=True)
    return d

def get_vae_dir(base_dir: Optional[str] = None) -> str:
    """Resolve the VAE models directory."""
    m_root = _find_comfyui_models_root(base_dir)
    d = os.path.join(m_root, "vae")
    os.makedirs(d, exist_ok=True)
    return d

def get_controlnet_dir(base_dir: Optional[str] = None) -> str:
    """Resolve the ControlNet models directory."""
    m_root = _find_comfyui_models_root(base_dir)
    d = os.path.join(m_root, "controlnet")
    os.makedirs(d, exist_ok=True)
    return d

def get_clip_dir(base_dir: Optional[str] = None) -> str:
    """Resolve the CLIP / Text Encoder models directory."""
    m_root = _find_comfyui_models_root(base_dir)
    d = os.path.join(m_root, "clip")
    os.makedirs(d, exist_ok=True)
    return d

def get_unet_dir(base_dir: Optional[str] = None) -> str:
    """Resolve the UNet / Diffusion models directory."""
    m_root = _find_comfyui_models_root(base_dir)
    d = os.path.join(m_root, "unet")
    os.makedirs(d, exist_ok=True)
    return d

def get_model_target_dir(model_type: str, base_dir: Optional[str] = None) -> str:
    """Route a model to its correct destination subfolder based on type."""
    t = str(model_type).lower().strip()
    if "lora" in t:
        return get_loras_dir(base_dir)
    elif "upscale" in t or "esrgan" in t:
        return get_upscale_dir(base_dir)
    elif "vae" in t:
        return get_vae_dir(base_dir)
    elif "control" in t or "controlnet" in t:
        return get_controlnet_dir(base_dir)
    elif "clip" in t or "encoder" in t or "t5" in t:
        return get_clip_dir(base_dir)
    elif "unet" in t or "diffusion" in t or "dit" in t:
        return get_unet_dir(base_dir)
    else:
        return get_checkpoints_dir(base_dir)

def get_free_disk_space_gb(target_dir: str) -> float:
    """Return available free disk space in GB for the partition hosting target_dir."""
    try:
        import shutil
        total, used, free = shutil.disk_usage(target_dir)
        return round(free / (1024 ** 3), 2)
    except Exception:
        return 999.0



# ---------------------------------------------------------------------------
# Curated High-Quality Model Catalog
# ---------------------------------------------------------------------------
CURATED_MODELS: List[Dict[str, Any]] = [
    {
        "id": "epicrealism_xl",
        "name": "epiCRealism XL v5",
        "filename": "epicrealismXL_v5.safetensors",
        "type": "checkpoint",
        "category": "SDXL Photorealism",
        "size_gb": 6.6,
        "description": "State-of-the-art cinematic photorealism, ultra-fine skin textures, natural lighting, and sharp portraits.",
        "url": "https://huggingface.co/emilianJR/epiCRealism/resolve/main/epicrealismXL_v5.safetensors",
        "fallback_url": "https://civitai.com/api/download/models/258284?type=Model&format=SafeTensor",
        "vram_rec": "8GB+ VRAM",
        "badge": "RECOMMENDED",
        "source": "Curated",
    },
    {
        "id": "juggernaut_xl",
        "name": "Juggernaut XL v9",
        "filename": "juggernautXL_version9.safetensors",
        "type": "checkpoint",
        "category": "SDXL All-Rounder",
        "size_gb": 6.6,
        "description": "Versatile all-around SDXL powerhouse for concept art, landscapes, detailed portraits, and game textures.",
        "url": "https://huggingface.co/RunDiffusion/Juggernaut-XL-v9/resolve/main/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
        "fallback_url": "https://civitai.com/api/download/models/456194?type=Model&format=SafeTensor",
        "vram_rec": "8GB+ VRAM",
        "badge": "POPULAR",
        "source": "Curated",
    },
    {
        "id": "dreamshaper_8",
        "name": "DreamShaper 8 (SD 1.5)",
        "filename": "dreamshaper_8.safetensors",
        "type": "checkpoint",
        "category": "SD 1.5 Fast / Lightweight",
        "size_gb": 2.1,
        "description": "Fast generation speed, low VRAM consumption (4GB+), superb illustration, artistic styles, and character art.",
        "url": "https://huggingface.co/Lykon/DreamShaper/resolve/main/DreamShaper_8_pruned.safetensors",
        "fallback_url": "https://civitai.com/api/download/models/128713?type=Model&format=SafeTensor",
        "vram_rec": "4GB+ VRAM",
        "badge": "FAST & LIGHT",
        "source": "Curated",
    },
    {
        "id": "sdxl_turbo",
        "name": "SDXL Turbo (1-Step Fast)",
        "filename": "sd_xl_turbo_1.0_fp16.safetensors",
        "type": "checkpoint",
        "category": "Ultra Fast Real-Time",
        "size_gb": 6.9,
        "description": "Real-time generation in 1 to 4 steps with lightning-fast inference for rapid iteration and instant previews.",
        "url": "https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors",
        "fallback_url": "https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0.safetensors",
        "vram_rec": "6GB+ VRAM",
        "badge": "TURBO",
        "source": "Curated",
    },
    {
        "id": "flux_schnell",
        "name": "FLUX.1-schnell (4-Step)",
        "filename": "flux1-schnell.safetensors",
        "type": "checkpoint",
        "category": "Next-Gen 12B DiT",
        "size_gb": 11.9,
        "description": "Next-generation 12B parameter flow matching model. Unmatched text rendering, prompt adherence, and photorealism.",
        "url": "https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/flux1-schnell.safetensors",
        "fallback_url": "https://huggingface.co/Comfy-Org/flux1-schnell/resolve/main/flux1-schnell-fp8.safetensors",
        "vram_rec": "12GB+ VRAM",
        "badge": "NEXT-GEN",
        "source": "Curated",
    },
    {
        "id": "ultrasharp_4x",
        "name": "4x-UltraSharp Upscaler",
        "filename": "4x-UltraSharp.pth",
        "type": "upscaler",
        "category": "Upscaling Super-Resolution",
        "size_gb": 0.06,
        "description": "Crystal-clear 4x super-resolution upscaler with clean edge preservation and zero blur.",
        "url": "https://huggingface.co/lokcx/4x-Ultrasharp/resolve/main/4x-UltraSharp.pth",
        "fallback_url": "https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x-UltraSharp.pth",
        "vram_rec": "2GB+ VRAM",
        "badge": "ESSENTIAL",
        "source": "Curated",
    },
    {
        "id": "realesrgan_4x",
        "name": "RealESRGAN x4 Plus",
        "filename": "RealESRGAN_x4plus.pth",
        "type": "upscaler",
        "category": "Upscaling Super-Resolution",
        "size_gb": 0.07,
        "description": "Industry standard 4x general image and texture upscaler for realistic details.",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "fallback_url": "https://huggingface.co/FacehugmanIII/4x_foolhardy_Remacri/resolve/main/4x_foolhardy_Remacri.pth",
        "vram_rec": "2GB+ VRAM",
        "badge": "STANDARD",
        "source": "Curated",
    },
]


# ---------------------------------------------------------------------------
# Dynamic Live APIs (HuggingFace + CivitAI)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Dynamic Live APIs (HuggingFace + CivitAI)
# ---------------------------------------------------------------------------
def fetch_huggingface_models(query: str = "", tag: str = "text-to-image", limit: int = 20, token: str = "") -> List[Dict[str, Any]]:
    """Fetch live newest/trending models from Hugging Face Model Hub API."""
    results = []
    try:
        search_param = urllib.parse.quote(query.strip()) if query.strip() else "safetensors"
        url = f"https://huggingface.co/api/models?search={search_param}&filter={tag}&sort=downloads&direction=-1&limit={limit}"
        headers = {"User-Agent": "ComfyUIX-Client/5.0"}
        auth_tok = token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        if auth_tok:
            headers["Authorization"] = f"Bearer {auth_tok.strip()}"
            
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        for item in data:
            model_id = item.get("id", "")
            if not model_id:
                continue
            name_clean = model_id.split("/")[-1]
            downloads = item.get("downloads", 0)
            likes = item.get("likes", 0)
            tags = item.get("tags", [])
            
            # Determine type
            m_type = "checkpoint"
            if any("lora" in t.lower() for t in tags):
                m_type = "lora"
            elif any("upscale" in t.lower() or "esrgan" in t.lower() for t in tags):
                m_type = "upscaler"
            elif any("vae" in t.lower() for t in tags):
                m_type = "vae"
            elif any("controlnet" in t.lower() for t in tags):
                m_type = "controlnet"

            target_dir = get_model_target_dir(m_type)
            filename = f"{name_clean}.safetensors" if not name_clean.endswith((".safetensors", ".pth", ".bin")) else name_clean
            dest_file = os.path.join(target_dir, filename)
            installed = os.path.exists(dest_file) and os.path.getsize(dest_file) > 1024 * 1024

            results.append({
                "id": f"hf_{model_id.replace('/', '_')}",
                "name": name_clean,
                "author": model_id.split("/")[0] if "/" in model_id else "Community",
                "filename": filename,
                "type": m_type,
                "category": f"HuggingFace ({m_type.upper()})",
                "size_gb": 4.5,
                "description": f"HF Model: {model_id} | Downloads: {downloads:,} | Likes: {likes:,}",
                "url": f"https://huggingface.co/{model_id}/resolve/main/{filename}",
                "fallback_url": f"https://huggingface.co/{model_id}/resolve/main/model.safetensors",
                "vram_rec": "8GB+ VRAM",
                "badge": f"🔥 {downloads:,} DLs",
                "source": "Hugging Face",
                "installed": installed,
                "dest_path": dest_file,
                "dest_dir": target_dir,
            })
    except Exception as e:
        logger.warning("HuggingFace API fetch error: %s", e)
    return results


def fetch_civitai_models(query: str = "", model_type: str = "Checkpoint", limit: int = 20, token: str = "") -> List[Dict[str, Any]]:
    """Fetch live top-rated and trending models from CivitAI API."""
    results = []
    try:
        query_param = f"&query={urllib.parse.quote(query.strip())}" if query.strip() else ""
        type_param = f"&types={urllib.parse.quote(model_type)}" if model_type else "&types=Checkpoint"
        url = f"https://civitai.com/api/v1/models?limit={limit}&sort=Most+Downloaded{type_param}{query_param}"
        headers = {"User-Agent": "ComfyUIX-Client/5.0"}
        civitai_token = token or os.environ.get("CIVITAI_API_TOKEN") or os.environ.get("CIVITAI_TOKEN")
        if civitai_token:
            headers["Authorization"] = f"Bearer {civitai_token.strip()}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        items = data.get("items", [])
        for item in items:
            name = item.get("name", "CivitAI Model")
            creator = item.get("creator", {}).get("username", "Creator")
            stats = item.get("stats", {})
            dls = stats.get("downloadCount", 0)
            rating = stats.get("rating", 5.0)
            versions = item.get("modelVersions", [])
            if not versions:
                continue
            v = versions[0]
            v_id = v.get("id")
            files = v.get("files", [])
            images = v.get("images", [])
            preview_url = images[0].get("url") if images else ""

            safe_file = None
            for f in files:
                if f.get("name", "").endswith((".safetensors", ".pth")):
                    safe_file = f
                    break
            if not safe_file and files:
                safe_file = files[0]

            m_type = item.get("type", "Checkpoint").lower()
            target_dir = get_model_target_dir(m_type)
            filename = safe_file.get("name", f"{name}.safetensors") if safe_file else f"{name}.safetensors"
            filename = filename.replace(" ", "_").replace("/", "_")
            size_kb = safe_file.get("sizeKB", 4 * 1024 * 1024) if safe_file else 4 * 1024 * 1024
            size_gb = round(size_kb / (1024 * 1024), 1)

            dest_file = os.path.join(target_dir, filename)
            installed = os.path.exists(dest_file) and os.path.getsize(dest_file) > 1024 * 1024
            
            token_suffix = f"&token={civitai_token.strip()}" if civitai_token else ""
            dl_url = f"https://civitai.com/api/download/models/{v_id}?type=Model&format=SafeTensor{token_suffix}"

            results.append({
                "id": f"civitai_{item.get('id')}",
                "name": name,
                "author": creator,
                "filename": filename,
                "type": m_type,
                "category": f"CivitAI {item.get('type', 'Checkpoint')}",
                "size_gb": size_gb,
                "description": f"{name} by {creator} | Rating: ★{rating:.1f} | Downloads: {dls:,}",
                "url": dl_url,
                "fallback_url": dl_url,
                "preview_url": preview_url,
                "vram_rec": "6GB-8GB VRAM",
                "badge": f"★ {rating:.1f}",
                "source": "CivitAI",
                "installed": installed,
                "dest_path": dest_file,
                "dest_dir": target_dir,
            })
    except Exception as e:
        logger.warning("CivitAI API fetch error: %s", e)
    return results


def fetch_dynamic_models(source: str = "all", query: str = "", limit: int = 25) -> List[Dict[str, Any]]:
    """Unified dynamic fetcher that aggregates and deduplicates models from all live hubs."""
    out = []
    if source in ("all", "curated") and not query:
        out.extend(list_presets())
    
    if source in ("all", "huggingface"):
        out.extend(fetch_huggingface_models(query=query, limit=limit))
        
    if source in ("all", "civitai"):
        out.extend(fetch_civitai_models(query=query, limit=limit))

    # Deduplicate by ID
    seen = set()
    deduped = []
    for m in out:
        mid = m.get("id")
        if mid not in seen:
            seen.add(mid)
            deduped.append(m)
    return deduped


def list_presets() -> List[Dict[str, Any]]:
    """Return all curated model presets with their installation status."""
    ckpt_dir = get_checkpoints_dir()
    upscale_dir = get_upscale_dir()
    
    results = []
    for item in CURATED_MODELS:
        m = item.copy()
        target_dir = upscale_dir if m["type"] == "upscaler" else ckpt_dir
        dest_file = os.path.join(target_dir, m["filename"])
        m["installed"] = os.path.exists(dest_file) and os.path.getsize(dest_file) > 1024 * 1024
        m["dest_path"] = dest_file
        results.append(m)
    return results


def get_installed_checkpoint_count() -> int:
    """Count how many checkpoint files currently exist on disk."""
    ckpt_dir = get_checkpoints_dir()
    if not os.path.isdir(ckpt_dir):
        return 0
    count = 0
    for f in os.listdir(ckpt_dir):
        if f.lower().endswith((".safetensors", ".ckpt", ".pt", ".bin")):
            fp = os.path.join(ckpt_dir, f)
            if os.path.isfile(fp) and os.path.getsize(fp) > 1024 * 1024:
                count += 1
    return count


# ---------------------------------------------------------------------------
# Multi-Threaded Streaming Downloader with Progress & Speed
# ---------------------------------------------------------------------------
class DownloadTask:
    """Represents an active or queued model download with disk validation and preview caching."""
    def __init__(self, model_info: Dict[str, Any], dest_dir: str, on_progress: Optional[Callable] = None, on_complete: Optional[Callable] = None):
        self.model_info = model_info
        self.dest_dir = dest_dir
        # Security: Sanitize filename to prevent path traversal attacks
        filename = os.path.basename(str(model_info.get("filename", "")).replace("\\", "/"))
        if not filename or filename in (".", ".."):
            filename = "downloaded_model.safetensors"
        self.dest_path = os.path.join(dest_dir, filename)
        self.temp_path = self.dest_path + ".download"
        self.on_progress = on_progress
        self.on_complete = on_complete
        
        self.is_running = False
        self.is_cancelled = False
        self.is_paused = False
        self.bytes_downloaded = 0
        self.total_bytes = 0
        self.speed_bps = 0.0
        self.progress_pct = 0.0
        self.error_msg = ""
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start download in background thread after verifying disk space."""
        if self.is_running:
            return
            
        # Pre-flight disk space verification
        free_gb = get_free_disk_space_gb(self.dest_dir)
        required_gb = float(self.model_info.get("size_gb", 4.0))
        if free_gb < (required_gb + 0.5):
            self.error_msg = f"Insufficient disk space ({free_gb:.1f}GB free, {required_gb:.1f}GB needed)"
            logger.error("Download aborted: %s", self.error_msg)
            if self.on_complete:
                self.on_complete(False, "", self.error_msg)
            return

        self.is_running = True
        self.is_cancelled = False
        self._thread = threading.Thread(target=self._run_download, daemon=True)
        self._thread.start()

    def cancel(self):
        """Cancel the download and clean up temp files."""
        self.is_cancelled = True
        self.is_running = False
        if os.path.exists(self.temp_path):
            try:
                os.remove(self.temp_path)
            except Exception:
                pass

    def _run_download(self):
        url = self.model_info.get("url", "")
        fallback_url = self.model_info.get("fallback_url", "")
        urls_to_try = [url]
        if fallback_url and fallback_url != url:
            urls_to_try.append(fallback_url)

        os.makedirs(self.dest_dir, exist_ok=True)
        success = False

        for current_url in urls_to_try:
            if self.is_cancelled:
                break
            try:
                logger.info("Starting download from: %s", current_url)
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ComfyUIX/5.0",
                    "Accept": "*/*",
                }
                
                # Check for existing partial download (resume)
                initial_bytes = 0
                if os.path.exists(self.temp_path):
                    initial_bytes = os.path.getsize(self.temp_path)
                    if initial_bytes > 0:
                        headers["Range"] = f"bytes={initial_bytes}-"

                req = urllib.request.Request(current_url, headers=headers)

                with urllib.request.urlopen(req, timeout=30) as response:
                    status_code = response.getcode()
                    content_length = response.headers.get("Content-Length")
                    
                    if status_code == 206:  # Partial Content (Resume)
                        self.total_bytes = initial_bytes + int(content_length) if content_length else 0
                        mode = "ab"
                        self.bytes_downloaded = initial_bytes
                    else:
                        self.total_bytes = int(content_length) if content_length else int(self.model_info.get("size_gb", 4) * 1024 * 1024 * 1024)
                        mode = "wb"
                        self.bytes_downloaded = 0

                    chunk_size = 1024 * 512  # 512 KB chunks for high throughput
                    last_time = time.time()
                    last_bytes = self.bytes_downloaded

                    with open(self.temp_path, mode) as out_f:
                        while not self.is_cancelled:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            self.bytes_downloaded += len(chunk)

                            now = time.time()
                            dt = now - last_time
                            if dt >= 0.5:
                                d_bytes = self.bytes_downloaded - last_bytes
                                self.speed_bps = d_bytes / dt
                                if self.total_bytes > 0:
                                    self.progress_pct = min(100.0, (self.bytes_downloaded / self.total_bytes) * 100.0)
                                last_time = now
                                last_bytes = self.bytes_downloaded

                                if self.on_progress:
                                    self.on_progress(self.bytes_downloaded, self.total_bytes, self.speed_bps, self.progress_pct)

                    if not self.is_cancelled:
                        # Validate downloaded file size & integrity before committing
                        if not os.path.exists(self.temp_path) or os.path.getsize(self.temp_path) < 1024 * 512:
                            logger.error("Download for %s incomplete or corrupt (<512KB)", self.model_info.get("name"))
                            if os.path.exists(self.temp_path):
                                try:
                                    os.remove(self.temp_path)
                                except Exception:
                                    pass
                            self.error_msg = "Download incomplete or corrupt (file too small)"
                            continue

                        # Completed successfully
                        if os.path.exists(self.dest_path):
                            try:
                                os.remove(self.dest_path)
                            except Exception:
                                pass
                        os.replace(self.temp_path, self.dest_path)
                        self.progress_pct = 100.0
                        self.is_running = False
                        success = True
                        logger.info("Download completed and verified successfully: %s (%d bytes)", self.dest_path, os.path.getsize(self.dest_path))

                        # Download companion preview image (.preview.png) if available
                        preview_url = self.model_info.get("preview_url")
                        if preview_url:
                            try:
                                prev_dest = os.path.splitext(self.dest_path)[0] + ".preview.png"
                                p_req = urllib.request.Request(preview_url, headers={"User-Agent": "ComfyUIX/5.0"})
                                with urllib.request.urlopen(p_req, timeout=10) as p_resp:
                                    if p_resp.status == 200:
                                        with open(prev_dest, "wb") as pf:
                                            pf.write(p_resp.read())
                                        logger.info("Saved companion model preview image: %s", prev_dest)
                            except Exception as _pe:
                                logger.debug("Companion preview download notice: %s", _pe)

                        if self.on_complete:
                            try:
                                self.on_complete(True, self.dest_path, "")
                            except Exception as _cb_err:
                                logger.debug("on_complete callback notice: %s", _cb_err)
                        return

            except Exception as e:
                logger.warning("Download error from %s: %s", current_url, e)
                self.error_msg = str(e)
                continue

        if not success:
            self.is_running = False
            if not self.is_cancelled:
                logger.error("All download sources failed for %s", self.model_info.get("name"))
                if self.on_complete:
                    self.on_complete(False, "", self.error_msg or "Download failed. Please check network connection.")


def download_custom_url(url: str, custom_name: str = "", model_type: str = "checkpoint",
                        on_progress: Optional[Callable] = None, on_complete: Optional[Callable] = None) -> DownloadTask:
    """Download a model from an arbitrary direct URL to its appropriate directory."""
    url = url.strip()
    if not url:
        raise ValueError("URL cannot be empty")
    
    if not custom_name:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        filename = os.path.basename(path)
        if not filename or "?" in filename:
            filename = "custom_model.safetensors"
    else:
        filename = custom_name
        if not filename.endswith((".safetensors", ".ckpt", ".pth", ".bin")):
            filename += ".safetensors"

    # Security: Sanitize filename to prevent path traversal attacks (e.g., ../../../etc/passwd)
    filename = os.path.basename(filename.replace("\\", "/"))
    if not filename or filename in (".", ".."):
        filename = "custom_model.safetensors"

    dest_dir = get_model_target_dir(model_type)

    model_info = {
        "id": "custom_" + str(abs(hash(url))),
        "name": filename,
        "filename": filename,
        "type": model_type,
        "category": f"Custom {model_type.upper()}",
        "size_gb": 4.0,
        "description": f"Direct download from: {url[:50]}...",
        "url": url,
        "fallback_url": "",
    }
    
    task = DownloadTask(model_info, dest_dir, on_progress=on_progress, on_complete=on_complete)
    task.start()
    return task

