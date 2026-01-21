# Keying Remove Background (rembg) — ComfyUI 自研抠图节点

这是一款面向**电商商品图工程化交付**的 ComfyUI 自定义节点，基于 `rembg` 实现**一键抠图**，并针对批量处理与稳定性做了增强：

- ✅ 修复传统实现的 `squeeze()` 形状坍塌问题（避免 PIL 报 `(1024,3)` 等非法形状）
- ✅ 支持 **Batch 输入**（IMAGE `[B,H,W,3]`）
- ✅ 同时输出 **前景图（IMAGE）+ Alpha 遮罩（MASK）**
- ✅ 可选直接输出 **白底主图**（省掉合成节点）
- ✅ rembg session 按模型缓存（同模型批处理更快）

---

## 1. 节点信息

- **节点名**：`Keying Remove Background (rembg)`
- **分类**：`Keying/Image`
- **输入**：
  - `image`：`IMAGE`（支持 batch）
  - `model`：rembg 模型名（`isnet-general-use/u2net/u2netp/isnet-anime`）
  - `output_mode`：`cutout` 或 `white_bg`
- **输出**：
  - `image`：`IMAGE`（RGB）
  - `mask`：`MASK`（alpha，0~1）

> 说明：本节点输出 `image` 为 RGB，透明信息通过 `mask` 输出。后续可用于 `GrowMask/FeatherMask/ImageCompositeMasked` 等工程化链路。

---

## 2. 安装方式（macOS / Windows / Linux）

### 2.1 放置节点文件

将代码保存到：

```
ComfyUI/
└─ custom_nodes/
   └─ keying_rembg/
      └─ __init__.py
```

### 2.2 安装依赖（在 ComfyUI 的 venv 中）

确保你在 ComfyUI 所使用的虚拟环境里安装依赖：

```bash
# 进入 ComfyUI 根目录（按你的实际路径）
cd /path/to/ComfyUI
source .venv/bin/activate

pip install -U pip
pip install rembg onnxruntime
```

> Apple Silicon（M1/M2/M3）一般使用 `onnxruntime` 即可。

### 2.3 重启 ComfyUI

重启后，在画布空白处右键搜索：

- `Keying Remove Background (rembg)`

---

## 3. 快速上手

### 3.1 最小工作流（抠图 + 保存）
```
Load Image → Keying Remove Background (rembg) → Save Image
```

如果你需要白底主图：
- 将 `output_mode` 设为 `white_bg`

### 3.2 工程化白底（推荐：可控修边）
更推荐使用 `cutout + mask` 方式把“提质步骤”显式放在工作流里：

```
Load → Keying Remove Background (cutout)
      ├─ image → (source)
      └─ mask  → GrowMask → FeatherMask → (mask)
SolidColor(白底) → (destination)
ImageCompositeMasked → Save
```

这样你可以通过 `GrowMask/FeatherMask` 做：
- 去白边（expand=-1~-2）
- 补漏抠（expand=+1）
- 羽化（0.5~1.5）

---

## 4. 参数建议（电商通用）

### model
- `isnet-general-use`：通用商品图优先
- `u2net`：稳定
- `u2netp`：更快更轻
- `isnet-anime`：偏二次元

### output_mode
- `cutout`：输出 RGB + mask（推荐，适合后处理与合成）
- `white_bg`：直接输出白底 RGB（省节点，但修边可控性更弱）

---

## 5. 常见问题（FAQ）

### Q1：为什么要输出 MASK，而不是直接输出透明 PNG？
ComfyUI 的 `IMAGE` 类型更通用（RGB），透明信息用 `MASK` 表达更适配 ComfyUI 的遮罩生态（修边、裁切、合成等）。

### Q2：batch 处理时尺寸不一致怎么办？
ComfyUI 的 batch 需要尺寸一致。建议在批量加载阶段统一尺寸（例如 `resize_to_first` 或固定尺寸），避免后续节点报错。

### Q3：我想输出透明 PNG（RGBA）可以吗？
可以扩展节点：增加第三个输出专门导出 RGBA（或在保存节点中支持 alpha）。当前版本推荐使用 `MASK` 作为 alpha 并在合成/保存环节控制输出格式。

---

## 6. 目录示例

```
ComfyUI/
  custom_nodes/
    keying_rembg/
      __init__.py
  input/
    batch_in/
  output/
    cutout/
    white/
```
