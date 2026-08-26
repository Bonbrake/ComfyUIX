"""
ComfyUI Uncensored v5.0 - WebSocket Progress Listener & REST ComfyClient
Pure-Python RFC 6455 WebSocket client + REST API client for ComfyUI.
Handles real-time node execution progress, live latent preview images, and VRAM watchdog.
"""
import io
import os
import sys
import time
import json
import base64
import socket
import struct
import logging
import requests
import threading
from typing import Optional, Callable
from PIL import Image
from comfyui_desktop import config

logger = logging.getLogger(__name__)

def _get_url():
    return getattr(config, "COMFYUI_URL", "http://127.0.0.1:8188")


class ComfyClient:
    """REST API Client for ComfyUI Endpoints."""
    @staticmethod
    def post_prompt(workflow, client_id="comfyui_uncensored"):
        payload = {"prompt": workflow, "client_id": client_id}
        r = requests.post(_get_url() + "/prompt", json=payload, timeout=10)
        return r

    @staticmethod
    def post_interrupt():
        try:
            return requests.post(_get_url() + "/interrupt", timeout=0.5)
        except Exception:
            return None

    @staticmethod
    def purge_vram():
        """Invoke ComfyUI /free endpoint to clear CUDA memory cache and unload idle models."""
        try:
            r = requests.post(_get_url() + "/free", json={"unload_models": True, "free_memory": True}, timeout=0.5)
            return r.status_code == 200
        except Exception:
            return False

    @staticmethod
    def get_system_stats():
        try:
            r = requests.get(_get_url() + "/system_stats", timeout=0.5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None

    @staticmethod
    def get_history(prompt_id: Optional[str] = None):
        try:
            url = _get_url() + "/history"
            if prompt_id:
                url += f"/{prompt_id}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}


class ComfyWebSocketClient:
    """Zero-dependency RFC 6455 WebSocket Client for ComfyUI Live Progress & Latent Streaming."""
    def __init__(self, host: str = "127.0.0.1", port: int = 8188, client_id: str = "comfyui_uncensored",
                 on_progress: Optional[Callable] = None,
                 on_node_executing: Optional[Callable] = None,
                 on_preview: Optional[Callable] = None,
                 on_executed: Optional[Callable] = None):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.on_progress = on_progress
        self.on_node_executing = on_node_executing
        self.on_preview = on_preview
        self.on_executed = on_executed
        
        self._sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _connect(self) -> bool:
        try:
            s = socket.create_connection((self.host, self.port), timeout=3.0)
            key = base64.b64encode(os.urandom(16)).decode("ascii")
            path = f"/ws?clientId={self.client_id}"
            req = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {self.host}:{self.port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n\r\n"
            )
            s.sendall(req.encode("ascii"))
            resp = s.recv(4096).decode("utf-8", "ignore")
            if "101 Switching Protocols" in resp or "101" in resp:
                self._sock = s
                return True
            s.close()
        except Exception:
            pass
        return False

    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n and self._running:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionResetError("Socket closed")
            buf.extend(chunk)
        return bytes(buf)

    def _run_loop(self):
        while self._running:
            if not self._sock:
                if not self._connect():
                    time.sleep(2.0)
                    continue

            try:
                # Read 2 byte WebSocket frame header
                hdr = self._recv_exact(2)
                b1, b2 = hdr[0], hdr[1]
                fin = (b1 & 0x80) != 0
                opcode = b1 & 0x0F
                has_mask = (b2 & 0x80) != 0
                payload_len = b2 & 0x7F

                if payload_len == 126:
                    payload_len = struct.unpack(">H", self._recv_exact(2))[0]
                elif payload_len == 127:
                    payload_len = struct.unpack(">Q", self._recv_exact(8))[0]

                mask_key = self._recv_exact(4) if has_mask else None
                payload = self._recv_exact(payload_len)

                if has_mask and mask_key:
                    unmasked = bytearray(payload)
                    for i in range(len(unmasked)):
                        unmasked[i] ^= mask_key[i % 4]
                    payload = bytes(unmasked)

                if opcode == 1:  # Text Frame (JSON)
                    text_msg = payload.decode("utf-8", "replace")
                    self._handle_json_msg(text_msg)
                elif opcode == 2:  # Binary Frame (JPEG Latent Preview)
                    self._handle_binary_preview(payload)
                elif opcode == 8:  # Close Frame
                    self.stop()
                    break
                elif opcode == 9:  # Ping Frame -> Pong
                    if self._sock:
                        pong = bytearray([0x8A, 0x00])
                        self._sock.sendall(pong)

            except Exception:
                if self._sock:
                    try:
                        self._sock.close()
                    except Exception:
                        pass
                    self._sock = None
                time.sleep(1.0)

    def _handle_json_msg(self, text: str):
        try:
            msg = json.loads(text)
            mtype = msg.get("type")
            data = msg.get("data", {})

            if mtype == "progress":
                val = data.get("value", 0)
                max_val = data.get("max", 1)
                prompt_id = data.get("prompt_id", "")
                if self.on_progress:
                    self.on_progress(val, max_val, prompt_id)

            elif mtype == "executing":
                node_id = data.get("node")
                prompt_id = data.get("prompt_id", "")
                if self.on_node_executing:
                    self.on_node_executing(node_id, prompt_id)

            elif mtype == "executed":
                node_id = data.get("node")
                output = data.get("output", {})
                prompt_id = data.get("prompt_id", "")
                if self.on_executed:
                    self.on_executed(node_id, output, prompt_id)

        except Exception:
            pass

    def _handle_binary_preview(self, payload: bytes):
        """Decode binary preview JPEG sent from ComfyUI latent previewer."""
        if len(payload) <= 8:
            return
        try:
            # First 8 bytes are the ComfyUI event header (4 bytes event type + 4 bytes image format)
            img_bytes = payload[8:]
            pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            if self.on_preview:
                self.on_preview(pil_img)
        except Exception:
            pass


class VRAMWatchdog:
    """Monitors VRAM usage and performs smart automatic memory purging when critical."""
    def __init__(self, status_callback, get_threshold_func):
        self.status_callback = status_callback
        self.get_threshold_func = get_threshold_func
        self._running = True

    def is_critical(self, threshold=None):
        try:
            val = self.get_threshold_func() if self.get_threshold_func else "90%"
            if "Disabled" in val:
                return False
            if threshold is None:
                if "95%" in val: threshold = 0.95
                elif "85%" in val: threshold = 0.85
                elif "80%" in val: threshold = 0.80
                else: threshold = 0.90

            stats = ComfyClient.get_system_stats()
            if not stats or not stats.get("devices"):
                return False

            d = stats["devices"][0]
            total = d.get("vram_total", 0) or 0
            free = d.get("vram_free", 0) or 0
            if total <= 0:
                return False

            used_pct = 1 - (free / total)
            if used_pct > threshold:
                # Smart VRAM Recovery: Automatically attempt /free to clear PyTorch cache
                ComfyClient.purge_vram()
                time.sleep(0.5)
                stats2 = ComfyClient.get_system_stats()
                if stats2 and stats2.get("devices"):
                    d2 = stats2["devices"][0]
                    tot2 = d2.get("vram_total", 0) or 0
                    fr2 = d2.get("vram_free", 0) or 0
                    if tot2 > 0:
                        used_pct = 1 - (fr2 / tot2)
            return used_pct > threshold
        except Exception:
            return False

    def stop(self):
        self._running = False

