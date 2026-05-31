import torch
import torch.nn.functional as F

def _to_b1hw(mask_bhw: torch.Tensor) -> torch.Tensor:
    if mask_bhw.dim() != 3:
        raise ValueError(f"MASK must be [B,H,W], got {tuple(mask_bhw.shape)}")
    return mask_bhw.unsqueeze(1)

def _to_bhw(mask_b1hw: torch.Tensor) -> torch.Tensor:
    return mask_b1hw.squeeze(1)

def _dilate(x_b1hw: torch.Tensor, r: int) -> torch.Tensor:
    k = 2 * r + 1
    return F.max_pool2d(x_b1hw, kernel_size=k, stride=1, padding=r)

def _erode(x_b1hw: torch.Tensor, r: int) -> torch.Tensor:
    k = 2 * r + 1
    return -F.max_pool2d(-x_b1hw, kernel_size=k, stride=1, padding=r)

class KeyingMaskEdgeRing:
    """
    只提取 mask 的边缘环带（ring mask）：
    ring = dilate(mask, outer) - erode(mask, inner)
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask": ("MASK",),
                "outer": ("INT", {"default": 6, "min": 1, "max": 128, "step": 1}),
                "inner": ("INT", {"default": 3, "min": 1, "max": 128, "step": 1}),
            }
        }

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("edge_ring_mask",)
    FUNCTION = "execute"
    CATEGORY = "Keying/Mask"

    def execute(self, mask, outer, inner):
        m = mask.contiguous().clamp(0.0, 1.0)  # [B,H,W]
        x = _to_b1hw(m)                        # [B,1,H,W]

        outer = int(outer)
        inner = int(inner)

        out = _dilate(x, outer)
        inn = _erode(x, inner)

        ring = (out - inn).clamp(0.0, 1.0)
        return (_to_bhw(ring),)

NODE_CLASS_MAPPINGS = {
    "KeyingMaskEdgeRing": KeyingMaskEdgeRing
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KeyingMaskEdgeRing": "Keying Mask Edge Ring"
}