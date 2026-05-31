# -*- coding = utf-8 -*-
# @Time: 2026/1/13 下午9:12
# @Author: 柯影数智
# @File: __init__.py
# @Email: 1090461393@qq.com
# @SoftWare: PyCharm

import numpy as np
import torch


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


# 常用电商/设计背景色预设（你可以随时加）
PRESET_COLORS = {
    "Pure White #FFFFFF": (255, 255, 255),
    "Studio Gray #F7F7F7": (247, 247, 247),   # 电商棚拍感（推荐）
    "Warm White #FAFAF5": (250, 250, 245),    # 米白偏暖
    "Light Gray #EEEEEE": (238, 238, 238),
    "Mid Gray #CCCCCC": (204, 204, 204),
    "Dark Gray #333333": (51, 51, 51),
    "Pure Black #000000": (0, 0, 0),
    "Brand Blue #1677FF": (22, 119, 255),     # 示例品牌色
}


class KeyingSolidCanvas:
    """
    纯色画布（可自动获取参考图像宽高）
    输出：IMAGE [B,H,W,3] float32 in [0,1]

    说明：
    - preset != (Custom RGB) 时：r/g/b 会被忽略（不可生效）
    - preset == (Custom RGB) 时：r/g/b 才会生效
    """

    CUSTOM_PRESET = "(Custom RGB)"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # 尺寸来源
                "auto_from_image": ("BOOLEAN", {"default": True}),
                "width": ("INT", {"default": 1024, "min": 1, "max": 16384}),
                "height": ("INT", {"default": 1024, "min": 1, "max": 16384}),
                "batch_mode": (["match_reference", "single"], {"default": "match_reference"}),

                # 常用背景色预设（✅ Custom 时才读取 r/g/b）
                "preset": ([cls.CUSTOM_PRESET] + list(PRESET_COLORS.keys()), {"default": "Studio Gray #F7F7F7"}),

                # 仅当 preset == (Custom RGB) 时生效
                "r": ("INT", {"default": 255, "min": 0, "max": 255}),
                "g": ("INT", {"default": 255, "min": 0, "max": 255}),
                "b": ("INT", {"default": 255, "min": 0, "max": 255}),
            },
            "optional": {
                "reference_image": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "make"
    CATEGORY = "Keying/Image"

    def make(
        self,
        auto_from_image: bool,
        width: int,
        height: int,
        batch_mode: str,
        preset: str,
        r: int,
        g: int,
        b: int,
        reference_image=None,
    ):
        ref = _ensure_image_4d(reference_image)

        # 1) 颜色选择：preset 优先；只有 Custom 才读 r/g/b
        if preset == self.CUSTOM_PRESET:
            rr, gg, bb = int(r), int(g), int(b)
        else:
            rr, gg, bb = PRESET_COLORS.get(preset, (255, 255, 255))

        # 2) 尺寸 & batch
        if auto_from_image and ref is not None:
            B, H, W, _ = ref.shape
            out_h, out_w = int(H), int(W)
            out_b = int(B) if batch_mode == "match_reference" else 1
        else:
            out_w, out_h = int(width), int(height)
            out_b = int(ref.shape[0]) if (ref is not None and batch_mode == "match_reference") else 1

        # 3) 生成画布
        canvas = np.empty((out_h, out_w, 3), dtype=np.float32)
        canvas[..., 0] = rr / 255.0
        canvas[..., 1] = gg / 255.0
        canvas[..., 2] = bb / 255.0

        t = torch.from_numpy(canvas).unsqueeze(0)  # [1,H,W,3]
        if out_b > 1:
            t = t.repeat(out_b, 1, 1, 1)  # [B,H,W,3]
        return (t,)


NODE_CLASS_MAPPINGS = {
    "Keying Solid Canvas": KeyingSolidCanvas
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Keying Solid Canvas": "Keying Solid Canvas (Auto Size)"
}