# -*- coding = utf-8 -*-
# @Time: 2026/1/17
# @Author: 柯影数智
# @File: cn_prompt_assistant.py

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

import requests

# ==========================================================
# Profiles auto-scan
# ==========================================================

_PROFILES_DIR = Path(__file__).parent / "profiles"

def _scan_profiles() -> List[str]:
    if not _PROFILES_DIR.exists():
        return ["lumina", "universal"]
    names = []
    for p in _PROFILES_DIR.glob("*.json"):
        if p.name.startswith("_"):
            continue
        names.append(p.stem)
    names = sorted(set(names))
    return names or ["lumina", "universal"]

PROFILE_CHOICES = _scan_profiles()

def _load_profile(name: str) -> Dict[str, Any]:
    base = _PROFILES_DIR / f"{name}.json"
    if base.exists():
        return json.loads(base.read_text(encoding="utf-8"))
    return {
        "pos_prefix": "",
        "neg_prefix": "",
        "quality_tail": "best quality",
        "neg_basic": "",
        "neg_strong": "",
        "must_have_pos": [],
        "banned_pos": [],
        "max_pos_tags": 80,
        "max_pos_chars": 1400,
        "max_section_tags": {},
    }

# ==========================================================
# Utils
# ==========================================================

def _single_line(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ").replace("\r", " ")).strip()

def _split_csv_tags(text: str) -> List[str]:
    if not text:
        return []
    parts = [p.strip() for p in text.split(",")]
    return [p for p in parts if p]

def _dedupe_keep_order(tags: List[str]) -> List[str]:
    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out

def _strip_prefix(prompt: str, prefix: str) -> str:
    if not prompt:
        return ""
    p = prompt.strip()
    pref = (prefix or "").strip()
    if pref and p.startswith(pref):
        return p[len(pref):].strip(" ,")
    return p

# ==========================================================
# Scene-only detection + constraints (NO HUMANS)
# ==========================================================

_HUMAN_TAGS = {
    # danbooru-ish
    "1girl","1boy","2girls","2boys","3girls","3boys",
    "girl","boy","man","woman","people","person","human",
    "portrait","face","looking at viewer",
    "upper body","close-up","close up",  # 常见“自动人像化”触发点
}

_SCENE_FORCE_POS = ["scenery", "no humans"]
_STILL_LIFE_FORCE_POS = ["still life", "no humans"]

_SCENE_NEG_BLOCK = [
    "1girl","1boy","2girls","2boys","3girls","3boys",
    "girl","boy","man","woman","people","person","human",
    "portrait","face"
]

def _is_scene_only(cn_text: str) -> bool:
    t = (cn_text or "").strip()
    if not t:
        return False

    # 明确人物相关（命中则认为不是纯场景）
    human_kw = [
        "人","人物","角色","模特","女孩","男孩","少女","少年","女人","男人",
        "她","他","小姐姐","小哥哥","情侣","合照","肖像","脸"
    ]
    if any(k in t for k in human_kw):
        return False

    # 明确“无人/空镜/静物/风景”等（命中则偏向纯场景）
    scene_kw = [
        "无人","空镜","纯场景","风景","场景","静物","室内","室外","建筑","回廊","走廊","庭院",
        "房间","桌","书","灯","煤油灯","油灯","怀表","日出","日落","雪","松林","山","街景","夜景"
    ]
    return any(k in t for k in scene_kw)

def _is_still_life(cn_text: str) -> bool:
    t = (cn_text or "").strip()
    if not t:
        return False
    still_kw = ["静物","油灯","煤油灯","怀表","书","木桌","茶杯","花瓶","桌面","器物"]
    return any(k in t for k in still_kw)

def _apply_scene_only_constraints(slots: Dict[str, List[str]], is_still: bool) -> Dict[str, List[str]]:
    # 1) character 清空
    slots["character"] = []

    # 2) 从所有段剔除人物相关 tag
    for k in list(slots.keys()):
        slots[k] = [t for t in slots[k] if t not in _HUMAN_TAGS]

    # 3) scene 段强制插入 scenery/no humans 或 still life/no humans
    force = _STILL_LIFE_FORCE_POS if is_still else _SCENE_FORCE_POS
    for tag in reversed(force):  # reversed -> 保持 force 的顺序插入到开头
        if tag not in slots["scene"]:
            slots["scene"].insert(0, tag)

    # 4) 纯场景别再给“portrait/close-up/upper body”之类人像构图（上面已剔除）
    # 也可以补一个更合理的景别（可选）：wide shot / landscape
    if not is_still:
        if "wide shot" not in slots["camera"]:
            slots["camera"].insert(0, "wide shot")
    else:
        # 静物偏近景/桌面构图也可以，但避免 portrait/upper body
        if "close-up" not in slots["camera"]:
            slots["camera"].insert(0, "close-up")

    return slots

# ==========================================================
# Conflict removal + length control
# ==========================================================

_CONFLICT_GROUPS = [
    {"1girl", "1boy", "2girls", "2boys", "3girls", "3boys"},
    {"solo", "group"},
    {"long hair", "short hair", "very long hair"},
    {"day", "night", "sunset", "sunrise", "dusk"},
    {"close-up", "close up", "upper body", "full body", "wide shot", "portrait"},
    {"front view", "profile", "side view", "back view"},
]

def _resolve_conflicts(tags: List[str]) -> List[str]:
    tags = list(tags)
    for g in _CONFLICT_GROUPS:
        idx = [i for i, t in enumerate(tags) if t in g]
        if len(idx) <= 1:
            continue
        keep_i = idx[-1]
        tags = [t for i, t in enumerate(tags) if (t not in g) or (i == keep_i)]
    return tags

def _apply_banned(tags: List[str], banned: List[str]) -> List[str]:
    banned_set = set((b or "").strip() for b in (banned or []) if (b or "").strip())
    if not banned_set:
        return tags
    return [t for t in tags if t not in banned_set]

def _apply_must_have(tags: List[str], must_have: List[str]) -> List[str]:
    tags = list(tags)
    for t in (must_have or []):
        tt = (t or "").strip()
        if tt and tt not in tags:
            tags.append(tt)
    return tags

def _clip_by_limits(tags: List[str], max_tags: int, max_chars: int, prefix: str = "") -> List[str]:
    if max_tags and len(tags) > max_tags:
        tags = tags[:max_tags]

    if max_chars:
        pref = (prefix or "").strip()
        base = (pref + " " if pref else "")
        while tags and len((base + ", ".join(tags)).strip()) > max_chars:
            tags.pop()

    return tags

def _section_limit(slots: Dict[str, Any], max_section_tags: Dict[str, int]) -> Dict[str, Any]:
    if not max_section_tags:
        return slots
    out = {}
    for k, v in slots.items():
        vv = v
        if isinstance(vv, str):
            vv = [vv]
        if isinstance(vv, list):
            vv = [x.strip() for x in vv if isinstance(x, str) and x.strip()]
            lim = max_section_tags.get(k)
            if lim and len(vv) > int(lim):
                vv = vv[: int(lim)]
        out[k] = vv
    return out

# ==========================================================
# Pydantic schema for structured output
# ==========================================================

try:
    from pydantic import BaseModel
except Exception as e:
    raise ImportError("Missing dependency: pydantic. Please run: pip install pydantic") from e

class Slots(BaseModel):
    character: List[str] = []
    style: List[str] = []
    appearance: List[str] = []
    clothing: List[str] = []
    expression_action: List[str] = []
    camera: List[str] = []
    lighting_fx: List[str] = []
    scene: List[str] = []
    quality: List[str] = []

class PromptResult(BaseModel):
    slots: Slots
    positive: str
    negative: str

# ==========================================================
# Prompt building (optimized + scene-only support)
# ==========================================================

def _profile_neg(profile: Dict[str, Any], neg_level: str) -> str:
    s = profile.get("neg_strong") if neg_level == "strong" else profile.get("neg_basic")
    s = _single_line(s or "")
    if s:
        return s

    basic = "blurry, worst quality, low quality, deformed hands, bad anatomy, extra limbs, poorly drawn face, mutated, extra eyes, bad proportions"
    strong = basic + ", jpeg artifacts, signature, watermark, username, error, malformed limbs, fused fingers, too many fingers, long neck, cross-eyed, cropped"
    return strong if neg_level == "strong" else basic

def _build_system_prompt(profile: Dict[str, Any], neg_level: str) -> str:
    pos_prefix = (profile.get("pos_prefix") or "").strip()
    neg_prefix = (profile.get("neg_prefix") or "").strip()
    neg_base = _profile_neg(profile, neg_level)

    must_have = profile.get("must_have_pos") or []
    banned = profile.get("banned_pos") or []
    max_pos_tags = int(profile.get("max_pos_tags") or 0) if profile.get("max_pos_tags") else 0
    max_pos_chars = int(profile.get("max_pos_chars") or 0) if profile.get("max_pos_chars") else 0
    max_section_tags = profile.get("max_section_tags") or {}

    schema_example = {
        "slots": {
            "character": ["1girl", "solo"],
            "style": ["modern anime style"],
            "appearance": ["black hair", "red eyes", "bangs"],
            "clothing": ["school uniform", "choker"],
            "expression_action": ["gentle smile", "looking at viewer"],
            "camera": ["close-up", "upper body"],
            "lighting_fx": ["soft lighting", "depth of field"],
            "scene": ["cherry blossoms background"],
            "quality": ["best quality"]
        },
        "positive": (pos_prefix + " 1girl, solo, modern anime style, ... , best quality").strip(),
        "negative": (neg_prefix + " " + neg_base).strip(),
    }

    return (
        "You are a prompt compiler. Output MUST be strict json. Output ONLY a JSON object.\n"
        "Return keys: slots, positive, negative.\n"
        "All tags/phrases must be English only.\n"
        "\n"
        "Goal: Convert Chinese (or mixed-language) idea into stable anime-image prompts.\n"
        "Strategy: tags-first. Use concise danbooru-like tags/short phrases. Do NOT write long prose.\n"
        "\n"
        "Slots (9 sections, keep order):\n"
        "1) character (count/gender/solo)\n"
        "2) style\n"
        "3) appearance\n"
        "4) clothing\n"
        "5) expression_action\n"
        "6) camera\n"
        "7) lighting_fx\n"
        "8) scene\n"
        "9) quality\n"
        "\n"
        "Hard requirements:\n"
        "- If the idea is scenery/still life (no people), DO NOT add any character/person tags.\n"
        "  Set slots.character to an empty list and add tags like 'scenery, no humans' (or 'still life, no humans').\n"
        "- If the user DOES describe a person/character, then fill character tags normally.\n"
        "- Always include camera range AND at least one lighting term.\n"
        "- Always include a scene/background term unless user explicitly wants clean background.\n"
        "- Avoid contradictions and duplicates.\n"
        f"- Respect must_have_pos (append if missing): {must_have}\n"
        f"- Avoid banned_pos: {banned}\n"
        f"- Keep output compact (max tags≈{max_pos_tags}, max chars≈{max_pos_chars}).\n"
        f"- Per-section tag limits: {max_section_tags}\n"
        "\n"
        f"positive MUST start with: {pos_prefix}\n"
        f"negative MUST start with: {neg_prefix}\n"
        f"Negative base words (must include): {neg_base}\n"
        "\n"
        "Output rules:\n"
        "- positive and negative must be single-line strings.\n"
        "- positive should be primarily tags joined by commas.\n"
        "- negative should include the base negative words plus any extra relevant negatives.\n"
        "\n"
        "Example JSON:\n"
        + json.dumps(schema_example, ensure_ascii=False)
    )

def _make_user_prompt(cn_text: str) -> str:
    return (
        "Convert the following idea into the required JSON.\n"
        "Idea:\n"
        f"{cn_text}"
    )

# ==========================================================
# Calls
# ==========================================================

def _call_deepseek(api_key: str, model: str, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

def _call_ollama_sdk_only(host: str, model: str, system_prompt: str, user_prompt: str) -> str:
    from ollama import Client  # pip install ollama
    client = Client(host=host.rstrip("/"))
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        format=PromptResult.model_json_schema(),
        options={"temperature": 0},
    )
    content = getattr(getattr(resp, "message", None), "content", None)
    if not content:
        raise ValueError("Ollama SDK returned empty content.")
    _ = PromptResult.model_validate_json(content)
    return content

# ==========================================================
# Parse + enforce (conflicts + limits + profile rules + scene-only)
# ==========================================================

def _parse_json(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            raise ValueError(f"Model output is not valid JSON. Raw:\n{raw[:800]}")
        return json.loads(m.group(0))

def _slots_to_sections(obj: Dict[str, Any]) -> Dict[str, List[str]]:
    slots = obj.get("slots", {}) or {}
    if not isinstance(slots, dict):
        slots = {}
    out: Dict[str, List[str]] = {}
    for k in ["character","style","appearance","clothing","expression_action","camera","lighting_fx","scene","quality"]:
        v = slots.get(k, [])
        if isinstance(v, str):
            v = [v]
        if isinstance(v, list):
            v = [x.strip() for x in v if isinstance(x, str) and x.strip()]
        else:
            v = []
        out[k] = v
    return out

def _render_positive(profile: Dict[str, Any], slots: Dict[str, List[str]]) -> str:
    slots = _section_limit(slots, profile.get("max_section_tags") or {})

    order = ["character","style","appearance","clothing","expression_action","camera","lighting_fx","scene","quality"]
    tags: List[str] = []
    for k in order:
        tags.extend(slots.get(k, []) or [])

    tags = _dedupe_keep_order(tags)
    tags = _apply_banned(tags, profile.get("banned_pos") or [])
    tags = _resolve_conflicts(tags)
    tags = _apply_must_have(tags, profile.get("must_have_pos") or [])

    qt = (profile.get("quality_tail") or "").strip()
    if qt and qt not in tags:
        tags.append(qt)

    prefix = (profile.get("pos_prefix") or "").strip()
    tags = _clip_by_limits(
        tags,
        max_tags=int(profile.get("max_pos_tags") or 0) if profile.get("max_pos_tags") else 0,
        max_chars=int(profile.get("max_pos_chars") or 0) if profile.get("max_pos_chars") else 0,
        prefix=prefix
    )

    s = (prefix + " " if prefix else "") + ", ".join(tags)
    return _single_line(s)

def _merge_negative(profile: Dict[str, Any], neg_level: str, model_negative: str, scene_only: bool) -> str:
    neg_prefix = (profile.get("neg_prefix") or "").strip()

    base = _profile_neg(profile, neg_level)
    base_tags = _split_csv_tags(base)

    model_neg_core = _strip_prefix(model_negative or "", neg_prefix)
    model_tags = _split_csv_tags(model_neg_core)

    extra = _SCENE_NEG_BLOCK if scene_only else []
    all_tags = _dedupe_keep_order(base_tags + model_tags + extra)

    s = (neg_prefix + " " if neg_prefix else "") + ", ".join(all_tags)
    return _single_line(s)

def _finalize(profile: Dict[str, Any], neg_level: str, obj: Dict[str, Any], cn_text: str) -> Tuple[str, str]:
    scene_only = _is_scene_only(cn_text)
    still_life = scene_only and _is_still_life(cn_text)

    slots = _slots_to_sections(obj)
    if scene_only:
        slots = _apply_scene_only_constraints(slots, is_still=still_life)

    pos = _render_positive(profile, slots)

    model_neg = (obj.get("negative") or "").strip()
    neg = _merge_negative(profile, neg_level, model_neg, scene_only=scene_only)

    return pos, neg

# ==========================================================
# Nodes (two nodes)
# ==========================================================

class CNPromptAssistantDeepSeek:
    @classmethod
    def INPUT_TYPES(cls):
        default_profile = PROFILE_CHOICES[0] if PROFILE_CHOICES else "lumina"
        return {
            "required": {
                "cn_text": ("STRING", {"multiline": True, "default": "冬日雪后日出，东亚风格木质回廊，纸灯笼微亮，远处雪山与松林，广角远景，宁静氛围，柔和晨光。"}),
                "profile": (PROFILE_CHOICES, {"default": default_profile}),
                "neg_level": (["basic", "strong"], {"default": "strong"}),
                "temperature": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.5, "step": 0.05}),
                "max_tokens": ("INT", {"default": 900, "min": 256, "max": 4096, "step": 64}),
                "deepseek_model": ("STRING", {"default": "deepseek-chat"}),
                "deepseek_api_key": ("STRING", {"default": ""}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "run"
    CATEGORY = "Keying/Prompt"

    def run(
        self,
        cn_text: str,
        profile: str,
        neg_level: str,
        temperature: float,
        max_tokens: int,
        deepseek_model: str,
        deepseek_api_key: str,
    ):
        prof = _load_profile(profile)
        system_prompt = _build_system_prompt(prof, neg_level)
        user_prompt = _make_user_prompt(cn_text)

        api_key = deepseek_api_key.strip() or os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise ValueError("DeepSeek API key missing. Set DEEPSEEK_API_KEY env or fill deepseek_api_key.")

        raw = _call_deepseek(api_key, deepseek_model, system_prompt, user_prompt, max_tokens, temperature)
        obj = _parse_json(raw)
        pos, neg = _finalize(prof, neg_level, obj, cn_text)
        return (pos, neg)


class CNPromptAssistantOllama:
    @classmethod
    def INPUT_TYPES(cls):
        default_profile = PROFILE_CHOICES[0] if PROFILE_CHOICES else "lumina"
        return {
            "required": {
                "cn_text": ("STRING", {"multiline": True, "default": "昏暗房间里一盏复古煤油灯，木桌上放着旧书和金属怀表，光线集中在桌面，背景深黑，明暗对比，氛围感。"}),
                "profile": (PROFILE_CHOICES, {"default": default_profile}),
                "neg_level": (["basic", "strong"], {"default": "strong"}),
                "ollama_host": ("STRING", {"default": "http://127.0.0.1:11434"}),
                "ollama_model": ("STRING", {"default": "qwen2.5:7b-instruct"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "run"
    CATEGORY = "Keying/Prompt"

    def run(
        self,
        cn_text: str,
        profile: str,
        neg_level: str,
        ollama_host: str,
        ollama_model: str,
    ):
        prof = _load_profile(profile)
        system_prompt = _build_system_prompt(prof, neg_level)
        user_prompt = _make_user_prompt(cn_text)

        raw = _call_ollama_sdk_only(ollama_host, ollama_model, system_prompt, user_prompt)
        obj = _parse_json(raw)
        pos, neg = _finalize(prof, neg_level, obj, cn_text)
        return (pos, neg)