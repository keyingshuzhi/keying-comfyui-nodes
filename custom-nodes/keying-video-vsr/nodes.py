# -*- coding: utf-8 -*-

import glob
import os
import re
import shutil
import subprocess
import uuid
from typing import Callable, List

import numpy as np
from PIL import Image
import torch

import comfy.utils
import folder_paths


# Register model folder: ComfyUI/models/video_vsr
if "video_vsr" not in folder_paths.folder_names_and_paths:
    _video_vsr_paths = [os.path.join(folder_paths.models_dir, "video_vsr")]
else:
    _video_vsr_paths, _ = folder_paths.folder_names_and_paths["video_vsr"]
folder_paths.folder_names_and_paths["video_vsr"] = (_video_vsr_paths, folder_paths.supported_pt_extensions)


VIDEO_EXTS = ["mp4", "mov", "mkv", "avi", "webm", "m4v", "flv", "ts", "mts", "m2ts", "3gp"]
VIDEO_EXT_SET = {f".{x}" for x in VIDEO_EXTS}
NO_VIDEO_CHOICE = "__no_video_in_input__"


def _resolve_path(path: str) -> str:
    if not path:
        return ""
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(os.getcwd(), path))


def _is_video_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXT_SET


def _list_video_files(folder: str, recursive: bool) -> List[str]:
    patterns = []
    if recursive:
        for ext in VIDEO_EXTS:
            patterns.append(os.path.join(folder, "**", f"*.{ext}"))
            patterns.append(os.path.join(folder, "**", f"*.{ext.upper()}"))
    else:
        for ext in VIDEO_EXTS:
            patterns.append(os.path.join(folder, f"*.{ext}"))
            patterns.append(os.path.join(folder, f"*.{ext.upper()}"))

    files: List[str] = []
    for pattern in patterns:
        files.extend(glob.glob(pattern, recursive=recursive))

    seen = set()
    unique = []
    for fp in files:
        if os.path.isfile(fp):
            name = os.path.basename(fp)
            if name.startswith("."):
                continue
            nfp = os.path.normpath(fp)
            if nfp not in seen:
                seen.add(nfp)
                unique.append(nfp)
    return unique


def _sort_files(files: List[str], sort: str) -> List[str]:
    if sort.startswith("name"):
        files = sorted(files, key=lambda x: os.path.basename(x).lower())
    else:
        files = sorted(files, key=lambda x: os.path.getmtime(x))

    if sort.endswith("desc"):
        files.reverse()
    return files


def _input_video_choices() -> List[str]:
    input_dir = folder_paths.get_input_directory()
    rels: List[str] = []

    if os.path.isdir(input_dir):
        for root, dirs, files in os.walk(input_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fn in files:
                if fn.startswith("."):
                    continue
                abs_fp = os.path.join(root, fn)
                if not _is_video_file(abs_fp):
                    continue
                rel = os.path.relpath(abs_fp, input_dir).replace("\\", "/")
                rels.append(rel)

    rels = sorted(list(set(rels)), key=lambda x: x.lower())
    return rels if rels else [NO_VIDEO_CHOICE]


def _input_folder_choices(video_choices: List[str]) -> List[str]:
    dirs = set(["."])
    input_dir = folder_paths.get_input_directory()

    vb = os.path.join(input_dir, "video_batch_in")
    if os.path.isdir(vb):
        dirs.add("video_batch_in")

    for rel in video_choices:
        if rel == NO_VIDEO_CHOICE:
            continue
        d = os.path.dirname(rel).replace("\\", "/")
        dirs.add(d if d else ".")

    # put video_batch_in first, then ., then others
    def _k(x: str):
        if x == "video_batch_in":
            return (0, x)
        if x == ".":
            return (1, x)
        return (2, x.lower())

    return sorted(dirs, key=_k)


def _resolve_input_video_relpath(rel_path: str) -> str:
    if not rel_path or rel_path == NO_VIDEO_CHOICE:
        raise FileNotFoundError(
            "input 目录未找到可用视频。请先把视频放到 ComfyUI/input 目录，再刷新节点。"
        )
    if os.path.isabs(rel_path):
        return _resolve_path(rel_path)
    return folder_paths.get_annotated_filepath(rel_path, default_dir=folder_paths.get_input_directory())


def _resolve_input_folder_relpath(rel_path: str) -> str:
    if not rel_path:
        rel_path = "."
    if os.path.isabs(rel_path):
        return _resolve_path(rel_path)
    return folder_paths.get_annotated_filepath(rel_path, default_dir=folder_paths.get_input_directory())


def _model_choices() -> List[str]:
    names = folder_paths.get_filename_list("video_vsr")
    names = [x for x in names if os.path.splitext(x)[1].lower() in folder_paths.supported_pt_extensions]
    return names if names else ["RealBasicVSR_x4.pth"]


def _infer_scale(model_name: str, scale_hint: int) -> int:
    m = re.search(r"(?:^|[^a-z0-9])x([2348])(?:[^a-z0-9]|$)", model_name.lower())
    if m:
        return int(m.group(1))

    lower = model_name.lower()
    if "realbasicvsr" in lower or "basicvsr" in lower or "rvrt" in lower:
        return 4

    return int(scale_hint)


def _make_vf_chain(scale: int, denoise_strength: float, temporal_strength: float, sharpen_strength: float) -> str:
    scale = max(1, int(scale))
    luma_spatial = max(0.0, float(denoise_strength))
    chroma_spatial = max(0.0, luma_spatial * 0.75)
    luma_tmp = max(0.0, float(temporal_strength))
    chroma_tmp = max(0.0, luma_tmp * 0.75)
    sharpen = max(0.0, float(sharpen_strength))

    return (
        "hqdn3d="
        f"luma_spatial={luma_spatial:.3f}:"
        f"chroma_spatial={chroma_spatial:.3f}:"
        f"luma_tmp={luma_tmp:.3f}:"
        f"chroma_tmp={chroma_tmp:.3f},"
        f"scale=w=iw*{scale}:h=ih*{scale}:flags=lanczos,"
        "unsharp="
        "luma_msize_x=5:luma_msize_y=5:"
        f"luma_amount={sharpen:.3f}:"
        "chroma_msize_x=5:chroma_msize_y=5:"
        "chroma_amount=0.0"
    )


def _ensure_unique_output_path(path: str, overwrite: bool) -> str:
    if overwrite or (not os.path.exists(path)):
        return path

    root, ext = os.path.splitext(path)
    idx = 1
    while True:
        cand = f"{root}_{idx:03d}{ext}"
        if not os.path.exists(cand):
            return cand
        idx += 1


def _parse_paths_from_text(text: str) -> List[str]:
    out = []
    for line in (text or "").splitlines():
        p = line.strip()
        if p:
            out.append(_resolve_path(p))
    return out


def _parse_names_from_text(text: str) -> List[str]:
    out = []
    for line in (text or "").splitlines():
        n = line.strip()
        if n:
            out.append(n)
    return out


def _resolve_codec(codec: str, output_format: str) -> str:
    if codec != "auto":
        return codec
    if output_format == "mkv":
        return "libx265"
    return "libx264"


def _collect_files(
    mode: str,
    single_video_file: str,
    batch_folder: str,
    recursive: bool,
    max_videos: int,
    start_index: int,
    sort: str,
    batch_list_paths: str,
) -> List[str]:
    if mode == "single_video":
        return [_resolve_input_video_relpath(single_video_file)]

    if mode == "batch_list":
        files = _parse_paths_from_text(batch_list_paths)
        if not files:
            raise ValueError("mode=batch_list 时，batch_list_paths 不能为空。")
        return files

    abs_folder = _resolve_input_folder_relpath(batch_folder)
    if not os.path.isdir(abs_folder):
        raise FileNotFoundError(f"Folder not found: {abs_folder}")

    files = _list_video_files(abs_folder, bool(recursive))
    if not files:
        raise FileNotFoundError(f"No videos found in: {abs_folder}")

    files = _sort_files(files, sort)
    files = files[start_index:start_index + max_videos]
    return files


def _ffprobe_duration_us(video_path: str) -> int:
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        return 0

    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            return 0
        s = (proc.stdout or "").strip()
        if not s:
            return 0
        seconds = float(s)
        return max(0, int(seconds * 1_000_000.0))
    except Exception:
        return 0


def _empty_preview_image() -> torch.Tensor:
    return torch.zeros((1, 64, 64, 3), dtype=torch.float32)


def _pil_to_image_tensor(pil_img: Image.Image) -> torch.Tensor:
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    arr = np.asarray(pil_img).astype(np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


def _extract_preview_image_tensor(video_path: str, seek_sec: float = 0.5) -> torch.Tensor:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return _empty_preview_image()

    preview_dir = os.path.join(folder_paths.get_temp_directory(), "keying_video_vsr_previews")
    os.makedirs(preview_dir, exist_ok=True)
    out_png = os.path.join(preview_dir, f"{uuid.uuid4().hex}.png")

    # try mid-frame first, then first frame fallback
    for ss in [max(0.0, float(seek_sec)), 0.0]:
        cmd = [
            ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{ss:.3f}",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-vf",
            "scale=640:-1:force_original_aspect_ratio=decrease",
            out_png,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0 and os.path.isfile(out_png):
            try:
                pil_img = Image.open(out_png)
                return _pil_to_image_tensor(pil_img)
            except Exception:
                pass

    return _empty_preview_image()


def _ffmpeg_run(
    input_path: str,
    output_path: str,
    vf_chain: str,
    codec: str,
    preset: str,
    crf: int,
    keep_audio: bool,
    overwrite: bool,
    progress_cb: Callable[[float], None] | None = None,
    duration_us: int = 0,
) -> None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("找不到 ffmpeg，请先安装 ffmpeg 并确保在 PATH 中可用。")

    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if overwrite else "-n",
        "-progress",
        "pipe:1",
        "-nostats",
        "-i",
        input_path,
        "-map",
        "0:v:0",
        "-vf",
        vf_chain,
        "-c:v",
        codec,
        "-preset",
        preset,
        "-crf",
        str(int(crf)),
        "-pix_fmt",
        "yuv420p",
    ]

    if keep_audio:
        cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]

    if output_path.lower().endswith(".mp4") or output_path.lower().endswith(".mov"):
        cmd += ["-movflags", "+faststart"]

    cmd += [output_path]

    # Merge stderr into stdout to avoid deadlocks while parsing progress lines.
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    last_ratio = 0.0
    logs: List[str] = []

    if proc.stdout is not None:
        for raw in proc.stdout:
            line = (raw or "").strip()
            if not line:
                continue
            logs.append(line)
            if len(logs) > 120:
                logs.pop(0)

            if progress_cb is None:
                continue

            if line.startswith("out_time_ms="):
                try:
                    out_time_us = int(line.split("=", 1)[1])
                except Exception:
                    continue

                if duration_us > 0:
                    ratio = max(0.0, min(1.0, out_time_us / float(duration_us)))
                else:
                    # unknown duration fallback: only push in small increments until end
                    ratio = min(0.98, last_ratio + 0.01)

                if ratio > last_ratio:
                    last_ratio = ratio
                    progress_cb(ratio)
            elif line == "progress=end":
                if last_ratio < 1.0:
                    last_ratio = 1.0
                    progress_cb(1.0)

    code = proc.wait()
    if code != 0:
        tail = "\n".join(logs[-20:])
        raise RuntimeError(tail if tail else "ffmpeg failed")


class KeyingVideoInput:
    """
    视频导入节点：
    - 下拉选择 input 目录中的视频文件（无需手动输路径）
    - 支持单视频 / 批量文件夹 / 批量列表
    - 输出首个视频的预览帧 IMAGE
    """

    @classmethod
    def INPUT_TYPES(cls):
        videos = _input_video_choices()
        folders = _input_folder_choices(videos)
        default_folder = "video_batch_in" if "video_batch_in" in folders else folders[0]

        return {
            "required": {
                "mode": (["single_video", "batch_folder", "batch_list"], {"default": "single_video"}),
                "single_video_file": (videos, {"default": videos[0]}),
                "batch_folder": (folders, {"default": default_folder}),
                "recursive": ("BOOLEAN", {"default": False}),
                "max_videos": ("INT", {"default": 9999, "min": 1, "max": 999999}),
                "start_index": ("INT", {"default": 0, "min": 0, "max": 999999}),
                "sort": (["name_asc", "name_desc", "mtime_asc", "mtime_desc"], {"default": "name_asc"}),
                "batch_list_paths": ("STRING", {"default": "", "multiline": True, "placeholder": "每行一个绝对路径（仅 batch_list 模式使用）"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT", "IMAGE")
    RETURN_NAMES = ("video_paths", "filenames", "count", "preview_image")
    FUNCTION = "load"
    CATEGORY = "Keying/Video"

    def load(self, mode, single_video_file, batch_folder, recursive, max_videos, start_index, sort, batch_list_paths):
        files = _collect_files(
            mode=mode,
            single_video_file=single_video_file,
            batch_folder=batch_folder,
            recursive=bool(recursive),
            max_videos=int(max_videos),
            start_index=int(start_index),
            sort=sort,
            batch_list_paths=batch_list_paths,
        )

        if not files:
            raise ValueError("没有可处理的视频。")

        paths = []
        names = []
        for fp in files:
            abs_fp = _resolve_path(fp)
            if not os.path.isfile(abs_fp):
                raise FileNotFoundError(f"Input video not found: {abs_fp}")
            paths.append(abs_fp)
            names.append(os.path.basename(abs_fp))

        preview = _extract_preview_image_tensor(paths[0])
        return ("\n".join(paths), "\n".join(names), len(paths), preview)


class KeyingVideoSingleInput:
    """
    单视频导入节点（优化版）：
    - 仅保留单视频下拉选择
    - 不输出当前这套预览，简化单视频流程交互
    """

    @classmethod
    def INPUT_TYPES(cls):
        videos = _input_video_choices()
        return {
            "required": {
                "single_video_file": (videos, {"default": videos[0]}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("video_paths", "filenames", "count")
    FUNCTION = "load"
    CATEGORY = "Keying/Video"

    def load(self, single_video_file):
        abs_fp = _resolve_input_video_relpath(single_video_file)
        if not os.path.isfile(abs_fp):
            raise FileNotFoundError(f"Input video not found: {abs_fp}")
        name = os.path.basename(abs_fp)
        return (abs_fp, name, 1)


class KeyingVideoBatchInput:
    """
    批量视频导入节点（仅文件夹）：
    - 下拉选择 input 目录中的文件夹
    - 不包含单视频文件参数，避免批量模式误操作
    - 输出首个视频预览
    """

    @classmethod
    def INPUT_TYPES(cls):
        videos = _input_video_choices()
        folders = _input_folder_choices(videos)
        default_folder = "video_batch_in" if "video_batch_in" in folders else folders[0]
        return {
            "required": {
                "batch_folder": (folders, {"default": default_folder}),
                "recursive": ("BOOLEAN", {"default": False}),
                "max_videos": ("INT", {"default": 9999, "min": 1, "max": 999999}),
                "start_index": ("INT", {"default": 0, "min": 0, "max": 999999}),
                "sort": (["name_asc", "name_desc", "mtime_asc", "mtime_desc"], {"default": "name_asc"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT", "IMAGE")
    RETURN_NAMES = ("video_paths", "filenames", "count", "preview_image")
    FUNCTION = "load"
    CATEGORY = "Keying/Video"

    def load(self, batch_folder, recursive, max_videos, start_index, sort):
        files = _collect_files(
            mode="batch_folder",
            single_video_file=NO_VIDEO_CHOICE,
            batch_folder=batch_folder,
            recursive=bool(recursive),
            max_videos=int(max_videos),
            start_index=int(start_index),
            sort=sort,
            batch_list_paths="",
        )
        if not files:
            raise ValueError("没有可处理的视频。")

        paths = []
        names = []
        for fp in files:
            abs_fp = _resolve_path(fp)
            if not os.path.isfile(abs_fp):
                raise FileNotFoundError(f"Input video not found: {abs_fp}")
            paths.append(abs_fp)
            names.append(os.path.basename(abs_fp))

        preview = _extract_preview_image_tensor(paths[0])
        return ("\n".join(paths), "\n".join(names), len(paths), preview)


class KeyingBatchLoadVideos:
    """
    兼容保留：仅文件夹批量读取视频。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {"default": "input/video_batch_in"}),
                "recursive": ("BOOLEAN", {"default": False}),
                "max_videos": ("INT", {"default": 9999, "min": 1, "max": 999999}),
                "start_index": ("INT", {"default": 0, "min": 0, "max": 999999}),
                "sort": (["name_asc", "name_desc", "mtime_asc", "mtime_desc"], {"default": "name_asc"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("video_paths", "filenames")
    FUNCTION = "load"
    CATEGORY = "Keying/Video"

    def load(self, folder, recursive, max_videos, start_index, sort):
        # legacy behavior: keep accepting manual folder path
        abs_folder = folder if os.path.isabs(folder) else _resolve_path(folder)
        if not os.path.isdir(abs_folder):
            raise FileNotFoundError(f"Folder not found: {abs_folder}")

        files = _list_video_files(abs_folder, bool(recursive))
        if not files:
            raise FileNotFoundError(f"No videos found in: {abs_folder}")

        files = _sort_files(files, sort)
        files = files[start_index:start_index + max_videos]

        paths = "\n".join([_resolve_path(x) for x in files])
        names = "\n".join([os.path.basename(x) for x in files])
        return (paths, names)


class KeyingVideoSuperResolutionProcess:
    """
    视频超分处理节点（中间节点，不负责最终导出）。

    交互优化：
    - 输出 preview_image 便于在工作流里直接预览
    - 内置 ComfyUI 进度条（按视频内进度 + 批处理总进度）
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_paths": ("STRING", {"default": "", "forceInput": True}),
                "model_name": (_model_choices(),),
                "scale_hint": ("INT", {"default": 4, "min": 1, "max": 8}),
                "backend": (["auto", "ffmpeg_temporal"], {"default": "auto"}),
                "denoise_strength": ("FLOAT", {"default": 1.2, "min": 0.0, "max": 20.0, "step": 0.1}),
                "temporal_strength": ("FLOAT", {"default": 2.2, "min": 0.0, "max": 20.0, "step": 0.1}),
                "sharpen_strength": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 5.0, "step": 0.05}),
                "temp_subfolder": ("STRING", {"default": "keying_video_vsr"}),
                "output_suffix": ("STRING", {"default": "_vsr"}),
                "output_format": (["mp4", "mkv", "mov"], {"default": "mp4"}),
                "video_codec": (["auto", "libx264", "libx265"], {"default": "auto"}),
                "crf": ("INT", {"default": 20, "min": 1, "max": 51}),
                "preset": (["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"], {"default": "slow"}),
                "keep_audio": ("BOOLEAN", {"default": True}),
                "overwrite_temp": ("BOOLEAN", {"default": False}),
                "stop_on_error": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "source_filenames": ("STRING", {"default": "", "forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "INT", "STRING", "IMAGE")
    RETURN_NAMES = ("processed_video_paths", "report", "processed_count", "source_filenames", "preview_image")
    FUNCTION = "run"
    CATEGORY = "Keying/Video"

    def run(
        self,
        video_paths,
        model_name,
        scale_hint,
        backend,
        denoise_strength,
        temporal_strength,
        sharpen_strength,
        temp_subfolder,
        output_suffix,
        output_format,
        video_codec,
        crf,
        preset,
        keep_audio,
        overwrite_temp,
        stop_on_error,
        source_filenames="",
    ):
        model_path = folder_paths.get_full_path("video_vsr", model_name)
        if model_path is None:
            raise FileNotFoundError(
                f"模型未找到: {model_name}\n"
                "请把权重放到 ComfyUI/models/video_vsr/ 目录下。"
            )

        if backend not in ("auto", "ffmpeg_temporal"):
            raise ValueError(f"Unsupported backend: {backend}")

        in_files = _parse_paths_from_text(video_paths)
        if not in_files:
            raise ValueError("video_paths 为空，无法处理。")

        passed_names = _parse_names_from_text(source_filenames)

        scale = _infer_scale(model_name, int(scale_hint))
        vf_chain = _make_vf_chain(scale, denoise_strength, temporal_strength, sharpen_strength)
        codec = _resolve_codec(video_codec, output_format)

        temp_dir = os.path.join(folder_paths.get_temp_directory(), temp_subfolder)
        os.makedirs(temp_dir, exist_ok=True)

        total_steps = max(1, len(in_files) * 1000)
        pbar = comfy.utils.ProgressBar(total_steps)

        processed_paths: List[str] = []
        out_names: List[str] = []
        report_lines: List[str] = [
            "backend=ffmpeg_temporal",
            f"model={model_name}",
            f"model_path={model_path}",
            "model_runtime=metadata_only",
            f"scale={scale}",
            f"videos={len(in_files)}",
            f"temp_dir={temp_dir}",
        ]

        progressed = 0

        for idx, in_fp in enumerate(in_files, start=1):
            abs_in = _resolve_path(in_fp)
            if not os.path.isfile(abs_in):
                msg = f"[{idx}] missing input: {abs_in}"
                report_lines.append(f"ERROR {msg}")
                if stop_on_error:
                    raise FileNotFoundError(msg)

                # mark this file slot as done to keep progress moving
                target = idx * 1000
                if target > progressed:
                    pbar.update(target - progressed)
                    progressed = target
                continue

            if idx - 1 < len(passed_names):
                base = os.path.splitext(os.path.basename(passed_names[idx - 1]))[0]
            else:
                base = os.path.splitext(os.path.basename(abs_in))[0]

            out_name = f"{base}{output_suffix}.{output_format}"
            out_fp = _ensure_unique_output_path(os.path.join(temp_dir, out_name), bool(overwrite_temp))

            duration_us = _ffprobe_duration_us(abs_in)
            file_last_step = 0

            def _progress_cb(ratio: float):
                nonlocal file_last_step, progressed
                step = int(max(0.0, min(1.0, ratio)) * 1000)
                if step <= file_last_step:
                    return
                target_global = (idx - 1) * 1000 + step
                if target_global > progressed:
                    pbar.update(target_global - progressed)
                    progressed = target_global
                file_last_step = step

            try:
                _ffmpeg_run(
                    input_path=abs_in,
                    output_path=out_fp,
                    vf_chain=vf_chain,
                    codec=codec,
                    preset=preset,
                    crf=int(crf),
                    keep_audio=bool(keep_audio),
                    overwrite=bool(overwrite_temp),
                    progress_cb=_progress_cb,
                    duration_us=duration_us,
                )
                processed_paths.append(out_fp)
                out_names.append(os.path.basename(abs_in))
                report_lines.append(f"OK [{idx}] {abs_in} -> {out_fp}")
            except Exception as e:
                report_lines.append(f"ERROR [{idx}] {abs_in}: {e}")
                if stop_on_error:
                    raise
            finally:
                # ensure per-file step is completed
                target = idx * 1000
                if target > progressed:
                    pbar.update(target - progressed)
                    progressed = target

        preview_source = processed_paths[0] if processed_paths else (in_files[0] if in_files else "")
        preview = _extract_preview_image_tensor(preview_source) if preview_source else _empty_preview_image()

        return (
            "\n".join(processed_paths),
            "\n".join(report_lines),
            len(processed_paths),
            "\n".join(out_names),
            preview,
        )


class KeyingVideoOutput:
    """
    视频导出节点：将处理后视频复制/移动到 output 目录。

    交互优化：
    - 输出 preview_image，便于最终结果可视化预览
    """

    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "processed_video_paths": ("STRING", {"default": "", "forceInput": True}),
                "subfolder": ("STRING", {"default": "video_vsr"}),
                "rename_mode": (["keep_processed_name", "use_source_filenames"], {"default": "keep_processed_name"}),
                "filename_suffix": ("STRING", {"default": ""}),
                "overwrite": ("BOOLEAN", {"default": False}),
                "move_files": ("BOOLEAN", {"default": False}),
                "stop_on_error": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "source_filenames": ("STRING", {"default": "", "forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "INT", "IMAGE")
    RETURN_NAMES = ("saved_paths", "saved_count", "preview_image")
    FUNCTION = "save"
    CATEGORY = "Keying/Video"

    def save(self, processed_video_paths, subfolder, rename_mode, filename_suffix, overwrite, move_files, stop_on_error, source_filenames=""):
        src_paths = _parse_paths_from_text(processed_video_paths)
        if not src_paths:
            raise ValueError("processed_video_paths 为空，无法导出。")

        source_names = _parse_names_from_text(source_filenames)

        out_dir = os.path.join(folder_paths.get_output_directory(), subfolder)
        os.makedirs(out_dir, exist_ok=True)

        saved = []

        for idx, src in enumerate(src_paths):
            abs_src = _resolve_path(src)
            if not os.path.isfile(abs_src):
                msg = f"[{idx + 1}] missing processed file: {abs_src}"
                if stop_on_error:
                    raise FileNotFoundError(msg)
                continue

            src_ext = os.path.splitext(abs_src)[1]
            if rename_mode == "use_source_filenames" and idx < len(source_names):
                base = os.path.splitext(os.path.basename(source_names[idx]))[0]
                dst_name = f"{base}{filename_suffix}{src_ext}"
            else:
                base = os.path.splitext(os.path.basename(abs_src))[0]
                dst_name = f"{base}{filename_suffix}{src_ext}"

            dst = _ensure_unique_output_path(os.path.join(out_dir, dst_name), bool(overwrite))

            try:
                if move_files:
                    shutil.move(abs_src, dst)
                else:
                    shutil.copy2(abs_src, dst)
                saved.append(dst)
            except Exception:
                if stop_on_error:
                    raise

        preview_source = saved[0] if saved else ""
        preview = _extract_preview_image_tensor(preview_source) if preview_source else _empty_preview_image()
        return ("\n".join(saved), len(saved), preview)


class KeyingVideoSuperResolution:
    """
    兼容保留：旧版一体化节点（导入+处理+导出）。
    """

    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        videos = _input_video_choices()
        folders = _input_folder_choices(videos)
        default_folder = "video_batch_in" if "video_batch_in" in folders else folders[0]

        return {
            "required": {
                "mode": (["single_video", "batch_folder", "batch_list"], {"default": "single_video"}),
                "single_video_file": (videos, {"default": videos[0]}),
                "batch_folder": (folders, {"default": default_folder}),
                "recursive": ("BOOLEAN", {"default": False}),
                "max_videos": ("INT", {"default": 9999, "min": 1, "max": 999999}),
                "start_index": ("INT", {"default": 0, "min": 0, "max": 999999}),
                "sort": (["name_asc", "name_desc", "mtime_asc", "mtime_desc"], {"default": "name_asc"}),
                "batch_list_paths": ("STRING", {"default": "", "multiline": True}),
                "model_name": (_model_choices(),),
                "scale_hint": ("INT", {"default": 4, "min": 1, "max": 8}),
                "backend": (["auto", "ffmpeg_temporal"], {"default": "auto"}),
                "denoise_strength": ("FLOAT", {"default": 1.2, "min": 0.0, "max": 20.0, "step": 0.1}),
                "temporal_strength": ("FLOAT", {"default": 2.2, "min": 0.0, "max": 20.0, "step": 0.1}),
                "sharpen_strength": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 5.0, "step": 0.05}),
                "output_subfolder": ("STRING", {"default": "video_vsr"}),
                "output_suffix": ("STRING", {"default": "_vsr"}),
                "output_format": (["mp4", "mkv", "mov"], {"default": "mp4"}),
                "video_codec": (["auto", "libx264", "libx265"], {"default": "auto"}),
                "crf": ("INT", {"default": 20, "min": 1, "max": 51}),
                "preset": (["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"], {"default": "slow"}),
                "keep_audio": ("BOOLEAN", {"default": True}),
                "overwrite": ("BOOLEAN", {"default": False}),
                "stop_on_error": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("saved_paths", "report", "processed_count")
    FUNCTION = "run"
    CATEGORY = "Keying/Video"

    def run(
        self,
        mode,
        single_video_file,
        batch_folder,
        recursive,
        max_videos,
        start_index,
        sort,
        batch_list_paths,
        model_name,
        scale_hint,
        backend,
        denoise_strength,
        temporal_strength,
        sharpen_strength,
        output_subfolder,
        output_suffix,
        output_format,
        video_codec,
        crf,
        preset,
        keep_audio,
        overwrite,
        stop_on_error,
    ):
        files = _collect_files(
            mode=mode,
            single_video_file=single_video_file,
            batch_folder=batch_folder,
            recursive=bool(recursive),
            max_videos=int(max_videos),
            start_index=int(start_index),
            sort=sort,
            batch_list_paths=batch_list_paths,
        )
        list_text = "\n".join([_resolve_path(x) for x in files])

        process = KeyingVideoSuperResolutionProcess()
        process_result = process.run(
            video_paths=list_text,
            model_name=model_name,
            scale_hint=scale_hint,
            backend=backend,
            denoise_strength=denoise_strength,
            temporal_strength=temporal_strength,
            sharpen_strength=sharpen_strength,
            temp_subfolder="keying_video_vsr_legacy",
            output_suffix=output_suffix,
            output_format=output_format,
            video_codec=video_codec,
            crf=crf,
            preset=preset,
            keep_audio=keep_audio,
            overwrite_temp=overwrite,
            stop_on_error=stop_on_error,
            source_filenames="",
        )
        if isinstance(process_result, dict):
            process_result = process_result.get("result", process_result)
        processed_paths, report, _count, out_names, _preview = process_result

        saver = KeyingVideoOutput()
        save_result = saver.save(
            processed_video_paths=processed_paths,
            subfolder=output_subfolder,
            rename_mode="keep_processed_name",
            filename_suffix="",
            overwrite=overwrite,
            move_files=True,
            stop_on_error=stop_on_error,
            source_filenames=out_names,
        )
        if isinstance(save_result, dict):
            save_result = save_result.get("result", save_result)
        saved_paths, saved_count, _preview2 = save_result

        report_merged = report + f"\nlegacy_saved={saved_count}"
        return (saved_paths, report_merged, saved_count)


NODE_CLASS_MAPPINGS = {
    "KeyingVideoInput": KeyingVideoInput,
    "KeyingVideoSingleInput": KeyingVideoSingleInput,
    "KeyingVideoBatchInput": KeyingVideoBatchInput,
    "KeyingBatchLoadVideos": KeyingBatchLoadVideos,
    "KeyingVideoSuperResolutionProcess": KeyingVideoSuperResolutionProcess,
    "KeyingVideoOutput": KeyingVideoOutput,
    "KeyingVideoSuperResolution": KeyingVideoSuperResolution,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KeyingVideoInput": "Keying Video Input",
    "KeyingVideoSingleInput": "Keying Video Single Input",
    "KeyingVideoBatchInput": "Keying Video Batch Input (Folder Only)",
    "KeyingBatchLoadVideos": "Keying Batch Load Videos (Folder)",
    "KeyingVideoSuperResolutionProcess": "Keying Video Super Resolution (Process)",
    "KeyingVideoOutput": "Keying Video Output",
    "KeyingVideoSuperResolution": "Keying Video Super Resolution",
}
