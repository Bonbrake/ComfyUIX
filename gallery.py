"""
ComfyUI Uncensored v5.0 - Async Gallery Engine & Memory Safety
Handles ThreadPool thumbnail decoding, PIL image cache lifecycle, TGA texture exports,
and recursive multi-path Media Vault auto-discovery.
"""
import os
import gc
import math
import logging
from PIL import Image, ImageTk
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class ImageCache:
    """Explicit Image Memory Registry that prevents PIL & ImageTk GDI/RAM memory leaks."""
    def __init__(self):
        self._pil_cache = {}
        self._tk_cache = {}

    def register(self, key, pil_image, tk_image=None):
        self.release(key)
        self._pil_cache[key] = pil_image
        if tk_image:
            self._tk_cache[key] = tk_image

    def release(self, key):
        if key in self._pil_cache:
            try:
                img = self._pil_cache.pop(key)
                if hasattr(img, "close"):
                    img.close()
            except Exception as e:
                logger.debug("PIL close error: %s", e)
        if key in self._tk_cache:
            self._tk_cache.pop(key, None)

    def clear(self):
        keys = list(self._pil_cache.keys())
        for k in keys:
            self.release(k)
        self._pil_cache.clear()
        self._tk_cache.clear()
        gc.collect()

# Global ImageCache Instance
image_cache = ImageCache()

def convert_to_game_texture(image_path):
    """Export output image as a Power-of-Two tileable TGA texture for game engines."""
    try:
        if not image_path or not os.path.exists(image_path):
            return False
        image_path = os.path.abspath(image_path)
        with Image.open(image_path) as im:
            w, h = im.size
            # Nearest Power-of-Two dimensions
            pot_w = 2 ** round(math.log2(w)) if w > 0 else 512
            pot_h = 2 ** round(math.log2(h)) if h > 0 else 512
            pot_im = im.resize((pot_w, pot_h), Image.Resampling.LANCZOS)
            tga_path = os.path.splitext(image_path)[0] + ".tga"
            pot_im.save(tga_path, format="TGA")
            pot_im.close()
            return tga_path
    except Exception as e:
        logger.error("Failed to convert texture to TGA: %s", e)
        return False

def discover_media_directories(primary_dir=None, comfyui_dir=None, portable_dir=None):
    """Auto-discover all standard ComfyUI generated output image directories."""
    candidates = []
    if primary_dir:
        candidates.append(os.path.normpath(primary_dir))

    # Standard user ComfyUI Pictures directory
    pics = os.path.normpath(os.path.expanduser(r"~/Pictures"))
    gen_pics = os.path.join(pics, "ComfyUI_Generated")
    candidates.append(gen_pics)

    # ComfyUI installation output dirs
    if comfyui_dir:
        candidates.append(os.path.join(comfyui_dir, "output"))
    if portable_dir:
        candidates.append(os.path.join(portable_dir, "output"))
        candidates.append(os.path.join(portable_dir, "ComfyUI", "output"))
        candidates.append(os.path.join(portable_dir, "ComfyUI_windows_portable", "ComfyUI", "output"))

    # Well-known fallback paths
    candidates.extend([
        r"C:\ComfyUI-Desktop\output",
        r"C:\ComfyUI-Desktop\ComfyUI_windows_portable\ComfyUI\output",
        r"C:\ComfyUI_windows_portable\ComfyUI\output",
        r"C:\ComfyUI\output",
        os.path.abspath("output"),
        os.path.normpath(os.path.expanduser(r"~/Documents/ComfyUI/output")),
    ])

    seen = set()
    valid_dirs = []
    for d in candidates:
        if d and os.path.isdir(d):
            norm = os.path.normpath(d)
            if norm not in seen:
                seen.add(norm)
                valid_dirs.append(norm)
    return valid_dirs

TEXTURE_KEYWORDS = (
    "texture", "albedo", "normal", "roughness", "metallic", "height",
    "specular", "diffuse", "pbr", "ambient", "displacement", "emission",
    "mat_", "_tex", "_mat", "orm", "mask"
)

def is_texture_file(filepath: str) -> bool:
    """Determine if a file is an authentic texture/material map."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".tga", ".dds", ".exr"):
        return True
    base = os.path.basename(filepath).lower()
    parent = os.path.basename(os.path.dirname(filepath)).lower()
    if parent in ("textures", "materials", "pbr_maps", "texture_exports"):
        return True
    for kw in TEXTURE_KEYWORDS:
        if kw in base:
            return True
    return False

def generate_pbr_maps(image_path: str) -> dict:
    """Generate complete PBR Texture Map Suite (Normal, Roughness, Height, AO, TGA).
    
    Returns a dictionary of generated map file paths.
    """
    try:
        import numpy as np
        try:
            from scipy.ndimage import sobel
        except ImportError:
            sobel = None
    except ImportError:
        np = None

    if not image_path or not os.path.exists(image_path):
        return {}
    
    base_name, _ = os.path.splitext(os.path.abspath(image_path))
    results = {}

    try:
        with Image.open(image_path).convert("RGB") as im:
            w, h = im.size
            pot_w = 2 ** round(math.log2(w)) if w > 0 else 512
            pot_h = 2 ** round(math.log2(h)) if h > 0 else 512
            pot_im = im.resize((pot_w, pot_h), Image.Resampling.LANCZOS)
            
            # 1. Albedo TGA
            tga_path = base_name + "_albedo.tga"
            pot_im.save(tga_path, format="TGA")
            results["albedo"] = tga_path

            gray = pot_im.convert("L")
            gray_arr = np.array(gray, dtype=np.float32) / 255.0 if np is not None else None

            # 2. Tangent-space Normal Map (Sobel filter or np.gradient fallback)
            if gray_arr is not None:
                if sobel is not None:
                    dx = sobel(gray_arr, axis=1) * 3.0
                    dy = sobel(gray_arr, axis=0) * 3.0
                else:
                    # High-performance NumPy gradient fallback when scipy is absent
                    gy, gx = np.gradient(gray_arr)
                    dx = gx * 6.0
                    dy = gy * 6.0
                dz = np.ones_like(gray_arr)
                norm = np.sqrt(dx**2 + dy**2 + dz**2)
                norm = np.maximum(norm, 1e-6)
                nx = (dx / norm * 0.5 + 0.5) * 255.0
                ny = (-dy / norm * 0.5 + 0.5) * 255.0  # OpenGL / DirectX Y-flip
                nz = (dz / norm * 0.5 + 0.5) * 255.0
                normal_arr = np.stack([nx, ny, nz], axis=-1).astype(np.uint8)
                normal_im = Image.fromarray(normal_arr, "RGB")
                norm_path = base_name + "_normal.png"
                normal_im.save(norm_path)
                results["normal"] = norm_path

                # 3. Roughness Map (Inverted Specular with contrast curve)
                rough_arr = (1.0 - gray_arr) ** 0.8 * 255.0
                rough_im = Image.fromarray(rough_arr.astype(np.uint8), "L")
                rough_path = base_name + "_roughness.png"
                rough_im.save(rough_path)
                results["roughness"] = rough_path

                # 4. Height / Displacement Map
                height_path = base_name + "_height.png"
                gray.save(height_path)
                results["height"] = height_path

                # 5. Ambient Occlusion (AO) approximation
                ao_arr = np.clip(gray_arr * 1.2, 0.0, 1.0) * 255.0
                ao_im = Image.fromarray(ao_arr.astype(np.uint8), "L")
                ao_path = base_name + "_ao.png"
                ao_im.save(ao_path)
                results["ao"] = ao_path

            # 6. 3x3 Seamless Tiled Preview
            tiled_w, tiled_h = pot_w * 3, pot_h * 3
            tiled_im = Image.new("RGB", (tiled_w, tiled_h))
            for tx in range(3):
                for ty in range(3):
                    tiled_im.paste(pot_im, (tx * pot_w, ty * pot_h))
            tiled_path = base_name + "_3x3_tiled.png"
            tiled_im.save(tiled_path)
            results["tiled_3x3"] = tiled_path

    except Exception as e:
        logger.error("PBR Map Generation failed: %s", e)

    return results

def scan_all_media_files(directories, recursive=True, max_depth=2, filter_type="all"):
    """Scan given directories for media files, excluding input and cache folders.
    filter_type: 'all', 'images', 'videos', 'textures'
    """
    valid_exts = (".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".tga", ".bmp")
    if filter_type == "images":
        valid_exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
    elif filter_type == "videos":
        valid_exts = (".mp4", ".webm", ".avi", ".mov", ".gif")
    elif filter_type == "textures":
        valid_exts = (".tga", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".dds")

    valid_files = []
    seen = set()
    ignored_dir_names = {"input", "inputs", "temp", "_temp", "cache", "__pycache__", "thumbnails", "thumbs", ".git", ".cache"}

    for base in directories:
        if not os.path.isdir(base):
            continue
        if not recursive:
            try:
                for f in os.listdir(base):
                    if f.lower().endswith(valid_exts) and not f.lower().startswith("input"):
                        fp = os.path.join(base, f)
                        if os.path.isfile(fp) and fp not in seen:
                            ext = os.path.splitext(fp)[1].lower()
                            if filter_type == "textures" and not is_texture_file(fp):
                                continue
                            if filter_type == "images" and is_texture_file(fp) and ext == ".tga":
                                continue
                            seen.add(fp)
                            valid_files.append(fp)
            except Exception:
                pass
            continue

        for root, dirs, files in os.walk(base):
            # Prune ignored directory branches
            dirs[:] = [d for d in dirs if d.lower() not in ignored_dir_names]
            lower_root = root.lower()
            if any(ign in lower_root.split(os.sep) for ign in ignored_dir_names):
                continue
            if ("screenshot" in lower_root or "camera roll" in lower_root) and root not in directories:
                continue
            rel = os.path.relpath(root, base)
            if rel != "." and len(rel.split(os.sep)) > max_depth:
                continue
            for f in files:
                if f.lower().endswith(valid_exts) and not f.lower().startswith("input"):
                    fp = os.path.join(root, f)
                    if fp not in seen:
                        ext = os.path.splitext(fp)[1].lower()
                        if filter_type == "textures" and not is_texture_file(fp):
                            continue
                        if filter_type == "images" and is_texture_file(fp) and ext == ".tga":
                            continue
                        seen.add(fp)
                        valid_files.append(fp)

    return valid_files


def extract_generation_metadata(image_path: str) -> dict:
    """Extract embedded generation parameters, prompts, and ComfyUI workflow DAG from PNG/WebP files."""
    import json
    res = {
        "has_metadata": False,
        "prompt": "",
        "negative": "",
        "model": "",
        "seed": None,
        "steps": None,
        "cfg": None,
        "sampler": "",
        "scheduler": "",
        "width": None,
        "height": None,
        "loras": [],
        "raw": {}
    }
    if not image_path or not os.path.isfile(image_path):
        return res
    try:
        with Image.open(image_path) as im:
            info = im.info or {}
            res["raw"] = {str(k): str(v)[:500] for k, v in info.items()}

            # 1. ComfyUI Prompt JSON chunk
            if "prompt" in info:
                try:
                    p_data = json.loads(info["prompt"]) if isinstance(info["prompt"], str) else info["prompt"]
                    if isinstance(p_data, dict):
                        res["has_metadata"] = True
                        for nid, node in p_data.items():
                            ctype = str(node.get("class_type", ""))
                            inputs = node.get("inputs", {})
                            if any(k in ctype for k in ("CLIPTextEncode", "TextEncode", "Prompt")):
                                txt = str(inputs.get("text", "")).strip()
                                if txt:
                                    if not res["prompt"]:
                                        res["prompt"] = txt
                                    elif not res["negative"]:
                                        res["negative"] = txt
                            elif "KSampler" in ctype or "Sampler" in ctype:
                                if "seed" in inputs and res["seed"] is None: res["seed"] = inputs["seed"]
                                if "steps" in inputs and res["steps"] is None: res["steps"] = inputs["steps"]
                                if "cfg" in inputs and res["cfg"] is None: res["cfg"] = inputs["cfg"]
                                if "sampler_name" in inputs and not res["sampler"]: res["sampler"] = str(inputs["sampler_name"])
                                if "scheduler" in inputs and not res["scheduler"]: res["scheduler"] = str(inputs["scheduler"])
                            elif "CheckpointLoader" in ctype or "UNETLoader" in ctype:
                                if "ckpt_name" in inputs and not res["model"]: res["model"] = str(inputs["ckpt_name"])
                                elif "unet_name" in inputs and not res["model"]: res["model"] = str(inputs["unet_name"])
                            elif "EmptyLatent" in ctype:
                                if "width" in inputs and res["width"] is None: res["width"] = inputs["width"]
                                if "height" in inputs and res["height"] is None: res["height"] = inputs["height"]
                            elif "LoraLoader" in ctype:
                                if "lora_name" in inputs:
                                    res["loras"].append({
                                        "name": str(inputs["lora_name"]),
                                        "strength_model": inputs.get("strength_model", 1.0),
                                        "strength_clip": inputs.get("strength_clip", 1.0)
                                    })
                except Exception as e:
                    logger.debug("ComfyUI chunk parse note: %s", e)

            # 2. A1111 / WebUI / Forge 'parameters' chunk fallback
            if not res["has_metadata"] and "parameters" in info:
                p_text = str(info["parameters"])
                res["has_metadata"] = True
                if "Negative prompt:" in p_text:
                    parts = p_text.split("Negative prompt:")
                    res["prompt"] = parts[0].strip()
                    tail = parts[1]
                    if "Steps:" in tail:
                        sub = tail.split("Steps:")
                        res["negative"] = sub[0].strip()
                    else:
                        res["negative"] = tail.strip()
                elif "Steps:" in p_text:
                    res["prompt"] = p_text.split("Steps:")[0].strip()
                else:
                    res["prompt"] = p_text.strip()
    except Exception as e:
        logger.debug("Failed to extract metadata from %s: %s", image_path, e)

    return res
