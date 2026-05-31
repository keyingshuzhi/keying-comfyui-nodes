# Keying Solid Canvas (Auto Size) — ComfyUI 自研纯色画布节点（预设色 + Custom RGB）

这是一个用于**生成纯色画布/底图**的 ComfyUI 自定义节点，面向电商商品图“工程化交付”场景，支持：

- ✅ **自动获取参考图像尺寸**（从输入 `reference_image` 读取宽高）
- ✅ **支持自定义宽高**（关闭自动模式即可）
- ✅ 支持 **常用背景色预设**（棚拍灰、纯白、暖白、浅灰等）
- ✅ 支持 **Custom RGB**（只有当 `preset = (Custom RGB)` 时，r/g/b 才会生效）
- ✅ 支持 **Batch 输出**（可跟随参考图的 batch 数，适配批量合成）

> 说明：ComfyUI 前端不支持“动态禁用控件”，因此 r/g/b 在 UI 中会一直显示；但**只有 preset 选为 (Custom RGB) 时，r/g/b 才会参与生成**。其它 preset 下 r/g/b 会被忽略。

---

## 1. 节点信息

- **节点名**：`Keying Solid Canvas (Auto Size)`
- **分类**：`Keying/Image`
- **输出**：`image`（`IMAGE`，RGB，float32，范围 0~1，形状 `[B,H,W,3]`）

### 输入参数（required）

| 参数 | 说明 | 默认 |
|---|---|---|
| auto_from_image | 是否从参考图自动取尺寸 | True |
| width / height | 自定义尺寸（auto 关闭或无参考图时生效） | 1024 / 1024 |
| batch_mode | 输出 batch 策略：`match_reference` 或 `single` | match_reference |
| preset | 背景色预设（含 `(Custom RGB)`） | Studio Gray #F7F7F7 |
| r / g / b | 仅当 `preset=(Custom RGB)` 时生效 | 255/255/255 |

### 输入参数（optional）

| 参数 | 说明 |
|---|---|
| reference_image | 参考图像（用于自动宽高 & 可选 batch 数） |

---

## 2. 内置背景色预设（可扩展）

节点内置一组电商/设计常用背景色，你可以在代码 `PRESET_COLORS` 中增删：

- `Pure White #FFFFFF`：纯白（主图通用）
- `Studio Gray #F7F7F7`：电商棚拍灰（推荐默认）
- `Warm White #FAFAF5`：暖白/米白
- `Light Gray #EEEEEE`
- `Mid Gray #CCCCCC`
- `Dark Gray #333333`
- `Pure Black #000000`
- `Brand Blue #1677FF`：示例品牌色（可替换为你们品牌色）
- `(Custom RGB)`：自定义 RGB（读取 r/g/b）

---

## 3. 安装方式

将代码保存到：

```
ComfyUI/
└─ custom_nodes/
   └─ keying_canvas_color/
      └─ __init__.py
```

然后重启 ComfyUI。

> 本节点仅依赖 `numpy`，且 ComfyUI 环境通常已包含；一般无需单独写 requirements。

---

## 4. 快速上手

### 4.1 自动跟随参考图尺寸（推荐）
用于电商白底合成：背景自动与前景尺寸一致。

```
(rembg 输出) ───────────────┐
                            │
Keying Solid Canvas(reference_image=rembg, auto_from_image=True, preset=Studio Gray #F7F7F7)
        └── canvas → ImageCompositeMasked.destination

(rembg 输出) → ImageCompositeMasked.source
(mask 链路)  → ImageCompositeMasked.mask
```

优点：
- 背景尺寸自动匹配前景
- 批量时输出 batch 一致，不易报维度错误

---

### 4.2 自定义画布尺寸（主图统一构图）
例如统一生成 1024×1024 画布：

- `auto_from_image = False`
- `width = 1024`
- `height = 1024`
- `preset = Studio Gray #F7F7F7`（或 Pure White）

---

### 4.3 使用 Custom RGB（仅此时 r/g/b 生效）
- `preset = (Custom RGB)`
- 设置 `r/g/b`（例如：`255/255/255`）

> 若 preset 不是 `(Custom RGB)`，则 r/g/b 会被忽略。

---

## 5. 参数建议（电商常用）

### 背景色推荐
- 纯白：`Pure White #FFFFFF`
- 轻灰白（更像棚拍）：`Studio Gray #F7F7F7`
- 暖白：`Warm White #FAFAF5`

### batch_mode 推荐
- 批量处理：`match_reference`
- 单图测试：`single`

---

## 6. 常见问题（FAQ）

### Q1：为什么输出是 RGB，没有 alpha？
该节点负责生成“背景画布”，一般连接到 `ImageCompositeMasked.destination`。  
透明信息来自前景图/遮罩链路（例如 rembg 输出 alpha → mask）。

### Q2：为什么 r/g/b 不会随时生效？
只有当 `preset = (Custom RGB)` 时，r/g/b 才会参与生成。其他预设色会直接覆盖 r/g/b。

### Q3：能不能让 UI 里 r/g/b 在非 Custom 时不可编辑/隐藏？
ComfyUI 前端通常不支持动态禁用/隐藏控件。更产品化的替代方案是拆成两个节点：
- `Canvas Preset`（只选 preset）
- `Canvas RGB`（只输入 r/g/b）
如你需要我可以继续拆分给你。

---

## 7. 目录示例

```
ComfyUI/
  custom_nodes/
    keying_canvas_color/
      __init__.py
  input/
    batch_in/
  output/
    white/
```

---

## 8. License
按你们项目需要填写（MIT / Apache-2.0 / 私有协议等）。
