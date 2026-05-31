# -*- coding = utf-8 -*-
# @Time: 2026/1/13 下午8:09
# @Author: 柯影数智
# @File: __init__.py
# @Email: 1090461393@qq.com
# @SoftWare: PyCharm


import os
import glob
from typing import List, Tuple, Optional

import numpy as np
from PIL import Image

import torch
import folder_paths


def pil_to_tensor(pil: Image.Image) -> torch.Tensor:
    """
    PIL (RGB/RGBA) -> ComfyUI IMAGE tensor: [1, H, W, 3] float32 in [0,1]
    """
    if pil.mode not in ("RGB", "RGBA"):
        pil = pil.convert("RGBA")
    # drop alpha for IMAGE; alpha can be handled separately if needed
    if pil.mode == "RGBA":
        pil = pil.convert("RGB")
    arr = np.array(pil).astype(np.float32) / 255.0  # HWC
    t = torch.from_numpy(arr)[None, ...]  # 1,H,W,C
    return t


def tensor_to_pil(img: torch.Tensor) -> Image.Image:
    """
    ComfyUI IMAGE tensor: [H,W,3] or [1,H,W,3] float in [0,1] -> PIL RGB
    """
    if img.dim() == 4:
        img = img[0]
    img = img.detach().cpu().clamp(0, 1).numpy()
    arr = (img * 255.0).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


def list_images(folder: str, recursive: bool, exts: List[str]) -> List[str]:
    patterns = []
    if recursive:
        for e in exts:
            patterns.append(os.path.join(folder, "**", f"*.{e}"))
    else:
        for e in exts:
            patterns.append(os.path.join(folder, f"*.{e}"))
    files = []
    for p in patterns:
        files.extend(glob.glob(p, recursive=recursive))
    # 去掉隐藏文件/系统文件
    files = [f for f in files if os.path.isfile(f) and not os.path.basename(f).startswith(".")]
    return files


class KeyingBatchLoadImages:
    """
    从文件夹批量读取图片，输出 ComfyUI 的 IMAGE batch + 文件名列表（换行分隔）。
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "folder": ("STRING", {"default": "input/batch_in"}),
                "recursive": ("BOOLEAN", {"default": False}),
                "max_images": ("INT", {"default": 9999, "min": 1, "max": 999999}),
                "start_index": ("INT", {"default": 0, "min": 0, "max": 999999}),
                "sort": (["name_asc", "name_desc", "mtime_asc", "mtime_desc"], {"default": "name_asc"}),
                "resize_mode": (["resize_to_first", "no_resize_require_same"], {"default": "resize_to_first"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "filenames")
    FUNCTION = "load"
    CATEGORY = "Keying/Batch"

    def load(self, folder, recursive, max_images, start_index, sort, resize_mode):
        # 允许相对路径（相对 ComfyUI 根目录）
        base = os.getcwd()
        abs_folder = folder
        if not os.path.isabs(abs_folder):
            abs_folder = os.path.join(base, folder)

        if not os.path.isdir(abs_folder):
            raise FileNotFoundError(f"Folder not found: {abs_folder}")

        files = list_images(abs_folder, recursive, exts=["png", "jpg", "jpeg", "webp", "bmp"])
        if not files:
            raise FileNotFoundError(f"No images found in: {abs_folder}")

        # 排序
        if sort.startswith("name"):
            files.sort(key=lambda x: os.path.basename(x).lower())
            if sort.endswith("desc"):
                files.reverse()
        else:
            files.sort(key=lambda x: os.path.getmtime(x))
            if sort.endswith("desc"):
                files.reverse()

        files = files[start_index:start_index + max_images]

        tensors = []
        names = []
        target_wh: Optional[Tuple[int, int]] = None

        for fp in files:
            pil = Image.open(fp)
            pil = pil.convert("RGB")
            if target_wh is None:
                target_wh = pil.size  # (W,H)

            if resize_mode == "resize_to_first":
                if pil.size != target_wh:
                    pil = pil.resize(target_wh, resample=Image.LANCZOS)
            else:
                # no_resize_require_same
                if pil.size != target_wh:
                    raise ValueError(
                        f"Image size mismatch: first={target_wh}, current={pil.size}. "
                        f"Set resize_mode=resize_to_first to auto-resize."
                    )

            t = pil_to_tensor(pil)  # [1,H,W,3]
            tensors.append(t)
            names.append(os.path.basename(fp))

        batch = torch.cat(tensors, dim=0)  # [B,H,W,3]
        filenames = "\n".join(names)
        return (batch, filenames)


class KeyingBatchSaveImages:
    """
    批量保存 IMAGE batch。
    可用 filenames（换行分隔）来保持原文件名；否则用 index 命名。

    重要：OUTPUT_NODE=True 否则 ComfyUI 会认为“没有输出节点”，报 Prompt has no outputs
    """
    OUTPUT_NODE = True  # ✅ 关键修复：声明为输出节点

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "subfolder": ("STRING", {"default": "keying_batch"}),
                "format": (["png", "jpg"], {"default": "jpg"}),
                "quality": ("INT", {"default": 95, "min": 1, "max": 100}),
                "prefix": ("STRING", {"default": ""}),
            },
            "optional": {
                # ✅ 强制从连线输入，避免误把 filenames 连到 subfolder
                "filenames": ("STRING", {"default": "", "forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_paths",)
    FUNCTION = "save"
    CATEGORY = "Keying/Batch"

    def save(self, images, subfolder, format, quality, prefix, filenames=""):
        out_dir = folder_paths.get_output_directory()
        target_dir = os.path.join(out_dir, subfolder)
        os.makedirs(target_dir, exist_ok=True)

        # 解析 filenames（可为空）
        name_list = [x.strip() for x in (filenames or "").splitlines() if x.strip()]
        b = images.shape[0] if images.dim() == 4 else 1

        saved = []

        for i in range(b):
            img_i = images[i:i + 1] if images.dim() == 4 else images
            pil = tensor_to_pil(img_i)

            if i < len(name_list):
                base = os.path.splitext(name_list[i])[0]
            else:
                base = f"{i:05d}"

            if prefix:
                base = f"{prefix}{base}"

            fn = f"{base}.{format}"
            path = os.path.join(target_dir, fn)

            if format == "png":
                pil.save(path, format="PNG", optimize=True)
            else:
                pil.save(path, format="JPEG", quality=int(quality), optimize=True)

            saved.append(path)

        return ("\n".join(saved),)


NODE_CLASS_MAPPINGS = {
    "KeyingBatchLoadImages": KeyingBatchLoadImages,
    "KeyingBatchSaveImages": KeyingBatchSaveImages,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KeyingBatchLoadImages": "Keying Batch Load Images (Folder)",
    "KeyingBatchSaveImages": "Keying Batch Save Images",
}
