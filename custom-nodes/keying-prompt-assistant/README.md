# CN Prompt Assistant (DeepSeek / Ollama) for ComfyUI

一个 **ComfyUI 自定义节点**：让用户用**中文**输入创意，节点自动生成 **英文结构化正向提示词（positive）** 和 **英文负向提示词（negative）**，用于在 ComfyUI 中更稳定地出图。

> ✅ 适用场景：工作流里大多数模型都以英文 prompt 为主（SD/SDXL/Lumina 系列等），但你希望终端用户只写中文也能稳定产出。

---

## 功能特性

- **中文输入 → 英文输出**（正向/负向）
- **两种后端模式（一个节点切换）**
  - `deepseek_api`：调用 DeepSeek API（当前仅支持 DeepSeek）
  - `ollama_local`：本地 Ollama 推理（离线、低延迟）
- **结构化槽位（Slots）输出**
  - 同时输出 `slots_json`，方便调试、二次编辑、做 UI 表单化
- **模型 Profile（模板化渲染）**
  - `lumina`：自动添加 Lumina/Neta Lumina 推荐固定前缀
  - `universal`：通用模型（不加前缀，更适配 SD/SDXL 等）
- **负向词库分档**
  - `basic` / `strong` 两档，提升稳定性与可控性

---

## 安装

### 1) 放到 ComfyUI 的 custom_nodes

将本项目目录放到：

`ComfyUI/custom_nodes/keying_prompt_assistant/`

目录结构示例：

```
keying_prompt_assistant/
  __init__.py
  cn_prompt_assistant.py
  profiles/
    lumina.json
    universal.json
```

### 2) 安装依赖

本节点默认使用 `requests` 发起 HTTP 请求（DeepSeek / Ollama）。

在 ComfyUI 的 Python 环境里安装：

```
pip install requests
```

> 如果你已经在其他节点里安装过 requests，可以跳过。

### 3) 重启 ComfyUI

重启后，在节点列表中找到：

`Keying/Prompt -> CN Prompt Assistant (DeepSeek/Ollama)`

---

## 快速开始：怎么接线

> ⚠️ 这个节点 **不会替代** `CLIPTextEncode`（或 Lumina 对应的 Text Encode）。
> 它只负责把中文变成英文 prompt 文本；文本仍需 Encode 才能进入采样器。

### A) 通用 SD / SDXL 工作流（典型接法）

1. `CN Prompt Assistant` 输出：
   - `positive`（STRING）
   - `negative`（STRING）
2. 分别连接到：
   - `CLIPTextEncode (positive)` 的 `text`
   - `CLIPTextEncode (negative)` 的 `text`
3. 再把两个 `CLIPTextEncode` 的输出接到采样器（KSampler）的：
   - `positive` conditioning
   - `negative` conditioning

### B) Lumina / Neta Lumina 工作流

- 如果你的工作流中有 **Lumina 专用 Text Encode** 节点：用法同上，把 `positive/negative` 接到对应的 encode 节点即可。
- 如果你的工作流使用了 **集成式节点（内部已 encode）**：把 `positive/negative` 直接接到它的 prompt 输入口（如果输入类型是 STRING）。

---

## 节点参数说明

### 输入

- `cn_text`：中文创意文本（可很短）
- `backend`：
  - `deepseek_api`：走 DeepSeek
  - `ollama_local`：走本地 Ollama
- `profile`：
  - `lumina`：带 Lumina 固定前缀
  - `universal`：不加前缀，适配 SD/SDXL 等
- `neg_level`：
  - `basic`：更干净
  - `strong`：更稳（更强压制畸形/水印等）
- `temperature`：建议 `0.1 ~ 0.3`（更稳定、更少跑偏）
- `max_tokens`：建议 `700 ~ 1200`（避免 JSON 被截断）
- `deepseek_model`：默认 `deepseek-chat`
- `deepseek_api_key`：可留空（默认读环境变量 `DEEPSEEK_API_KEY`）
- `ollama_host`：默认 `http://localhost:11434`
- `ollama_model`：例如 `qwen2.5:7b-instruct` / `llama3` / `gemma` 等

### 输出

- `positive`：英文正向 prompt（单行）
- `negative`：英文负向 prompt（单行）
- `slots_json`：结构化槽位（JSON 字符串）

---

## DeepSeek 模式配置

### 方式 1：环境变量（推荐）

设置环境变量：

```
export DEEPSEEK_API_KEY="你的key"
```

节点里 `deepseek_api_key` 留空即可。

### 方式 2：节点参数

直接在节点里填 `deepseek_api_key`。

> 安全提示：不要把包含 key 的工作流 JSON 分享给别人。

---

## Ollama 模式配置（本地）

1. 安装并启动 Ollama
2. 拉取一个指令模型（示例）：
   - `qwen2.5:7b-instruct`
3. 节点中填写：
   - `backend = ollama_local`
   - `ollama_host = http://localhost:11434`
   - `ollama_model = qwen2.5:7b-instruct`

> 推荐：temperature 设低一点（0.2），更容易稳定输出 JSON。

---

## Profiles（模板）说明

Profiles 用于控制“提示词前缀/质量词”等渲染差异。

路径：

`profiles/lumina.json`  
`profiles/universal.json`

### lumina.json（示例）

- 会给 positive 加：  
  `You are an assistant designed to generate anime images based on textual prompts. <Prompt Start>`
- 会给 negative 加：  
  `You are an assistant designed to generate low-quality images based on textual prompts <Prompt Start>`

### universal.json（示例）

- `pos_prefix` 和 `neg_prefix` 为空（更适配 SD/SDXL）
- `quality_tail` 默认 `best quality`

你也可以新增自己的 profile，例如：

`profiles/sdxl.json`  
`profiles/your_model.json`

并在节点代码里把 `profile` 下拉选项加入即可（或做成自动扫描 profiles 目录的方式）。

---

## 使用示例

### 输入（中文）

> 黑发少女，樱花树下，温柔微笑，近景，柔光，日系现代动漫

### 输出（示例）

- `positive`（英文、单行、结构化顺序）
- `negative`（英文、单行、basic/strong 负向词库）
- `slots_json`（结构化分段，便于你看它到底补全了什么）

> 具体输出会随 profile / 模型 / 后端变化，但始终保证：可直接接入 encode 节点。

---

## 常见问题（Troubleshooting）

### 1) 输出不是 JSON / 节点报 “not valid JSON”
- 建议把 `temperature` 调低（0.1~0.2）
- `max_tokens` 调高一点（避免截断）
- Ollama 模式下确保启用了 `format: "json"`（本节点已默认启用）

### 2) 画面不稳定 / 风格漂移
- 选择合适的 `profile`
  - Lumina 系列用 `lumina`
  - SD/SDXL 用 `universal`
- `neg_level` 设为 `strong`，减少畸形与水印
- 让用户输入更“具体”（人物外观、镜头、光源、场景关系）

### 3) 接线后 sampler 没反应 / conditioning 空
- 确认你把 `positive/negative` **先接到 Text Encode** 再进 sampler
- 采样器输入如果是 `CONDITIONING` 类型，就一定要 encode

---

## Roadmap（可扩展方向）

- Profile 自动扫描（新增 profile 无需改代码）
- 负向词库 profile 化（每个 profile 独立 basic/strong）
- UI 表单化：让用户填“人物/服装/镜头/光影/场景”，自动组合中文描述
- 增加更多 API 后端（当前 API 仅支持 DeepSeek）

---

## License

按你的项目需求填写（MIT / Apache-2.0 / 私有等）。
