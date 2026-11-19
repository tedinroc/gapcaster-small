"""Text-to-speech with real duration measurement.

Four local offline runtimes:
- "qwen3_tts": Qwen3-TTS-12Hz-1.7B-Base-8bit (Apache-2.0) via mlx-audio with bundled Apache-2.0 Taiwanese Mandarin reference voice
- "avspeech": macOS on-device neural AVSpeechSynthesizer (zh-TW fallback, e.g. Siri Shufen / Meijia)
- "mlx": Kokoro-82M (Apache-2.0) via mlx-audio on Apple Silicon (English default)
- "kokoro": Kokoro-82M (Apache-2.0) via PyTorch on CPU or Intel Arc XPU (Stage II)
"""
import atexit
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

QWEN3_TTS_DEFAULT_MODEL = os.environ.get("GAPCASTER_QWEN3_TTS", "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit")
DEFAULT_TW_REF_AUDIO = Path(__file__).parent / "assets" / "tw_ref_female.wav"
DEFAULT_TW_REF_TEXT = "在密码学中，加密是将明文资讯改变为难以读取的密文内容，使之不可读的方法。"


_AVSPEECH_SWIFT = r"""import Foundation
import AVFoundation

let args = CommandLine.arguments
let langArg = args.count > 1 ? args[1] : "zh-TW"
let voiceArg = args.count > 2 ? args[2] : "zh-TW"

_ = AVSpeechSynthesisVoice.speechVoices()
RunLoop.main.run(mode: .default, before: Date(timeIntervalSinceNow: 0.1))

func pickVoice(_ req: String, _ lang: String) -> AVSpeechSynthesisVoice? {
    if req == "zh-TW" || (req == "auto" && lang.hasPrefix("zh")) {
        if let neural = AVSpeechSynthesisVoice(identifier: "com.apple.ttsbundle.gryphon-neural_Shufen_zh-TW_premium") {
            return neural
        }
        let cands = AVSpeechSynthesisVoice.speechVoices().filter { $0.language == "zh-TW" }
            .sorted { $0.quality.rawValue > $1.quality.rawValue }
        if let best = cands.first { return best }
        return AVSpeechSynthesisVoice(language: "zh-TW")
    }
    if req == "en-US" || (req == "auto" && lang.hasPrefix("en")) {
        let cands = AVSpeechSynthesisVoice.speechVoices().filter { $0.language == "en-US" }
            .sorted { $0.quality.rawValue > $1.quality.rawValue }
        if let best = cands.first { return best }
        return AVSpeechSynthesisVoice(language: "en-US")
    }
    if let byId = AVSpeechSynthesisVoice(identifier: req) { return byId }
    if let byName = AVSpeechSynthesisVoice.speechVoices().first(where: { $0.name == req }) { return byName }
    return AVSpeechSynthesisVoice(language: lang)
}

guard let voice = pickVoice(voiceArg, langArg) else {
    fputs("{\"ready\":false,\"error\":\"no voice\"}\n", stdout)
    fflush(stdout)
    exit(1)
}

let readyObj: [String: Any] = ["ready": true, "voice_id": voice.identifier, "quality": voice.quality.rawValue]
let readyData = try! JSONSerialization.data(withJSONObject: readyObj)
FileHandle.standardOutput.write(readyData)
FileHandle.standardOutput.write("\n".data(using: .utf8)!)
fflush(stdout)

class SynthDelegate: NSObject, AVSpeechSynthesizerDelegate {
    var finished = false
    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        finished = true
    }
    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        finished = true
    }
}

let synth = AVSpeechSynthesizer()
let delegate = SynthDelegate()
synth.delegate = delegate
while let line = readLine() {
    guard let data = line.data(using: .utf8),
          let req = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
          let text = req["text"] as? String,
          let outPath = req["out"] as? String else { continue }
    try? FileManager.default.removeItem(atPath: outPath)
    delegate.finished = false
    let utt = AVSpeechUtterance(string: text)
    utt.voice = voice
    utt.rate = AVSpeechUtteranceDefaultSpeechRate
    utt.postUtteranceDelay = 0.05
    var outFile: AVAudioFile? = nil
    let deadline = Date(timeIntervalSinceNow: 30.0)
    synth.write(utt) { buf in
        guard let pcm = buf as? AVAudioPCMBuffer else { return }
        if pcm.frameLength == 0 {
            return
        }
        if outFile == nil {
            outFile = try? AVAudioFile(forWriting: URL(fileURLWithPath: outPath), settings: pcm.format.settings)
        }
        try? outFile?.write(from: pcm)
    }
    while !delegate.finished && Date() < deadline {
        RunLoop.main.run(mode: .default, before: Date(timeIntervalSinceNow: 0.01))
    }
    outFile = nil
    FileHandle.standardOutput.write("{\"ok\":true}\n".data(using: .utf8)!)
    fflush(stdout)
}
"""


def avspeech_available() -> bool:
    return sys.platform == "darwin" and shutil.which("swift") is not None


def qwen3_tts_available() -> bool:
    return importlib.util.find_spec("mlx_audio") is not None and DEFAULT_TW_REF_AUDIO.is_file()


def default_tts_model(backend: str) -> str:
    if backend == "qwen3_tts":
        return QWEN3_TTS_DEFAULT_MODEL
    return "mlx-community/Kokoro-82M-bf16"


def resolve_tts(lang: str = "en", backend: str | None = None, voice: str | None = None) -> tuple[str, str]:
    """Choose TTS runtime and default voice for `lang`."""
    if not backend or backend == "auto":
        if lang == "zh":
            if qwen3_tts_available():
                backend = "qwen3_tts"
            elif avspeech_available():
                backend = "avspeech"
            else:
                backend = "mlx"
        else:
            backend = "mlx"
    if not voice:
        if backend == "qwen3_tts":
            voice = "tw_ref_female" if lang == "zh" else "default"
        elif backend == "avspeech":
            voice = "zh-TW" if lang == "zh" else "en-US"
        else:
            voice = "zf_xiaobei" if lang == "zh" else "af_heart"
    return backend, voice


def normalize_peak(a: np.ndarray, target: float = 0.62) -> np.ndarray:
    a = np.asarray(a, dtype=np.float32).flatten()
    if a.size == 0:
        return a
    peak = float(np.max(np.abs(a)))
    return a * (target / peak) if peak > 1e-4 else a


class TTS:
    def __init__(self, model: str, voice: str, lang: str = "en", backend: str = "mlx", device: str | None = None,
                 ref_audio: str = "", ref_text: str = ""):
        self.voice, self.backend, self.lang = voice, backend, lang
        self.voice_id = voice
        self.needs_simplified = backend != "avspeech"
        self.lang_code = {"en": "a", "zh": "z"}.get(lang, "a")
        self._proc = None
        self._tmpdir = None
        self._cache_1x: tuple[str, Path] | None = None
        self._ref_audio: str | None = None
        self._ref_text: str = ""
        if backend == "qwen3_tts":
            from mlx_audio.tts.utils import load_model
            self.model_id = model if (model and "kokoro" not in model.lower()) else QWEN3_TTS_DEFAULT_MODEL
            ref_path: Path | None = None
            if ref_audio:
                ref_path = Path(ref_audio)
            elif voice and Path(voice).is_file():
                ref_path = Path(voice)
            elif lang == "zh" and DEFAULT_TW_REF_AUDIO.is_file():
                ref_path = DEFAULT_TW_REF_AUDIO
            if ref_path is not None and ref_path.is_file():
                self._ref_audio = str(ref_path)
                if ref_text:
                    self._ref_text = ref_text
                elif ref_path.resolve() == DEFAULT_TW_REF_AUDIO.resolve():
                    self._ref_text = DEFAULT_TW_REF_TEXT
                self.voice_id = f"qwen3-tts-1.7b:{ref_path.stem}"
            else:
                self.voice_id = "qwen3-tts-1.7b"
            self._tmpdir = tempfile.TemporaryDirectory(prefix="gapcaster_qwen3tts_")
            atexit.register(self.close)
            self.model = load_model(self.model_id)
            self.sr = int(getattr(self.model, "sample_rate", 24000))
        elif backend == "avspeech":
            if not avspeech_available():
                raise RuntimeError("avspeech TTS backend requires macOS with `swift` installed")
            self._tmpdir = tempfile.TemporaryDirectory(prefix="gapcaster_avspeech_")
            script_path = Path(self._tmpdir.name) / "worker.swift"
            script_path.write_text(_AVSPEECH_SWIFT, encoding="utf-8")
            locale = "zh-TW" if lang == "zh" else "en-US"
            self._proc = subprocess.Popen(
                ["swift", str(script_path), locale, voice],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
            )
            atexit.register(self.close)
            hello = json.loads(self._proc.stdout.readline() or "{}")
            if not hello.get("ready"):
                self.close()
                raise RuntimeError(f"avspeech worker failed to start: {hello}")
            self.voice_id = hello.get("voice_id", voice)
            self.sr = 24000
        elif backend == "kokoro":
            import torch
            from kokoro import KPipeline
            device = device or ("xpu" if hasattr(torch, "xpu") and torch.xpu.is_available() else "cpu")
            self.pipe = KPipeline(lang_code=self.lang_code, repo_id="hexgrad/Kokoro-82M", device=device)
            self.sr = 24000
        else:
            from mlx_audio.tts.utils import load_model
            self.model = load_model(model)
            self.sr = self.model.sample_rate
        self.calls = 0
        self.audio_seconds = 0.0
        if lang == "zh" and backend == "avspeech":
            self.synth("準備。")
        elif lang == "zh" and backend == "qwen3_tts":
            self.synth("准备。")
        else:
            self.synth("Ready.")

    def close(self):
        if self._proc is not None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                pass
            self._proc = None
        if self._tmpdir is not None:
            try:
                self._tmpdir.cleanup()
            except Exception:
                pass
            self._tmpdir = None

    def _synth_avspeech(self, text: str, speed: float) -> np.ndarray:
        assert self._proc is not None and self._tmpdir is not None
        tmp = Path(self._tmpdir.name)
        if self._cache_1x is None or self._cache_1x[0] != text:
            raw_wav = tmp / "raw.wav"
            base_24k = tmp / "base_24k.wav"
            req = json.dumps({"text": text, "out": str(raw_wav)}, ensure_ascii=False)
            self._proc.stdin.write(req + "\n")
            self._proc.stdin.flush()
            self._proc.stdout.readline()
            if not raw_wav.exists() or raw_wav.stat().st_size == 0:
                return np.zeros(1, dtype=np.float32)
            subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(raw_wav),
                 "-ar", str(self.sr), "-ac", "1", str(base_24k)],
                check=True,
            )
            self._cache_1x = (text, base_24k)
        src_wav = self._cache_1x[1]
        if abs(speed - 1.0) > 1e-3:
            sp_wav = tmp / "speed_24k.wav"
            subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(src_wav),
                 "-af", f"atempo={speed:.4f}", "-ar", str(self.sr), "-ac", "1", str(sp_wav)],
                check=True,
            )
            src_wav = sp_wav
        a, _ = sf.read(src_wav, dtype="float32")
        return np.asarray(a, dtype=np.float32)

    def _synth_qwen3_tts(self, text: str, speed: float) -> np.ndarray:
        assert self._tmpdir is not None
        tmp = Path(self._tmpdir.name)
        if self._cache_1x is None or self._cache_1x[0] != text:
            base_24k = tmp / "qwen3_base.wav"
            max_ok = max(12.0, len(text) * 0.75 + 4.0)
            best = np.zeros(1, dtype=np.float32)
            for temp, top_p in ((0.3, 0.8), (0.2, 0.75)):
                kw = {"text": text, "lang_code": "zh" if self.lang == "zh" else "auto",
                      "temperature": temp, "top_p": top_p}
                if self._ref_audio:
                    kw["ref_audio"] = self._ref_audio
                    if self._ref_text:
                        kw["ref_text"] = self._ref_text
                chunks = [np.array(r.audio, dtype=np.float32) for r in self.model.generate(**kw)]
                cand = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
                cand = normalize_peak(trim(cand, self.sr, thresh=0.008), target=0.62)
                dur = len(cand) / self.sr
                best = cand
                if 0.15 <= dur <= max_ok:
                    break
            sf.write(base_24k, best, self.sr)
            self._cache_1x = (text, base_24k)
        src_wav = self._cache_1x[1]
        if abs(speed - 1.0) > 1e-3:
            sp_wav = tmp / "qwen3_speed.wav"
            subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(src_wav),
                 "-af", f"atempo={speed:.4f}", "-ar", str(self.sr), "-ac", "1", str(sp_wav)],
                check=True,
            )
            src_wav = sp_wav
        a, _ = sf.read(src_wav, dtype="float32")
        return np.asarray(a, dtype=np.float32)

    def _generate(self, text, speed):
        if self.backend == "qwen3_tts":
            return [self._synth_qwen3_tts(text, speed)]
        if self.backend == "avspeech":
            return [self._synth_avspeech(text, speed)]
        if self.backend == "kokoro":
            return [np.asarray(r.audio, dtype=np.float32) for r in self.pipe(text, voice=self.voice, speed=speed)]
        return [np.array(r.audio, dtype=np.float32) for r in
                self.model.generate(text=text, voice=self.voice, speed=speed, lang_code=self.lang_code)]

    def synth(self, text: str, speed: float = 1.0):
        chunks = self._generate(text, speed)
        audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
        audio = trim(audio, self.sr)
        self.calls += 1
        self.audio_seconds += len(audio) / self.sr
        return audio, len(audio) / self.sr


def trim(a, sr, thresh: float = 0.005):
    """Cut leading/trailing near-silence while keeping soft sentence-final vowel release."""
    idx = np.where(np.abs(a) > thresh)[0]
    if len(idx) == 0:
        return a
    pad_lead = int(0.03 * sr)
    pad_tail = int(0.08 * sr)
    return a[max(0, idx[0] - pad_lead): min(len(a), idx[-1] + pad_tail)]
