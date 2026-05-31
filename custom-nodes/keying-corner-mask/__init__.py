# -*- coding: utf-8 -*-
"""
Keying Corner Text Mask — 批量角落文本遮罩
- Input: reference IMAGE (optional but recommended)
- Output: MASK + preview IMAGE (方便预览)
- Mode: top_left / top_right / bottom_left / bottom_right / top_left+bottom_right / top_right+bottom_left
- Region defined by (width_ratio, height_ratio) and (margin_ratio, margin_px)
"""

import torch
import numpy as np


def _ensure_image_4d(x: torch.Tensor) -> torch.Tensor:
    if x is None:
        return None
    if not isinstance(x, torch.Tensor):
        raise TypeError(f"reference_image must be torch.Tensor, got {type(x)}")
    if x.dim() == 3:
        return x.unsqueeze(0)
    if x.dim() != 4:
        raise ValueError(f"reference_image must be IMAGE tensor with 3/4 dims, got {tuple(x.shape)}")
    return x


class KeyingCornerTextMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": ([
                    "top_left",
                    "top_right",
                    "bottom_left",
                    "bottom_right",
                    "top_left+bottom_right",
                    "top_right+bottom_left",
                ], {"default": "top_left"}),
                # 角落遮罩区域大小（用比例最稳，适配不同分辨率）
                "width_ratio": ("FLOAT", {"default": 0.38, "min": 0.05, "max": 0.95, "step": 0.01}),
                "height_ratio": ("FLOAT", {"default": 0.22, "min": 0.05, "max": 0.95, "step": 0.01}),
                # 边距：px + ratio 取最大值
                "margin_px": ("INT", {"default": 10, "min": 0, "max": 4096}),
                "margin_ratio": ("FLOAT", {"default": 0.02, "min": 0.0, "max": 0.2, "step": 0.005}),
                # 如果不传参考图，允许手填尺寸（一般不用）
                "fallback_width": ("INT", {"default": 1024, "min": 1, "max": 16384}),
                "fallback_height": ("INT", {"default": 1024, "min": 1, "max": 16384}),
                "batch_mode": (["match_reference", "single"], {"default": "match_reference"}),
            },
            "optional": {
                "reference_image": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("MASK", "IMAGE")
    RETURN_NAMES = ("mask", "mask_preview")
    FUNCTION = "make"
    CATEGORY = "Keying/Image"

    def _apply_rect(self, mask: np.ndarray, x0: int, y0: int, w: int, h: int):
        H, W = mask.shape
        x0 = max(0, min(x0, W))
        y0 = max(0, min(y0, H))
        x1 = max(0, min(x0 + w, W))
        y1 = max(0, min(y0 + h, H))
        mask[y0:y1, x0:x1] = 1.0

    def make(
        self,
        mode: str,
        width_ratio: float,
        height_ratio: float,
        margin_px: int,
        margin_ratio: float,
        fallback_width: int,
        fallback_height: int,
        batch_mode: str,
        reference_image=None,
    ):
        ref = _ensure_image_4d(reference_image)

        if ref is not None:
            B, H, W, _ = ref.shape
            out_b = int(B) if batch_mode == "match_reference" else 1
            H = int(H); W = int(W)
        else:
            out_b = 1
            H = int(fallback_height); W = int(fallback_width)

        # 区域大小
        rw = max(1, int(round(W * float(width_ratio))))
        rh = max(1, int(round(H * float(height_ratio))))

        # 边距
        m = max(int(margin_px), int(round(min(H, W) * float(margin_ratio))))

        # 生成单张 mask
        base_mask = np.zeros((H, W), dtype=np.float32)

        def rect_top_left():
            self._apply_rect(base_mask, m, m, rw, rh)

        def rect_top_right():
            self._apply_rect(base_mask, W - rw - m, m, rw, rh)

        def rect_bottom_left():
            self._apply_rect(base_mask, m, H - rh - m, rw, rh)

        def rect_bottom_right():
            self._apply_rect(base_mask, W - rw - m, H - rh - m, rw, rh)

        if mode == "top_left":
            rect_top_left()
        elif mode == "top_right":
            rect_top_right()
        elif mode == "bottom_left":
            rect_bottom_left()
        elif mode == "bottom_right":
            rect_bottom_right()
        elif mode == "top_left+bottom_right":
            rect_top_left()
            rect_bottom_right()
        else:  # top_right+bottom_left
            rect_top_right()
            rect_bottom_left()

        # batch 复制
        mask_bhw = np.repeat(base_mask[None, ...], out_b, axis=0)  # [B,H,W]
        mask_t = torch.from_numpy(mask_bhw)  # float32

        # 预览图（灰度3通道）
        preview = mask_t.unsqueeze(-1).repeat(1, 1, 1, 3)  # [B,H,W,3]
        return (mask_t, preview)


NODE_CLASS_MAPPINGS = {
    "Keying Corner Text Mask": KeyingCornerTextMask
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Keying Corner Text Mask": "Keying Corner Text Mask (Batch)"
}