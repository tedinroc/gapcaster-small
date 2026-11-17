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
    assert not g.is_repeat("狙擊手舉起步槍瞄準", ["老人跪在地上喘氣"], lang="zh")


def test_english_rules_unchanged():
    assert g.check("We see a man running.", 6)[0] == ["camera-language", "first-person"]
