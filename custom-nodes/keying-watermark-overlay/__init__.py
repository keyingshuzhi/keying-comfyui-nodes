# -*- coding: utf-8 -*-
"""
Keying Text Watermark — ComfyUI 自研文字水印节点（固定文案）
- Batch supported: IMAGE [B,H,W,3]
- Watermark text is FIXED: "柯影数智 AI生成" (cannot be edited in UI)
- Position, margin, scale, opacity
- Optional stroke (outline) for readability
"""

import os
from typing import Tuple

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont


FIXED_WATERMARK_TEXT = "柯影数智 AI生成"


def _ensure_image_4d(x: torch.Tensor) -> torch.Tensor:
    if not isinstance(x, torch.Tensor):
        raise TypeError(f"Expected torch.Tensor, got {type(x)}")
    if x.dim() == 3:
        return x.unsqueeze(0)
    if x.dim() != 4:
        raise ValueError(f"Expected IMAGE tensor with 3/4 dims, got {tuple(x.shape)}")
    return x


def _tensor_to_pil(img_bhwc: torch.Tensor) -> Image.Image:
    img_bhwc = _ensure_image_4d(img_bhwc)
    img = img_bhwc[0].detach().to(torch.float32).clamp(0, 1).cpu().numpy()
    arr = (img * 255.0).round().astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


def _pil_to_tensor(pil: Image.Image) -> torch.Tensor:
    if pil.mode != "RGB":
        pil = pil.convert("RGB")
    arr = np.asarray(pil).astype(np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)  # [1,H,W,3]


def _load_font(font_path: str, font_size: int) -> ImageFont.FreeTypeFont:
    """
    Load a font that supports Chinese.
    - If font_path is provided and exists, use it.
    - Otherwise try common macOS Chinese fonts.
    - Fallback to PIL default (may NOT support Chinese).
    """
    candidates = []
    if font_path and os.path.isfile(font_path):
        candidates.append(font_path)

    # macOS common CJK fonts (add more if you like)
    candidates += [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]

    for p in candidates:
        try:
            if p and os.path.isfile(p):
                return ImageFont.truetype(p, font_size)
        except Exception:
            pass

    return ImageFont.load_default()


def _compute_position(pos: str, W: int, H: int, tw: int, th: int, margin: int) -> Tuple[int, int]:
    if pos == "top_left":
        return margin, margin
    if pos == "top_right":
        return max(margin, W - tw - margin), margin
    if pos == "bottom_left":
        return margin, max(margin, H - th - margin)
    if pos == "center":
        return (W - tw) // 2, (H - th) // 2
    # bottom_right
    return max(margin, W - tw - margin), max(margin, H - th - margin)


class KeyingFixedTextWatermark:
    """
    Fixed text watermark overlay for ComfyUI IMAGE batch.
    Text is fixed to: "柯影数智 AI生成"
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "position": (["top_left", "top_right", "bottom_left", "bottom_right", "center"], {"default": "bottom_right"}),
                "opacity": ("FLOAT", {"default": 0.22, "min": 0.0, "max": 1.0, "step": 0.01}),
                # Font size scales with short edge
                "font_size_ratio": ("FLOAT", {"default": 0.035, "min": 0.01, "max": 0.2, "step": 0.005}),
                "margin_ratio": ("FLOAT", {"default": 0.02, "min": 0.0, "max": 0.2, "step": 0.005}),
                "margin_px": ("INT", {"default": 24, "min": 0, "max": 4096}),
                "color": (["white", "black"], {"default": "white"}),

                # Stroke for readability
                "stroke_width": ("INT", {"default": 2, "min": 0, "max": 20}),
                "stroke_opacity": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01}),
                "stroke_color": (["black", "white"], {"default": "black"}),

                # Optional font path (recommended to provide a CJK font for portability)
                "font_path": ("STRING", {"default": ""}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "apply"
    CATEGORY = "Keying/Image"

    def apply(
        self,
        image: torch.Tensor,
        position: str,
        opacity: float,
        font_size_ratio: float,
        margin_ratio: float,
        margin_px: int,
        color: str,
        stroke_width: int,
        stroke_opacity: float,
        stroke_color: str,
        font_path: str,
    ):
        text = FIXED_WATERMARK_TEXT

        img = _ensure_image_4d(image).detach().to(torch.float32).clamp(0, 1).cpu()
        B, H, W, _ = img.shape

        short = min(H, W)
        font_size = max(10, int(round(short * float(font_size_ratio))))
        margin = max(int(margin_px), int(round(short * float(margin_ratio))))

        fill_rgb = (255, 255, 255) if color == "white" else (0, 0, 0)
        stroke_rgb = (0, 0, 0) if stroke_color == "black" else (255, 255, 255)

        fill_rgba = (*fill_rgb, int(round(255 * float(opacity))))
        stroke_rgba = (*stroke_rgb, int(round(255 * float(stroke_opacity))))

        font = _load_font(font_path, font_size)

        out_batch = []
        for i in range(B):
            pil = _tensor_to_pil(img[i:i + 1])
            base = pil.convert("RGBA")

            overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            bbox = draw.textbbox((0, 0), text, font=font, stroke_width=max(0, int(stroke_width)))
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            x, y = _compute_position(position, W, H, tw, th, margin)

            draw.text(
                (x, y),
                text,
                font=font,
                fill=fill_rgba,
                stroke_width=max(0, int(stroke_width)),
                stroke_fill=stroke_rgba if stroke_width > 0 else None,
            )

            merged = Image.alpha_composite(base, overlay).convert("RGB")
            out_batch.append(_pil_to_tensor(merged))

        out = torch.cat(out_batch, dim=0)  # [B,H,W,3]
        return (out,)


NODE_CLASS_MAPPINGS = {
    "Keying Fixed Text Watermark": KeyingFixedTextWatermark
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Keying Fixed Text Watermark": "Keying Watermark Text (柯影数智 AI生成)"
}