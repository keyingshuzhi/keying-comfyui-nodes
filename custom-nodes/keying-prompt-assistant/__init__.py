# -*- coding = utf-8 -*-
# @Time: 2026/1/17 下午4:19
# @Author: 柯影数智
# @File: __init__.py
# @Email: 1090461393@qq.com
# @SoftWare: PyCharm

from .cn_prompt_assistant import CNPromptAssistantDeepSeek, CNPromptAssistantOllama

NODE_CLASS_MAPPINGS = {
    "CNPromptAssistantDeepSeek": CNPromptAssistantDeepSeek,
    "CNPromptAssistantOllama": CNPromptAssistantOllama,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CNPromptAssistantDeepSeek": "CN Prompt Assistant (DeepSeek API)",
    "CNPromptAssistantOllama": "CN Prompt Assistant (Ollama Local)",
}