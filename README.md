# keying-comfyui-nodes / custom_nodes 目录说明（v1.0）

- GitHub 项目：`keying-comfyui-nodes`
- 版本：`v1.0`
- 日期：`2026-05-31`
- 适用范围：`ComfyUI/custom_nodes`

本文件用于整理 `custom_nodes` 目录内的节点来源、文档现状和提交规范，作为 `keying-comfyui-nodes` 仓库的发布基线说明。

## 1. 节点来源分类

### 1.1 第三方开源节点（保留原作者版权）

| 目录 | 说明文件 | 备注 |
| --- | --- | --- |
| `ComfyUI-IDM-VTON` | `README.md`（当前为空） | 目录已存在，但 README/LICENSE 为空文件，建议补齐来源仓库与许可证信息后再对外发布 |
| `ComfyUI-IPAdapter-plus` | `README.md` | 第三方开源节点 |
| `ComfyUI-TiledDiffusion` | `README.md` | 第三方开源节点 |

### 1.2 自研节点（Keying）

| 目录 | 主要节点（显示名） | 说明文件 |
| --- | --- | --- |
| `keying-batch-nodes` | `Keying Batch Load Images (Folder)` / `Keying Batch Save Images` | `README.md` |
| `keying-canvas-color` | `Keying Solid Canvas (Auto Size)` | `README.MD` |
| `keying-corner-mask` | `Keying Corner Text Mask (Batch)` | 暂无独立 README |
| `keying-mask-edge-ring` | `Keying Mask Edge Ring` | 暂无独立 README |
| `keying-prompt-assistant` | `CN Prompt Assistant (DeepSeek API)` / `CN Prompt Assistant (Ollama Local)` | `README.md` |
| `keying-rembg` | `Keying Remove Background (rembg)` | `README.md` |
| `keying-safe-upscale` | `Keying Make Image Contiguous` / `Keying Upscale With Model (Safe)` | `README.md` |
| `keying-video-vsr` | `Keying Video Input` / `Keying Video Super Resolution (Process)` / `Keying Video Output` 等 | `README.md`、`使用手册_三个新增节点.md` |
| `keying-watermark-overlay` | `Keying Watermark Text (柯影数智 AI生成)` | 暂无独立 README |

## 2. 自研节点开发规范（v1.0）

### 2.1 目录与命名

1. 每个节点包放在 `custom_nodes/keying-xxx/`。
2. 至少包含 `__init__.py`，必要时拆分 `nodes.py`。
3. `CATEGORY` 建议统一前缀为 `Keying/`（如 `Keying/Image`、`Keying/Video`）。

### 2.2 节点注册规范

1. 必须定义 `NODE_CLASS_MAPPINGS`。
2. 必须定义 `NODE_DISPLAY_NAME_MAPPINGS`。
3. 节点类中应包含：
   - `INPUT_TYPES`
   - `RETURN_TYPES`
   - `FUNCTION`
   - `CATEGORY`

### 2.3 数据格式约定

1. `IMAGE`：推荐使用 `[B, H, W, 3]`，`float32`，值域 `0~1`。
2. `MASK`：推荐使用 `[B, H, W]`，`float32`，值域 `0~1`。
3. 需要支持批处理时，避免因 `squeeze()` 导致维度坍塌。

### 2.4 文档最低要求

每个自研节点目录建议至少提供一个 `README.md`，包含：

1. 节点用途与适用场景
2. 输入/输出参数说明
3. 最小工作流示例
4. 依赖安装方式
5. 已知限制与注意事项

## 3. 第三方开源节点管理规范（v1.0）

1. 保留原始 `README`、`LICENSE` 和作者署名。
2. 若有二次修改，在对应目录新增“本地改动说明”（如 `LOCAL_CHANGES.md`）。
3. 禁止删除或覆盖第三方许可证文本。
4. 对外发布前，确认每个第三方目录都能追溯来源仓库与版本。

## 4. 发布检查清单（v1.0）

1. 清理缓存与系统文件：`__pycache__/`、`.DS_Store`。
2. 确认本文件已提交：`custom_nodes/README.md`。
3. 补齐自研缺失文档（当前缺失：`keying-corner-mask`、`keying-mask-edge-ring`、`keying-watermark-overlay`）。
4. 补齐第三方空文档（当前：`ComfyUI-IDM-VTON` 的 README/LICENSE 为空）。
5. 完成提交后打标签：`v1.0`。

---

如后续扩展到 `v1.1+`，建议在本文件末尾追加“版本变更记录”。
