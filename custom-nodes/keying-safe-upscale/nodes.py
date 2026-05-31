import math
import comfy
import torch


class KeyingMakeImageContiguous:
    """
    把 IMAGE tensor 强制变成 contiguous。
    注意：只能保证输入连续；如果后面节点切 tile 产生 view，仍可能触发 MPS 的 stride 问题。
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"
    CATEGORY = "Keying/Image"

    def execute(self, image):
        # image: [B,H,W,C] float tensor
        return (image.contiguous(),)


def _count_tiles(h: int, w: int, tile: int, overlap: int) -> int:
    """
    估算切块数量，用于进度条 total。
    step = tile - overlap
    """
    if tile <= 0:
        return 1
    step = max(1, tile - overlap)
    nx = max(1, math.ceil(max(1, w - overlap) / step))
    ny = max(1, math.ceil(max(1, h - overlap) / step))
    return nx * ny


class KeyingUpscaleWithModelSafe:
    """
    安全版 Upscale With Model：
    - 使用官方 Load Upscale Model 输出的 UPSCALE_MODEL
    - 在每个 tile 输入模型前强制 contiguous，避免 MPS 上的 view/stride 报错
    - 增加进度条（按 tile 推进）
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "upscale_model": ("UPSCALE_MODEL",),
                "image": ("IMAGE",),
                "tile": ("INT", {"default": 512, "min": 0, "max": 4096, "step": 64}),
                "overlap": ("INT", {"default": 64, "min": 0, "max": 256, "step": 8}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"
    CATEGORY = "Keying/Image"

    def execute(self, upscale_model, image, tile, overlap):
        # ComfyUI IMAGE: [B,H,W,C] -> 模型一般吃 [B,C,H,W]
        in_img = image.movedim(-1, 1).contiguous()  # 先整体 contiguous 一次

        def _run(tile_tensor: torch.Tensor) -> torch.Tensor:
            # 关键：tile 切片常是 view（非连续），这里强制 contiguous
            return upscale_model(tile_tensor.contiguous())

        b, c, h, w = in_img.shape
        tile = int(tile) if tile is not None else 0
        overlap = int(overlap)

        # 进度条：tile 数 * batch
        total_tiles = _count_tiles(h, w, tile, overlap) * int(b)
        pbar = comfy.utils.ProgressBar(total_tiles)

        # tile=0 代表不分块（最稳但更吃内存）
        if tile <= 0:
            out = _run(in_img)
            # 直接一次完成
            pbar.update(total_tiles)
        else:
            out = comfy.utils.tiled_scale(
                in_img,
                _run,
                tile_x=tile,
                tile_y=tile,
                overlap=overlap,
                upscale_amount=upscale_model.scale,
                pbar=pbar,  # ✅ 传入进度条，让 tiled_scale 自动更新
            )

        # back to [B,H,W,C]
        out = out.movedim(1, -1).contiguous()
        return (out,)


NODE_CLASS_MAPPINGS = {
    "KeyingMakeImageContiguous": KeyingMakeImageContiguous,
    "KeyingUpscaleWithModelSafe": KeyingUpscaleWithModelSafe,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KeyingMakeImageContiguous": "Keying Make Image Contiguous",
    "KeyingUpscaleWithModelSafe": "Keying Upscale With Model (Safe)",
}