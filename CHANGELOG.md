# CHANGELOG

本文件记录 keying-comfyui-nodes 的节点变更，按版本倒序排列。

## [Unreleased]
- 无。

## [0.1.0]
### Added
- Keying Remove Background (rembg)：batch 输入，cutout/white_bg 输出，mask 输出，rembg session 缓存，本地模型路径强制（ComfyUI/models/u2net），避免 tensor squeeze 导致形状错误。
- Keying Batch Load Images (Folder) / Keying Batch Save Images：批量读写、递归扫描、排序、resize 策略、保留原文件名保存、输出节点声明。
- Keying Solid Canvas (Auto Size)：参考图自动尺寸、batch 输出、预设色 + Custom RGB 背景。
- CN Prompt Assistant (DeepSeek API / Ollama Local)：中文转英文正负向、profiles 模板、slots_json 输出。
- 初始依赖：`rembg[cpu]`、`ollama`。
