"""Dialogue map from word-level ASR timestamps plus a VAD, and the silences between dialogue."""
import re


_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
HALLUCINATIONS = {
    "you", "thank you", "thanks for watching", "bye",
    "謝謝觀看", "谢谢观看", "感謝收看", "感谢收看", "請訂閱", "请订阅",
    "字幕由amaraorg社群提供", "",
}
# Known Whisper BGM watermark artefacts on Chinese/Mandarin music intros
BGM_WATERMARK = re.compile(
    r"^\s*(?:字幕(?:志願|志愿|愿|提供|組|组|製作|制作)?(?:者|員|员)?|字愿者)\s*[:：\-]?\s*(?:李宗盛)?|"
    r"(?:優優|优优)(?:獨播劇場|独播剧场)|明鏡與點點|明镜与点点|amara\.?org",
    re.I,
)


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9'\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff ]", "", t.lower()).strip()


def filter_segment_words(seg_words, seg_text: str):
    """Drop Whisper BGM watermark prefixes, stretched silence hallucinations, and music loops."""
    compact = re.sub(r"\s+", "", _norm(seg_text))
    if not compact or re.fullmatch(r"(.)\1{4,}", compact):
        return []
    raw = list(seg_words or [])
    m = BGM_WATERMARK.search(seg_text or "")
    if m and m.start() == 0:
        remainder = re.sub(r"\s+", "", _norm((seg_text or "")[m.end():]))
        if not remainder:
            return []
        kept_tail, acc = [], ""
        for w in reversed(raw):
            kept_tail.append(w)
            acc = re.sub(r"\s+", "", _norm(w.get("word", ""))) + acc
            if len(acc) >= len(remainder):
                break
        raw = list(reversed(kept_tail))
    if len(raw) == 1:
        dur0 = float(raw[0]["end"]) - float(raw[0]["start"])
        p0 = float(raw[0].get("probability", 1.0))
        if dur0 > 4.0 or (dur0 > 2.0 and p0 < 0.5):   # single-word Whisper phantom stretched across silence
            return []
    out = []
    for w in raw:
        s0, e0 = float(w["start"]), float(w["end"])
        if e0 - s0 > 1.8:     # words after music/silence often absorb preceding silence; keep last 1.5 s
            s0 = e0 - 1.5
        if e0 - s0 > 0 and _norm(w.get("word", "")):
            out.append({"w": w["word"].strip(), "start": s0, "end": e0,
                        "p": float(w.get("probability", 1.0))})
    return out


def transcribe(audio_path, model: str, lang: str | None = "en"):
    """Word timestamps from Whisper. Short, quiet exclamations are kept on purpose:
    narrating over a shout is worse than leaving a silence empty. Only known
    Whisper artefacts are dropped (stock phrases over music, repetition loops)."""
    import mlx_whisper
    res = mlx_whisper.transcribe(str(audio_path), path_or_hf_repo=model, word_timestamps=True,
                                 language=lang, condition_on_previous_text=False)
    segs = res.get("segments", [])
    words = []
    for i, seg in enumerate(segs):
        t, lp = _norm(seg.get("text", "")), seg.get("avg_logprob", 0)
        if seg.get("no_speech_prob", 0) > 0.6 and lp < -0.8:
            continue
        if t in HALLUCINATIONS and lp < -0.5:
            continue
        neighbours = [_norm(x.get("text", "")) for x in segs[max(0, i - 2): i + 3]]
        if lp < -1.0 and neighbours.count(t) >= 3:      # "I have. I have. I have." over music
            continue
        words.extend(filter_segment_words(seg.get("words", []), seg.get("text", "")))
    words.sort(key=lambda w: w["start"])
    return words, res.get("text", "")


def transcribe_openvino(audio_path, model: str, device: str = "CPU", lang: str | None = "en"):
    """Same output as transcribe(), from OpenVINO GenAI's WhisperPipeline (CPU here, Arc GPU on a B70)."""
    import os

    import openvino_genai as og
    import soundfile as sf
    path = model if os.path.isdir(model) else __import__("huggingface_hub").snapshot_download(model)
    pipe = og.WhisperPipeline(path, device, word_timestamps=True)
    cfg = pipe.get_generation_config()
    if lang:
        cfg.language = f"<|{lang}|>"
    cfg.task, cfg.return_timestamps = "transcribe", True
    a, _ = sf.read(str(audio_path), dtype="float32")
    res = pipe.generate(a.tolist(), cfg)
    words = []
    for w in res.words or []:
        s0, e0 = float(w.start_ts), float(w.end_ts)
        if e0 - s0 > 1.5:            # a first word after long silence absorbs the silence; keep its last 1.5 s at most
            s0 = e0 - 1.5
        if e0 > s0 and _norm(w.word):        # keep every real word; only pure punctuation is dropped
            words.append({"w": w.word.strip(), "start": s0, "end": e0, "p": 1.0})
    return words, " ".join(res.texts)


def vad_speech(audio_path, threshold: float = 0.5):
    """Second, independent speech detector (Silero VAD, MIT). Empty if not installed."""
    try:
        import soundfile as sf
        import torch
        from silero_vad import get_speech_timestamps, load_silero_vad
    except ImportError:
        return []
    a, sr = sf.read(str(audio_path), dtype="float32")
    ts = get_speech_timestamps(torch.from_numpy(a), load_silero_vad(), sampling_rate=sr, return_seconds=True,
                               threshold=threshold, min_speech_duration_ms=150, min_silence_duration_ms=300,
                               speech_pad_ms=80)
    return [{"start": float(x["start"]), "end": float(x["end"])} for x in ts]


def merge(spans_a, spans_b, merge_pause: float):
    """Union of two span lists: a moment counts as dialogue if either detector heard speech."""
    out = []
    for sp in sorted(spans_a + spans_b, key=lambda x: x["start"]):
        if out and sp["start"] - out[-1]["end"] < merge_pause:
            out[-1]["end"] = max(out[-1]["end"], sp["end"])
            if sp.get("text"):
                out[-1]["text"] = (out[-1].get("text", "") + " " + sp["text"]).strip()
        else:
            out.append({"start": sp["start"], "end": sp["end"], "text": sp.get("text", "")})
    return out


def speech_spans(words, merge_pause: float):
    spans = []
    for w in words:
        if spans and w["start"] - spans[-1]["end"] < merge_pause:
            spans[-1]["end"] = max(spans[-1]["end"], w["end"])
            sep = "" if (_CJK.search(spans[-1]["text"][-1:]) and _CJK.search(w["w"][:1])) else " "
            spans[-1]["text"] += sep + w["w"]
        else:
            spans.append({"start": w["start"], "end": w["end"], "text": w["w"]})
    return spans


def gaps(spans, total: float, lead: float, tail: float, min_slot: float):
    """Usable silences: [end of dialogue + lead, start of next dialogue - tail]."""
    out, cursor = [], 0.0
    edges = [(s["start"], s["end"]) for s in spans] + [(total, total)]
    for start, end in edges:
        a = cursor + (lead if cursor > 0 else 0.3)
        b = start - (tail if start < total else 0.2)
        if b - a >= min_slot:
            out.append({"start": round(a, 3), "end": round(b, 3)})
        cursor = max(cursor, end)
    return out


def overlap(a0, a1, b0, b1) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def load_srt(path):
    import re
    text = open(path, encoding="utf-8-sig").read()
    out = []
    for m in re.finditer(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", text):
        g = [int(x) for x in m.groups()]
        s = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        out.append({"start": s, "end": e})
    return out
