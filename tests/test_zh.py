"""Mandarin (zh) helpers and style rules; no models needed."""
from types import SimpleNamespace

from gapcaster import lang as L
from gapcaster import styleguard as g


def test_units_zh_counts_characters_and_latin_words():
    assert L.units("老人跪在地上。", "zh") == 6
    assert L.units("字幕：TEARS OF STEEL", "zh") == 5
    assert L.units("An old man kneels.", "en") == 4


def test_budget_by_language():
    zh = SimpleNamespace(lang="zh", chars_per_sec=4.0, words_per_sec=2.6)
    en = SimpleNamespace(lang="en", chars_per_sec=4.0, words_per_sec=2.6)
    assert L.budget(2.0, zh) == 8
    assert L.budget(0.5, zh) == 4          # floor
    assert L.budget(30, zh) == 40          # ceiling
    assert L.budget(2.0, en) == 5


def test_traditional_and_tts_conversion():
    assert L.to_traditional("一位老人跪在地上按住胸口喘气") == "一位老人跪在地上按住胸口喘氣"
    assert L.to_traditional("標籤寫著白城堡黃油餅乾") == "標籤寫著白城堡奶油餅乾"
    assert L.for_tts("字幕：四十年後。", "zh") == "字幕，四十年后。"
    assert L.for_tts("Forty years later.", "en") == "Forty years later."


def test_zh_hard_rules():
    hard, soft = g.check("我們看到一位老人似乎很傷心。", 10, lang="zh")
    assert set(hard) == {"camera-language", "speculation", "first-person"}
    assert "inner-state" in soft


def test_zh_onscreen_text_is_exempt():
    assert g.check("字幕：我們的未來。老人跪在地上。", 12, lang="zh") == ([], [])
    assert g.check("招牌寫著「我們都在」。", 12, lang="zh") == ([], [])


def test_zh_repeat_detection_uses_character_bigrams():
    assert g.is_repeat("老人跪在地上喘氣", ["老人跪在地上喘氣不止"], lang="zh")
    assert g.is_repeat("鳳蓮舉右手比出和平手勢，嘴角微揚。", ["鳳蓮比出和平手勢，微笑。"], lang="zh")
    assert "speech-tag" in g.check("鳳蓮笑著說。", 10, lang="zh")[0]
    assert not g.is_repeat("狙擊手舉起步槍瞄準", ["老人跪在地上喘氣"], lang="zh")


def test_english_rules_unchanged():
    assert g.check("We see a man running.", 6)[0] == ["camera-language", "first-person"]


def test_gapmap_norm_and_spans_preserve_chinese_dialogue():
    from gapcaster import gapmap
    assert gapmap._norm("我們今天來到台北！") == "我們今天來到台北"
    assert gapmap._norm("...") == ""
    assert gapmap._norm("Thank you!") == "thank you"
    words_zh = [
        {"w": "這", "start": 0.0, "end": 0.2},
        {"w": "裡", "start": 0.2, "end": 0.4},
        {"w": "是", "start": 0.4, "end": 0.6},
        {"w": "台", "start": 2.0, "end": 2.2},
        {"w": "灣", "start": 2.2, "end": 2.5},
    ]
    spans = gapmap.speech_spans(words_zh, merge_pause=0.6)
    assert [(s["text"], s["start"], s["end"]) for s in spans] == [
        ("這裡是", 0.0, 0.6),
        ("台灣", 2.0, 2.5),
    ]
    words_en = [{"w": "See", "start": 0.0, "end": 0.3}, {"w": "you", "start": 0.4, "end": 0.7}]
    assert gapmap.speech_spans(words_en, merge_pause=0.6)[0]["text"] == "See you"


def test_bgm_watermark_and_open_caption_filters():
    from gapcaster import gapmap
    from gapcaster.pipeline import is_spoken_subtitle

    # Pure music loop is dropped
    assert gapmap.filter_segment_words(
        [{"word": "一", "start": 85.0, "end": 88.0}], "一一一一一一一一"
    ) == []
    # BGM watermark prefix is stripped (even with UTF-8 split tokens) while real speech after it is kept and clamped
    seg_words = [
        {"word": "字幕", "start": 6.0, "end": 10.0},
        {"word": "志愿", "start": 10.0, "end": 12.0},
        {"word": "者", "start": 12.0, "end": 13.0},
        {"word": "\ufffd\ufffd", "start": 13.0, "end": 14.0},
        {"word": "宗", "start": 14.0, "end": 15.0},
        {"word": "盛", "start": 15.0, "end": 18.0},
        {"word": "善", "start": 18.0, "end": 22.0},
        {"word": "良", "start": 22.0, "end": 22.4},
    ]
    kept = gapmap.filter_segment_words(seg_words, "字幕志愿者 李宗盛 善良")
    assert [w["w"] for w in kept] == ["善", "良"]
    assert kept[0]["start"] == 20.5  # clamped to last 1.5s of stretched lead-in

    # Single-word stretched Whisper phantom over silence is dropped
    assert gapmap.filter_segment_words(
        [{"word": "Practice", "start": 131.9, "end": 139.6, "probability": 0.4}], "Practice"
    ) == []

    # Untranslated lowercase English common nouns in Mandarin AD trigger hard rule; proper names/captions pass
    assert "english-word" in g.check("四盆綠色手指 succulent 植物排在木桌上。", 15, lang="zh")[0]
    assert g.check("字幕：Young。善仁站在門口。", 15, exempt=["Young"], lang="zh") == ([], [])
    assert g.check("封面寫著「我能！」", 10, lang="zh") == ([], [])

    # clean() preserves end-of-sentence closing quotes while stripping full-line wrapper quotes
    from gapcaster.pipeline import clean
    assert clean("封面寫著「我能！」", "zh") == "封面寫著「我能！」"
    assert clean("「老人跪地。」", "zh") == "老人跪地。"
    assert clean('A sign reads "We are open"', "en") == 'A sign reads "We are open"'

    # Burned-in dialogue subtitle matches spoken ASR (even Simplified ASR vs Traditional caption)
    spans = [{"start": 21.0, "end": 26.0, "text": "善良孝顺负责任很热心"}]
    assert is_spoken_subtitle("負責任 Responsible", spans, 23.0, 25.0, "zh")
    assert not is_spoken_subtitle("關於林善仁 About Mr. Shan-Ren Lin", spans, 23.0, 25.0, "zh")
