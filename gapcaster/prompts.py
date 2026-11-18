SHOT = """You are helping draft audio description (AD) for blind and low-vision viewers.
Cast sheet (use a name only if the person clearly matches its description):
{cast}
Dialogue heard around this shot: "{ctx}"

The image(s) come from one film shot lasting {dur:.1f} s. Report only what is visible.
Reply with JSON only:
{{"who": "names, or brief visual descriptions of the people visible, or none",
  "where": "the setting",
  "action": "what is happening, present tense",
  "text": "exact words legible on screen (title cards, signs, headlines, labels), quoted verbatim; never describe unreadable text in prose — leave empty if too blurry/small, and exclude bottom dialogue subtitles",
  "key": "the single most important visual fact for a blind viewer",
  "confidence": 0.0 to 1.0}}"""

WRITE = """You write ONE audio description line for a film, for blind and low-vision viewers.
Rules: present tense. Describe only what is visible. If the facts show story text on screen (a title card such as "40 YEARS LATER", a sign, a headline) that has not been read yet, read it first, e.g. "A caption: Forty years later." Ignore sponsor credits and logos. Name feelings only through a visible expression or gesture. No camera language ("we see", "shot of"). Do not repeat what the dialogue already says. Use cast names or cast labels (such as \"the sniper\") when the person matches. Plain, concrete words.
Cast: {cast}
Recent AD lines (do not repeat them): {recent}
Dialogue just before: "{before}"
Dialogue just after: "{after}"
Visible during this window:
{facts}
{text_note}
The window is {avail:.1f} s long. Hard limit: {budget} words.
If nothing new is visible, reply SKIP. Otherwise reply with the line only."""

SHORTEN = """Shorten this audio description line. Spoken, it takes {dur:.1f} s, but the silence is only {avail:.1f} s.
Rewrite it in at most {target} words. Keep the most important visual fact (who and what they do comes first).
Present tense, no interpretation, no camera language. Reply with the line only.
Line: {line}"""

RESTYLE = """Rewrite this audio description line to fix these problems: {problems}.
Describe only what is visible, present tense, no guessing words (seems, appears, maybe), no camera language, no "I/we".
If the problem is "credits": describe the visible image instead of reading production credits, sponsors or logos.
At most {budget} words. Reply with the line only.
Line: {line}"""

VERIFY = """Check an audio description line against the facts a vision model extracted from the same shots.
Facts:
{facts}
Line: "{line}"
Is every concrete claim in the line (people, names, objects, colours, actions, places, text) supported by the facts?
Reply with JSON only: {{"supported": true or false, "unsupported": ["claim", ...]}}"""

READ_TEXT = """Rewrite this audio description line so it first reads the story text visible on screen, for example "A headline: Roboticist creates killer robots." or "A caption: Forty years later."
On-screen text: {text}
Then add the most important visible action if words remain. At most {budget} words. Present tense, no interpretation. Reply with the line only.
Line: {line}"""


# ---- Mandarin (Traditional Chinese, Taiwan) ---------------------------------------------------
# Shot facts stay in English (the SHOT prompt above): the vision model is most reliable there,
# and the facts are an internal record. The narration itself is written in Traditional Chinese.

WRITE_ZH = """你替視障觀眾撰寫一句電影「口述影像」旁白，使用繁體中文（台灣日常用語，例如奶油餅乾、平安符、T恤，不用大陸詞彙如黃油）。
規則：現在式、客觀描述畫面上看得到的事物。如果畫面有尚未唸出的劇情文字（例如「四十年後」字卡、招牌、報紙標題），先唸出來，例如「字幕：四十年後。」；外文字卡一律翻成中文唸，不要直接唸英文。除了畫面上的專有名詞或店名（如 Young）外，所有一般名詞一律翻成中文，絕對不可夾雜英文單字（例如不可寫 succulent，應寫多肉植物）。不要唸片頭贊助、基金會支持、製作名單或商標。情緒只能透過看得到的表情或動作表達。不要用鏡頭語言（「我們看到」「鏡頭」「畫面中」）。不要猜測（「似乎」「好像」「可能」）。不要重複對白已經說過的內容。人物符合角色表時用角色名稱或稱呼（例如「狙擊手」）。用字簡單具體，句子完整並以句號結尾。
角色表：{cast}
最近幾句旁白（不要重複）：{recent}
前一句對白：「{before}」
後一句對白：「{after}」
這段時間畫面上的事實（英文紀錄）：
{facts}
{text_note}
這段空檔長 {avail:.1f} 秒。硬性上限：{budget} 個字（含標點以外的所有中文字）。
如果畫面沒有新東西，只回覆 SKIP。否則只回覆這一句旁白。"""

SHORTEN_ZH = """把這句口述影像旁白縮短。唸出來要 {dur:.1f} 秒，但空檔只有 {avail:.1f} 秒。
改寫成最多 {target} 個中文字，使用純繁體中文（不可夾雜英文普通名詞）。保留最重要的畫面資訊（誰、在做什麼優先）。
必須是主詞與動作完整、自然通順的句子並以句號結尾，絕對不可截斷成半句話（例如不可只寫「獻上一杯」而漏掉受詞）。現在式、不詮釋、不用鏡頭語言。只回覆改寫後的句子。
原句：{line}"""

RESTYLE_ZH = """改寫這句口述影像旁白，修正這些問題：{problems}。
只描述看得到的事物、現在式、不要猜測詞（似乎、好像、可能、或許）、不要鏡頭語言（我們看到、鏡頭）、不要用「我」「我們」。
如果問題是 english-word：把句子裡夾雜的英文普通名詞翻譯成繁體中文（例如多肉植物、木椅、圍裙），不可留英文單字。
如果問題是 speech-tag：不要寫「笑著說」「開口說」，只描述看得到的表情或動作（例如「微笑」「點頭」）。
如果問題是 credits：描述畫面本身，不要唸製作名單、贊助或商標。
最多 {budget} 個中文字，使用繁體中文，完整句子以句號結尾。只回覆改寫後的句子。
原句：{line}"""

VERIFY_ZH = """Check a Traditional Chinese audio description line against the facts a vision model extracted (in English) from the same shots.
Facts:
{facts}
Line: "{line}"
Is every concrete claim in the line (people, names, objects, colours, actions, places, text) supported by the facts? Translation and paraphrase are fine; only flag claims the facts do not support.
Reply with JSON only: {{"supported": true or false, "unsupported": ["claim, quoted in Chinese as written in the line", ...]}}"""

READ_TEXT_ZH = """改寫這句口述影像旁白，讓它先唸出畫面上的劇情文字，例如「標題：機器人學家製造殺人機器人。」或「字幕：四十年後。」。外文字卡請翻成中文唸出。
畫面文字：{text}
如果還有字數，再加上最重要的動作。最多 {budget} 個中文字，繁體中文、現在式、不詮釋。只回覆改寫後的句子。
原句：{line}"""


def get(name: str, lang: str = "en") -> str:
    """Prompt template for a language; falls back to English."""
    if lang == "zh":
        zh = globals().get(name + "_ZH")
        if zh:
            return zh
    return globals()[name]
