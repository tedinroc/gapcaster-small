"""Deterministic style gate for audio description (no model involved).

Hard rules block a line and force a rewrite; soft rules only flag it for the human describer.
Based on common AD practice: describe what is visible, in the present tense, without
interpretation, camera language or guesses.
"""
import re

HARD = {
    "camera-language": r"\b(we see|we hear|we watch|the camera|camera (?:pans|zooms|cuts)|shot of|the scene shows|on screen we)\b",
    "speculation": r"\b(seems?|seemingly|appears? to|apparently|probably|perhaps|maybe|possibly|it looks like|presumably|likely)\b",
    "first-person": r"\bI\b(?=\s+(?:am|was|have|had|see|saw|think|hear|notice|feel|can|will|would|do|did|know)\b)|\bI['’](?:m|ve|d|ll)\b|\b(?i:we|us|our)\b",
}
SOFT = {
    "inner-state": r"\b(sad|happy|angry|upset|worried|nervous|scared|afraid|excited|confused|annoyed|frustrated|guilty|jealous|in love|exhausted|exhaustion|tired|weary|relieved|determined|hopeful|desperate|bored)\b",
    "evaluative": r"\b(beautiful|ugly|stunning|amazing|terrible|creepy|disgusting|gorgeous)\b",
    "simile": r"\bas if\b",
}


# Mandarin rules (Traditional Chinese; Simplified variants included so model drift is still caught)
HARD_ZH = {
    "camera-language": r"(我們看到|我們聽到|鏡頭|画面中我们|畫面中我們|畫面顯示|镜头)",
    "speculation": r"(似乎|好像|彷彿|仿佛|可能|或許|或许|大概|也許|也许|看起來像|看起来像|應該是|应该是)",
    "first-person": r"(我們|我们|我)",
}
SOFT_ZH = {
    "inner-state": r"(傷心|难过|難過|開心|开心|高興|生氣|生气|憤怒|害怕|恐懼|緊張|紧张|擔心|担心|興奮|兴奋|困惑|沮喪|絕望|疲憊|疲惫|無聊|放心|決心)",
    "evaluative": r"(美麗|美丽|漂亮|醜陋|驚人|惊人|可怕|恐怖|噁心|壯觀|壮观|令人)",
    "simile": r"(宛如|如同|好似|像是)",
}


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", t.lower())


def check(line: str, max_words: int | None = None, exempt=(), lang: str = "en"):
    """Return (hard, soft) rule names. `exempt` holds on-screen texts the line may read verbatim:
    they are removed before the rules run, so a caption containing "we" is not first person."""
    if lang == "zh":
        return _check_zh(line, max_words, exempt)
    hard, soft = [], []
    # quoted text is read verbatim, not judged; a single quote inside a word (Celia's) is an apostrophe
    line = re.sub(r"[\"“][^\"”]*[\"”]|(?<![A-Za-z])['‘][^'’]{3,}['’](?![A-Za-z])", "", line)
    for t in exempt or ():
        words = [re.escape(w) for w in _norm(t).split() if w]
        if len(words) >= 2:
            line = re.sub(r"\W+".join(words), " ", line, flags=re.I)
    low = line.lower()
    for k, pat in HARD.items():
        flags = 0 if k == "first-person" else re.I
        if re.search(pat, line if k == "first-person" else low, flags):
            hard.append(k)
    for k, pat in SOFT.items():
        if re.search(pat, low):
            soft.append(k)
    if max_words and len(line.split()) > max_words * 1.6:
        soft.append("long")
    return hard, soft


def _check_zh(line: str, max_units: int | None, exempt=()):
    from .lang import units
    hard, soft = [], []
    # text read verbatim (inside 「」 or after 字幕／標題：) is exempt from the rules
    line = re.sub(r"「[^」]*」|“[^”]*”|\"[^\"]*\"", "", line)
    line = re.sub(r"(字幕|標題|标题|招牌|告示|文字|字卡|頭條|头条)[:：][^。！？]*", "", line)
    for t in exempt or ():
        if t and t in line:
            line = line.replace(t, "")
    for k, pat in HARD_ZH.items():
        if re.search(pat, line):
            hard.append(k)
    for k, pat in SOFT_ZH.items():
        if re.search(pat, line):
            soft.append(k)
    if max_units and units(line, "zh") > max_units * 1.6:
        soft.append("long")
    return hard, soft


STOP_ZH = set("的了著着在是有和與与及一個个這这那他她它們们之也都就而並并把被")

STOP = set("a an the of and or to in on at with from by for his her their its is are as into onto over under up down".split())


def content_words(line: str, lang: str = "en"):
    if lang == "zh" or re.search(r"[\u4e00-\u9fff]", line):
        han = [c for c in re.findall(r"[\u4e00-\u9fff]", line) if c not in STOP_ZH]
        grams = {a + b for a, b in zip(han, han[1:])}
        return grams | {w for w in re.findall(r"[a-z']+", line.lower()) if w not in STOP}
    return {w for w in re.findall(r"[a-z']+", line.lower()) if w not in STOP}


def is_repeat(line: str, recent, threshold: float = 0.5, lang: str = "en") -> bool:
    """True when a draft mostly re-says one of the last lines (Jaccard on content words)."""
    a = content_words(line, lang)
    for prev in recent[-2:]:
        b = content_words(prev, lang)
        if a and b and len(a & b) / len(a | b) >= threshold:
            return True
    return False
