import argparse
import json

from .config import Settings


def main():
    ap = argparse.ArgumentParser(prog="gapcaster", description="Draft an audio-description track that fits the silences between dialogue.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="process a video")
    r.add_argument("video")
    r.add_argument("--out", required=True)
    r.add_argument("--start", type=float, default=0.0)
    r.add_argument("--end", type=float, default=None)
    r.add_argument("--cast", help="YAML cast sheet: [{name, look}]")
    r.add_argument("--ref-srt", help="reference subtitles, used only for evaluation")
    r.add_argument("--lang", default="en", choices=["en", "zh"], help="narration language: en (English) or zh (Mandarin, Traditional Chinese text)")
    r.add_argument("--voice", default=None, help="TTS voice (default: tw_ref_female via Qwen3-TTS for zh, af_heart via Kokoro for en)")
    r.add_argument("--backend", default="mlx", choices=["mlx", "openai"])
    r.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    r.add_argument("--model", default="qwen", help="model name on the OpenAI-compatible server (vLLM --served-model-name)")
    r.add_argument("--concurrency", type=int, default=8, help="parallel requests to the server (shot facts, verifier)")
    r.add_argument("--asr", default="mlx", choices=["mlx", "openvino"], help="speech recognition runtime")
    r.add_argument("--asr-device", default="CPU", help="OpenVINO device for ASR: CPU or GPU")
    r.add_argument("--tts", default="auto", choices=["auto", "qwen3_tts", "avspeech", "mlx", "kokoro"],
                   help="TTS runtime: auto (Qwen3-TTS-1.7B zh-TW for zh, mlx Kokoro for en), qwen3_tts, avspeech, mlx, or kokoro")
    r.add_argument("--inject", type=int, default=0, help="run the injected-error test on N lines")
    v = sub.add_parser("review", help="build the review page for a run")
    v.add_argument("run_dir")
    x = sub.add_parser("export", help="re-mix a run from the describer's approved.json")
    x.add_argument("run_dir")
    x.add_argument("--approved", required=True)
    x.add_argument("--tts", default=None, choices=["qwen3_tts", "avspeech", "mlx", "kokoro"], help="TTS runtime for edited lines (default: the run's own)")
    w = sub.add_parser("web", help="launch the local-only Describer Web Studio (127.0.0.1)")
    w.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1 for local privacy)")
    w.add_argument("--port", type=int, default=7860)
    w.add_argument("--runs-dir", default="runs")
    w.add_argument("--open", action="store_true", help="open the studio in the default browser")
    a = ap.parse_args()
    if a.cmd == "run":
        from .pipeline import run
        from .tts import default_tts_model, resolve_tts
        tts_backend, tts_voice = resolve_tts(a.lang, a.tts, a.voice)
        s = Settings(lang=a.lang, llm_backend=a.backend, llm_base_url=a.base_url, llm_model_name=a.model,
                     concurrency=a.concurrency, asr_backend=a.asr, asr_device=a.asr_device, tts_backend=tts_backend,
                     tts_model=default_tts_model(tts_backend), tts_voice=tts_voice)
        doc = run(a.video, a.out, a.start, a.end, a.cast, a.ref_srt, s, inject=a.inject)
        from .review import build
        build(a.out)
        print(json.dumps({k: v for k, v in doc["metrics"].items() if k != "injected_error_test"}, indent=1))
    elif a.cmd == "export":
        from .approve import apply
        print(json.dumps(apply(a.run_dir, a.approved, tts_backend=a.tts), indent=1))
    elif a.cmd == "web":
        from .web import serve
        serve(host=a.host, port=a.port, runs_dir=a.runs_dir, open_browser=a.open)
    else:
        from .review import build
        print(build(a.run_dir))


if __name__ == "__main__":
    main()
