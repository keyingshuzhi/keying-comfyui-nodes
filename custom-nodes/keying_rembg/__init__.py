# -*- coding: utf-8 -*-
"""
Keying Rembg Node for ComfyUI (Local-Only Models)
- Robust tensor<->PIL conversion (NO squeeze bug)
- Supports batch input
- Outputs: cutout IMAGE (RGB) + MASK (alpha 0..1)
- Optional: composite to white background
- IMPORTANT: Force models to load ONLY from:
    ComfyUI/models/u2net/
      - isnet-anime.onnx
      - isnet-general-use.onnx
      - u2net.onnx
      - u2netp.onnx
  and DO NOT use ~/.u2net
"""

import os
import io
from typing import Dict, List

import numpy as np
import torch
from PIL import Image

from rembg import remove, new_session


# -----------------------------
# Helpers: ComfyUI IMAGE/MASK <-> PIL/np
# ComfyUI IMAGE: torch float32 in [0,1], shape [B,H,W,C]
# MASK: torch float32 in [0,1], shape [B,H,W]
# -----------------------------

def _ensure_4d_image(x: torch.Tensor) -> torch.Tensor:
    if not isinstance(x, torch.Tensor):
        raise TypeError(f"Expected torch.Tensor, got {type(x)}")
    if x.dim() == 3:
        # [H,W,C] -> [1,H,W,C]
        return x.unsqueeze(0)
    if x.dim() != 4:
        raise ValueError(f"Expected IMAGE tensor with 3 or 4 dims, got shape={tuple(x.shape)}")
    return x


def tensor_image_to_pil_rgb(img_bhwc: torch.Tensor) -> Image.Image:
    """
    img_bhwc: [1,H,W,C] float in [0,1]
    Return: PIL RGB
    """
    img_bhwc = _ensure_4d_image(img_bhwc)
    img = img_bhwc[0]  # only remove batch dim, do NOT squeeze H/W

    img = img.detach().to(torch.float32).clamp(0, 1).cpu()

    # handle channels
    if img.shape[-1] == 1:
        img = img.repeat(1, 1, 3)
    elif img.shape[-1] == 4:
        img = img[..., :3]
    elif img.shape[-1] != 3:
        raise ValueError(f"Unsupported channel count: C={img.shape[-1]}")

    arr = (img.numpy() * 255.0).round().astype(np.uint8)  # HWC uint8
    return Image.fromarray(arr, mode="RGB")


def pil_rgb_to_tensor_image(pil: Image.Image) -> torch.Tensor:
    """
    PIL RGB -> IMAGE [1,H,W,3] float in [0,1]
    """
    if pil.mode != "RGB":
        pil = pil.convert("RGB")
    arr = np.asarray(pil).astype(np.float32) / 255.0  # HWC
    return torch.from_numpy(arr).unsqueeze(0)  # 1,H,W,3


def pil_alpha_to_tensor_mask(pil_rgba: Image.Image) -> torch.Tensor:
    """
    PIL RGBA -> MASK [1,H,W] float in [0,1]
    """
    if pil_rgba.mode != "RGBA":
        pil_rgba = pil_rgba.convert("RGBA")
    alpha = pil_rgba.split()[-1]  # L
    a = (np.asarray(alpha).astype(np.float32) / 255.0)  # HW
    return torch.from_numpy(a).unsqueeze(0)  # 1,H,W


def open_rembg_output(out) -> Image.Image:
    """
    rembg.remove may return PIL or bytes. Normalize to PIL Image.
    """
    if isinstance(out, Image.Image):
        return out
    if isinstance(out, (bytes, bytearray)):
        return Image.open(io.BytesIO(out))
    raise TypeError(f"Unexpected rembg output type: {type(out)}")


def composite_on_white(pil_rgba: Image.Image) -> Image.Image:
    """
    Composite RGBA onto white background, return RGB.
    """
    if pil_rgba.mode != "RGBA":
        pil_rgba = pil_rgba.convert("RGBA")
    bg = Image.new("RGBA", pil_rgba.size, (255, 255, 255, 255))
    out = Image.alpha_composite(bg, pil_rgba)
    return out.convert("RGB")


# -----------------------------
# Node
# -----------------------------

class KeyingRemoveBackgroundRembg:
    """
    Keying Remove Background (rembg) - Local Models Only

    Outputs:
      - image: IMAGE (RGB)
      - mask:  MASK (alpha 0..1)

    Models must exist at:
      <ComfyUI>/models/u2net/
        - isnet-anime.onnx
        - isnet-general-use.onnx
        - u2net.onnx
        - u2netp.onnx
    """

    _SESSIONS: Dict[str, object] = {}
    _LOCAL_MODEL_DIR: str | None = None

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "model": (
                    [
                        "isnet-general-use",
                        "u2net",
                        "u2netp",
                        "isnet-anime",
                    ],
                    {"default": "isnet-general-use"},
                ),
                "output_mode": (["cutout", "white_bg"], {"default": "cutout"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "run"
    CATEGORY = "Keying/Image"

    def _comfy_root(self) -> str:
        # __file__ = .../ComfyUI/custom_nodes/<this_node>/__init__.py
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    def _force_local_models(self) -> str:
        """
        Force rembg to use ComfyUI/models/u2net as model cache dir,
        and refuse to auto-download if files are missing.
        """
        if self._LOCAL_MODEL_DIR is not None:
            # Ensure env stays consistent (in case something else modified it)
            os.environ["U2NET_HOME"] = self._LOCAL_MODEL_DIR
            return self._LOCAL_MODEL_DIR

        root = self._comfy_root()
        model_dir = os.path.join(root, "models", "u2net")

        required_files = {
            "isnet-anime.onnx",
            "isnet-general-use.onnx",
            "u2net.onnx",
            "u2netp.onnx",
        }

        missing = [fn for fn in sorted(required_files) if not os.path.isfile(os.path.join(model_dir, fn))]
        if missing:
            raise FileNotFoundError(
                "KeyingRembg: 缺少本地模型文件，已禁止自动下载。\n"
                f"请把以下文件放到：{model_dir}\n"
                + "\n".join([f"- {m}" for m in missing])
            )

        # Force rembg to use this directory instead of ~/.u2net
        os.environ["U2NET_HOME"] = model_dir
        self._LOCAL_MODEL_DIR = model_dir
        return model_dir

    def _get_session(self, model_name: str):
        # ✅ Force local-only model dir before creating session
        self._force_local_models()

        s = self._SESSIONS.get(model_name)
        if s is None:
            s = new_session(model_name)
            self._SESSIONS[model_name] = s
        return s

    def run(self, image: torch.Tensor, model: str, output_mode: str):
        image = _ensure_4d_image(image)  # [B,H,W,C]
        session = self._get_session(model)

        out_images: List[torch.Tensor] = []
        out_masks: List[torch.Tensor] = []

        b = image.shape[0]
        for i in range(b):
            pil_in = tensor_image_to_pil_rgb(image[i:i + 1])
            out = remove(pil_in, session=session)
            pil_out = open_rembg_output(out).convert("RGBA")

            mask_t = pil_alpha_to_tensor_mask(pil_out)  # [1,H,W]
            out_masks.append(mask_t)

            if output_mode == "white_bg":
                pil_rgb = composite_on_white(pil_out)
            else:
                pil_rgb = pil_out.convert("RGB")

            img_t = pil_rgb_to_tensor_image(pil_rgb)  # [1,H,W,3]
            out_images.append(img_t)

        images_batch = torch.cat(out_images, dim=0)  # [B,H,W,3]
        masks_batch = torch.cat(out_masks, dim=0)    # [B,H,W]
        return (images_batch, masks_batch)


NODE_CLASS_MAPPINGS = {
    "Keying Remove Background (rembg)": KeyingRemoveBackgroundRembg
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Keying Remove Background (rembg)": "Keying Remove Background (rembg)"
}