"""End-to-end HTTP tests for the Local Describer Web Studio (`gapcaster web`)."""
import json
import threading
import time
import urllib.error
import urllib.request

import numpy as np
import soundfile as sf

from gapcaster import review, web


def _make_sample(root, name="demo-zh", lang="zh"):
    d = root / name
    (d / "lines").mkdir(parents=True)
    sf.write(d / "lines" / "AD001.wav", np.zeros(4800, dtype=np.float32), 24000)
    sf.write(d / "lines" / "AD002.wav", np.zeros(4800, dtype=np.float32), 24000)
    doc = {
        "source": {"file": "clip.mp4", "start": 0.0, "end": 10.0},
        "settings": {"lang": lang, "tts_voice": "zf_xiaobei"},
        "shots": [{"id": "S001", "start": 0.0, "end": 10.0, "frames": [], "facts": {"key": "Old man kneels"}}],
        "dialogue": [{"start": 0.0, "end": 1.0, "text": "Hi"}],
        "lines": [
            {"id": "AD001", "start": 2.0, "window_end": 5.0, "avail": 3.0, "text": "老人跪在地上。",
             "duration": 0.2, "speed": 1.0, "attempts": [{"text": "老人跪在地上。", "fit": True, "reason": "fits"}],
             "status": "fit", "shots": ["S001"], "flags": [], "audio": "lines/AD001.wav"},
            {"id": "AD002", "start": 6.0, "window_end": 9.0, "avail": 3.0, "text": "狙擊手瞄準。",
             "duration": 0.2, "speed": 1.0, "attempts": [{"text": "狙擊手瞄準。", "fit": True, "reason": "fits"}],
             "status": "fit", "shots": ["S001"], "flags": [], "audio": "lines/AD002.wav"},
        ],
        "metrics": {
            "clip_seconds": 10.0, "shots": 1, "lines": 2, "lines_placed": 2,
            "first_try_fit": 2, "fit_after_loop": 2,
            "ad_overlap_with_detected_dialogue_s": 0.0,
            "seconds_per_content_minute": 40.0, "mlx_peak_memory_gb": 13.8,
        },
    }
    (d / "script.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    (d / "ad.vtt").write_text("WEBVTT\n\nAD001\n00:00:02.000 --> 00:00:02.200\n老人跪在地上。\n", encoding="utf-8")
    review.build(d)
    return d


def test_studio_lists_samples_serves_range_and_exports_approved(tmp_path):
    runs_dir = tmp_path / "runs"
    samples_dir = tmp_path / "samples"
    _make_sample(samples_dir, "demo-zh", "zh")

    def fake_runner(vid_path, out_dir, start_s, end_s, cast_path, settings, log):
        log("mock pipeline ok")
        _make_sample(out_dir.parent, out_dir.name, settings.lang)

    srv = web.create_server("127.0.0.1", 0, runs_dir=runs_dir, samples_dir=samples_dir, runner=fake_runner)
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        # 1. Studio home page (with WCAG landmarks & h1)
        home = urllib.request.urlopen(f"{base}/").read().decode("utf-8")
        assert "GapCaster" in home and "127.0.0.1" in home
        assert '<h1 class="brand">' in home and '<main id="main" tabindex="-1">' in home

        # 2. Runs listing includes bundled sample
        listing = json.loads(urllib.request.urlopen(f"{base}/api/runs").read().decode("utf-8"))
        assert len(listing["runs"]) == 1
        assert listing["runs"][0]["slug"] == "demo-zh" and listing["runs"][0]["lang"] == "zh"

        # 3. Review page includes WCAG lang/landmarks/ARIA and injected one-click export toolbar
        rev = urllib.request.urlopen(f"{base}/samples/demo-zh/review.html").read().decode("utf-8")
        assert "studio-export-btn" in rev and "/api/export/sample/demo-zh" in rev
        assert '<html lang="zh-Hant">' in rev and '<main id="main" tabindex="-1">' in rev
        assert 'aria-label="核准 AD001"' in rev and 'aria-pressed="false"' in rev

        # 4. HTTP Range support for audio/video scrubbing
        req = urllib.request.Request(f"{base}/samples/demo-zh/lines/AD001.wav", headers={"Range": "bytes=0-15"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 206
            assert len(resp.read()) == 16

        # 5. One-click browser export writes only approved lines to runs/demo-zh-approved/
        payload = {
            "run": "demo",
            "lines": [
                {"id": "AD001", "status": "approved", "text": "老人跪在地上。"},
                {"id": "AD002", "status": "rejected", "text": "狙擊手瞄準。"},
            ],
        }
        req_exp = urllib.request.Request(
            f"{base}/api/export/sample/demo-zh",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        exp = json.loads(urllib.request.urlopen(req_exp).read().decode("utf-8"))
        assert exp["kept"] == 1 and exp["dropped"] == 1
        vtt = urllib.request.urlopen(f"{base}{exp['base_url']}/ad.vtt").read().decode("utf-8")
        assert "老人跪在地上。" in vtt and "狙擊手瞄準。" not in vtt
        assert not (samples_dir / "demo-zh" / "approved").exists()  # bundled sample stays clean

        # 6. Local run job submission & polling
        req_run = urllib.request.Request(
            f"{base}/api/run?filename=test.mp4&lang=zh&start=0&end=5",
            data=b"fake-video-bytes",
            method="POST",
        )
        job = json.loads(urllib.request.urlopen(req_run).read().decode("utf-8"))
        for _ in range(30):
            st = json.loads(urllib.request.urlopen(f"{base}/api/jobs/{job['job_id']}").read().decode("utf-8"))
            if st["status"] != "running":
                break
            time.sleep(0.05)
        assert st["status"] == "done" and "mock pipeline ok" in st["logs"]

        # 7. Path traversal is rejected
        try:
            urllib.request.urlopen(f"{base}/samples/demo-zh/../../etc/passwd")
            assert False, "expected 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        srv.shutdown()
        srv.server_close()
