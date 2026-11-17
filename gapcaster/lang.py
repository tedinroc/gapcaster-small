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


def to_traditional(text: str) -> str:
    """Normalise model output to Traditional Chinese with Taiwan phrasing (no-op for text already Traditional)."""
    return _converter("s2twp").convert(text)


def for_tts(text: str, lang: str = "en") -> str:
    """Text as the TTS front end should see it."""
    if lang == "zh":
        text = _converter("t2s").convert(text)
        # read the full-width quote marks as a short pause rather than skipping them
        text = text.replace("「", "，").replace("」", "，").replace("：", "，")
        return re.sub(r"，{2,}", "，", text).strip("，")
    return text
