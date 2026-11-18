"""Language helpers: length units, budgets and script conversion.

English is budgeted in words. Mandarin (``zh``) is budgeted in characters, because Chinese has no
spaces and a describer counts 字 per second, not words. Narration text for ``zh`` is kept in
Traditional Chinese (Taiwan usage) everywhere a person reads it (script, WebVTT, review page);
it is converted to Simplified only on the way into the TTS front end, whose Mandarin G2P expects
Simplified characters.
"""
import math
import re

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
LATIN_WORD = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)?")

_cc = {}


def _converter(cfg: str):
    if cfg not in _cc:
        import opencc  # opencc-python-reimplemented
        _cc[cfg] = opencc.OpenCC(cfg)
    return _cc[cfg]


def units(text: str, lang: str = "en") -> int:
    """Length of a line in the unit its budget uses: words (en) or characters (zh).
    In zh, each Han character counts one and each Latin word or number counts one."""
    if lang == "zh":
        return len(CJK.findall(text)) + len(LATIN_WORD.findall(text))
    return len(text.split())


def budget(avail: float, s) -> int:
    """Hard length limit for a silence of `avail` seconds."""
    if s.lang == "zh":
        return max(4, min(40, math.floor(avail * s.chars_per_sec)))
    return max(3, min(18, math.floor(avail * s.words_per_sec)))


def shorten_target(text: str, avail: float, spoken: float, lang: str = "en") -> int:
    """Length to ask for when a line overflows: scale by the measured overflow, with 10% margin."""
    n = units(text, lang)
    return max(2 if lang == "en" else 4, math.floor(n * avail / max(spoken, 1e-6) * 0.9))


def has_content(text: str, lang: str = "en") -> bool:
    if lang == "zh":
        return bool(CJK.search(text)) or bool(re.search(r"[A-Za-z]{2,}", text))
    return bool(re.search(r"[A-Za-z]{2,}", text))


TW_TERMS = (
    ("黃油", "奶油"),
    ("衛衣", "運動衫"),
    ("藥板", "藥排"),
    ("視頻", "影片"),
    ("屏幕", "螢幕"),
    ("鼠標", "滑鼠"),
)


def to_traditional(text: str) -> str:
    """Normalise model output to Traditional Chinese with Taiwan phrasing."""
    out = _converter("s2twp").convert(text)
    for cn, tw in TW_TERMS:
        if cn in out:
            out = out.replace(cn, tw)
    return out


_ZHU_WORDS = re.compile(
    r"(著名|著作|顯著|显著|執著|执著|名著|原著|專著|专著|土著|昭著|卓著|編著|编著|合著|譯著|译著|新著|巨著|論著|论著|著稱|著称|著述|著錄|著录)"
)


def for_tts(text: str, lang: str = "en", simplified: bool = True) -> str:
    """Text as the TTS front end should see it.
    Simplified G2P front ends (Kokoro) get t2s + aspectual 著->着; native zh-TW front ends keep Traditional."""
    if lang == "zh":
        if simplified:
            text = _converter("t2s").convert(text)
            if "著" in text:
                kept = {}

                def _hold(m):
                    k = f"\ue000{len(kept)}\ue001"
                    kept[k] = m.group(0)
                    return k

                text = _ZHU_WORDS.sub(_hold, text).replace("著", "着")
                for k, v in kept.items():
                    text = text.replace(k, v)
        # read the full-width quote marks as a short pause rather than skipping them
        text = text.replace("「", "，").replace("」", "，").replace("：", "，")
        text = re.sub(r"，{2,}", "，", text)
        text = re.sub(r"，([。！？；])", r"\1", text)
        return text.strip("，")
    return text
