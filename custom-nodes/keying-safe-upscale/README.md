# Keying Safe Upscale Nodes (ComfyUI)

一组用于 **ComfyUI** 的自定义节点，专门解决在 **macOS / MPS** 环境下进行 **Upscale With Model** 时，因 **tile 切片产生 view（非连续张量）** 导致的 `stride` / `view` 相关报错问题。

本插件提供两个节点：

- **Keying Make Image Contiguous**：把 `IMAGE` 张量强制变成 contiguous（连续内存）
- **Keying Upscale With Model (Safe)**：安全版 “Upscale With Model”，对每个 tile 在送入模型前强制 contiguous，并提供按 tile 的进度条

---

## 功能亮点

- ✅ 兼容 ComfyUI 官方 `Load Upscale Model` 输出的 `UPSCALE_MODEL`
- ✅ 每个 tile 推理前 `contiguous()`，显著降低 MPS 上的 view/stride 报错概率
- ✅ 支持 tile / overlap 分块超分，内存压力可控
- ✅ 支持 `tile=0`（不分块）获得最稳结果
- ✅ 进度条按 tile 推进（更符合大图超分的体验）

---

## 安装

把本仓库放到 ComfyUI 的 `custom_nodes/` 目录下：

```bash
cd /path/to/ComfyUI/custom_nodes
git clone <your_repo_url> keying-safe-upscale
```

然后重启 ComfyUI。

> 目录结构示例：
```txt
ComfyUI/
  custom_nodes/
    keying-safe-upscale/
      __init__.py
      nodes.py
      README.md
```

---

## 节点说明

### 1) Keying Make Image Contiguous

**用途**：将 ComfyUI 的 `IMAGE`（形状通常为 `[B,H,W,C]`）强制转为连续内存布局，减少后续算子在 MPS 上因 stride 不规则导致的问题。

**输入**
- `image (IMAGE)`

**输出**
- `IMAGE`

**备注**
- 该节点只能保证“输入张量”连续；如果后续节点（例如 tile 切片）再次产生 view，仍可能触发 stride 问题。此时建议使用下方的 Safe Upscale 节点。

---

### 2) Keying Upscale With Model (Safe)

**用途**：替代官方 Upscale With Model，核心改动是：
- 将 `IMAGE` 转为 `[B,C,H,W]` 后先整体 `contiguous()`
- 在 tiled 推理中，每个 tile 切片进入模型前再次 `contiguous()`
- 提供按 tile 数量估算的进度条

**输入**
- `upscale_model (UPSCALE_MODEL)`：来自 ComfyUI 官方 `Load Upscale Model`
- `image (IMAGE)`
- `tile (INT)`：默认 `512`
  - `0` 表示 **不分块**（最稳，但更吃内存）
- `overlap (INT)`：默认 `64`
  - 分块边缘重叠区域，降低接缝

**输出**
- `IMAGE`

---

## 推荐工作流连接方式

### 最常用
1. `Load Upscale Model`
2. `Keying Upscale With Model (Safe)`
3. （可选）后续保存/拼接/再处理节点

### 如果你想在更多节点前“提前保险”
- 在一些容易产生 view/stride 的处理前后插入：
  - `Keying Make Image Contiguous`

---

## 参数建议

- **tile**
  - `0`：不分块，稳定性最强（适合小图或显存/内存足够）
  - `512`：常用平衡值
  - `1024`：更少的 tile 数，速度可能更快，但更吃内存
- **overlap**
  - `32~96` 常用
  - 过小可能出现接缝；过大增加计算量

---

## 为什么会报错（MPS / stride / view）

在 macOS（尤其是 MPS）上，某些算子/模型对张量的 **内存连续性（contiguous）** 更敏感。

当进行 tile 推理时，切片得到的张量常是 **view（共享底层内存的非连续张量）**，可能导致：
- 运行时提示 stride 不支持
- view/reshape/contiguous 相关异常
- 某些模型在 tile 模式下直接崩溃

本插件通过在 **每个 tile 输入模型前强制 `contiguous()`** 来规避这类问题。

---

## 常见问题（FAQ）

### Q1：tile 设为 0 会更清晰吗？
不一定更清晰，主要是 **更稳**、更少 tile 接缝风险；清晰度更多取决于：
- 超分模型本身（4x / 2x）
- 输入分辨率与细节
- 后处理（锐化/降噪）

### Q2：为什么还要有 “Make Image Contiguous” 这个节点？
用于通用场景：当你不确定某个节点前后的张量布局时，可以用它做“保险”。  
但 **解决 tile 推理 view/stride 的关键** 是 Safe Upscale 节点在每个 tile 内部强制 contiguous。

### Q3：还是报错怎么办？
按优先级尝试：
1. 把 `tile=0`（不分块）
2. 降低 tile（如 512 → 384/256）
3. 增大 overlap（如 64 → 96）
4. 在上游插入 `Keying Make Image Contiguous`
5. 确认 ComfyUI 与 torch 版本、MPS 环境是否正常

---

## 版本与兼容性

- 依赖：ComfyUI（包含 `comfy.utils.tiled_scale` 与 `ProgressBar`）
- 后端：CPU / CUDA / MPS（重点优化 MPS 体验）

---

## License

按你的仓库实际 License 填写（MIT / Apache-2.0 / GPL 等）。
