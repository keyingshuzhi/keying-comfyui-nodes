# Keying Video VSR Nodes (ComfyUI)

视频超分自定义节点（导入 / 处理 / 导出三段式）。

## 使用手册

- 三节点手册（单视频优化链路）：`custom_nodes/keying-video-vsr/使用手册_三个新增节点.md`

## 交互优化

- 无需手动输入路径：
  - `Keying Video Input` 支持从 `ComfyUI/input` 自动扫描视频并下拉选择
- 预览可视化：
  - `Keying Video Input` 输出 `preview_image`（输入预览）
  - `Keying Video Super Resolution (Process)` 输出 `preview_image`（处理结果预览）
  - `Keying Video Output` 输出 `preview_image`（导出结果预览）
- 处理进度条：
  - `Keying Video Super Resolution (Process)` 内置 ComfyUI 进度条（按单视频进度 + 批处理总进度）

## 节点

- `Keying Video Input`
  - 支持：`single_video` / `batch_folder` / `batch_list`
  - 输出：`video_paths`、`filenames`、`count`、`preview_image`

- `Keying Video Super Resolution (Process)`
  - 输入：`video_paths`
  - 输出：`processed_video_paths`、`report`、`processed_count`、`source_filenames`、`preview_image`
  - 当前后端：`ffmpeg_temporal`（时序降噪 + Lanczos 放大 + 锐化）
  - 处理中间文件默认写入 `ComfyUI/temp/keying_video_vsr/`

- `Keying Video Output`
  - 输入：`processed_video_paths`
  - 导出到 `ComfyUI/output/<subfolder>/`
  - 输出：`saved_paths`、`saved_count`、`preview_image`

## 兼容节点

- `Keying Batch Load Videos (Folder)`：历史批量读取节点，保留可用。
- `Keying Video Super Resolution`：历史一体化节点（导入+处理+导出），保留可用。

## 推荐工作流

推荐使用三段式连线：

1. `Keying Video Input`
2. `Keying Video Super Resolution (Process)`
3. `Keying Video Output`

并把 `preview_image` 接到 `Preview Image` 节点做可视化。

## 模型目录

模型选择列表来自：

- `ComfyUI/models/video_vsr`

说明：

- 当前 `ffmpeg_temporal` 后端不会直接加载 `.pth` 权重做神经网络推理（权重在本版主要用于模型选择与倍率规范化）。

## 依赖

- 系统可执行 `ffmpeg`（需在 `PATH` 中）
