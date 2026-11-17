"""Local Describer Web Studio (`gapcaster web`).

Binds strictly to 127.0.0.1 by default, uses only the Python standard library, and makes zero
external network requests. Lets a non-technical audio describer inspect runs (including bundled
English and Mandarin samples), upload a local clip to draft narration in English or Traditional
Chinese, review and edit every line with its visual evidence, and export only approved lines
directly from the browser without touching a terminal.
"""
import json
import mimetypes
import re
import threading
import time
import urllib.parse
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import approve, review
from .config import Settings

STUDIO_HTML = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GapCaster Small · 本地口述影像工作台 / Local Describer Studio</title>
<style>
:root{--bg:#101412;--card:#181e1b;--card2:#202824;--ink:#eff3f0;--muted:#a8b3ad;--line:#313c36;--accent:#fb923c;--accent-ink:#241102;--ok:#6ee7a8;--focus:#fde047}
@media (prefers-color-scheme:light){:root{--bg:#f5f6f2;--card:#ffffff;--card2:#eef1ec;--ink:#181d1a;--muted:#525e57;--line:#cfd6d0;--accent:#b44309;--accent-ink:#ffffff;--ok:#1d7244;--focus:#0052a3}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC","PingFang TC",sans-serif}
a{color:inherit}
.skip{position:absolute;left:-999px;top:0;background:var(--accent);color:var(--accent-ink);padding:10px 16px;border-radius:0 0 8px 0;z-index:10;font-weight:700}
.skip:focus{left:0}
.wrap{max-width:1040px;margin:0 auto;padding:24px 20px 64px}
header{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;padding-bottom:16px;border-bottom:1px solid var(--line)}
.brand{font-size:21px;font-weight:800;letter-spacing:-.01em}
.brand span{color:var(--accent)}
.badge{font-size:13px;padding:4px 10px;border-radius:999px;border:1px solid var(--line);background:var(--card2);color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;margin-top:20px}
.card h2{margin:0 0 8px;font-size:20px}
.sub{color:var(--muted);margin:0 0 14px;font-size:14.5px}
.runs{display:grid;gap:12px}
.run-row{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.run-meta{font-size:13.5px;color:var(--muted)}
.acts{display:flex;gap:8px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:8px 14px;border-radius:9px;border:1px solid var(--accent);background:var(--accent);color:var(--accent-ink);font:inherit;font-size:14px;font-weight:700;text-decoration:none;cursor:pointer}
.btn.sec{background:transparent;color:var(--ink);border-color:var(--line)}
button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
form .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-bottom:12px}
label{display:block;font-weight:600;font-size:14px;margin-bottom:4px}
input,select,textarea{width:100%;padding:9px 11px;border-radius:8px;border:1px solid var(--line);background:var(--card2);color:var(--ink);font:inherit}
textarea{min-height:76px;font-family:ui-monospace,Menlo,monospace;font-size:13px}
pre.log{background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:12px;font-size:13px;max-height:240px;overflow:auto;white-space:pre-wrap;margin:12px 0 0}
footer{margin-top:28px;padding-top:16px;border-top:1px solid var(--line);font-size:13.5px;color:var(--muted)}
</style>
</head>
<body>
<a class="skip" href="#main">跳到主要內容 · Skip to main content</a>
<div class="wrap">
  <header>
    <div class="brand">Gap<span>Caster</span> Small · 本地工作台 / Local Studio</div>
    <div class="badge">127.0.0.1 · 零雲端上傳 / Zero cloud uploads · ≤10B open models</div>
  </header>
  <main id="main">
    <section class="card" aria-labelledby="h-runs">
      <h2 id="h-runs">1. 審核與匯出 · Inspect &amp; Review Runs</h2>
      <p class="sub">無需下載模型即可直接開啟內建的繁體中文與英文 8B 示範，逐句審核畫面證據並一鍵匯出核准後的字幕與音軌。 Open any run below to audit evidence per line, edit text, and export only approved lines.</p>
      <div id="runs-list" class="runs" role="region" aria-live="polite">載入中… / Loading…</div>
    </section>

    <section class="card" aria-labelledby="h-new">
      <h2 id="h-new">2. 在本機草擬新影片 · Draft a New Video Locally</h2>
      <p class="sub">影片、逐字稿與草稿全程留在這台電腦上。需要本機已安裝 ffmpeg 與對應模型（預設 Qwen3-VL-8B + Whisper + Kokoro-82M）。 Video and drafts never leave this machine.</p>
      <form id="run-form">
        <div class="grid">
          <div>
            <label for="f-video">影片檔案 · Video file (.mp4/.mov/.mkv)</label>
            <input id="f-video" name="video" type="file" accept="video/*" required>
          </div>
          <div>
            <label for="f-lang">口述語言 · Narration language</label>
            <select id="f-lang" name="lang">
              <option value="zh">繁體中文 (Mandarin, Traditional Chinese text)</option>
              <option value="en">English</option>
            </select>
          </div>
          <div>
            <label for="f-start">起點秒數 · Start (s)</label>
            <input id="f-start" name="start" type="number" step="0.1" min="0" value="0">
          </div>
          <div>
            <label for="f-end">終點秒數（空白＝全片）· End (s, optional)</label>
            <input id="f-end" name="end" type="number" step="0.1" min="1" placeholder="e.g. 60">
          </div>
        </div>
        <div style="margin-bottom:12px">
          <label for="f-cast">角色表 YAML（選填，由口述影像員決定人物稱呼）· Optional Cast Sheet YAML</label>
          <textarea id="f-cast" name="cast" placeholder="- name: 老人&#10;  look: older man, grey hair, dark checked jacket"></textarea>
        </div>
        <button type="submit" class="btn" id="run-btn">在本機開始草擬 · Run Local Pipeline</button>
        <div id="job-status" role="status" aria-live="polite" style="margin-top:10px;font-weight:700"></div>
        <pre id="job-log" class="log" hidden></pre>
      </form>
    </section>
  </main>
  <footer>
    資料主權說明 / Data sovereignty: 本介面預設僅綁定本機迴路 (<code>127.0.0.1</code>)，不建立帳號、不傳送遙測、不呼叫任何外部 API；未經人工核准的句子絕不會混入匯出成品。
  </footer>
</div>
<script>
async function loadRuns(){
  const res = await fetch('/api/runs');
  const data = await res.json();
  const box = document.getElementById('runs-list');
  if(!data.runs.length){ box.textContent = '尚無紀錄 / No runs yet.'; return; }
  box.innerHTML = '';
  for(const r of data.runs){
    const row = document.createElement('div');
    row.className = 'run-row';
    const info = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = r.title + (r.kind === 'sample' ? ' [內建示範 / Bundled sample]' : '');
    const meta = document.createElement('div');
    meta.className = 'run-meta';
    meta.textContent = `語言/Lang: ${r.lang} · 塞入空檔/Fitted: ${r.fitted}/${r.lines} · 對白重疊/Speech overlap: ${r.overlap_s}s · 峰值記憶體/Peak: ${r.peak_gb ?? '—'} GB`;
    info.appendChild(title); info.appendChild(meta);
    const acts = document.createElement('div');
    acts.className = 'acts';
    const aRev = document.createElement('a');
    aRev.className = 'btn'; aRev.href = `/${r.kind}s/${encodeURIComponent(r.slug)}/review.html`;
    aRev.textContent = '開啟審核頁 · Review & Export';
    const aVtt = document.createElement('a');
    aVtt.className = 'btn sec'; aVtt.href = `/${r.kind}s/${encodeURIComponent(r.slug)}/ad.vtt`;
    aVtt.textContent = 'WebVTT';
    const aJson = document.createElement('a');
    aJson.className = 'btn sec'; aJson.href = `/${r.kind}s/${encodeURIComponent(r.slug)}/script.json`;
    aJson.textContent = 'Provenance JSON';
    acts.append(aRev, aVtt, aJson);
    if(r.approved_url){
      const aApp = document.createElement('a');
      aApp.className = 'btn sec'; aApp.href = r.approved_url;
      aApp.textContent = '已核准字幕 · Approved VTT';
      acts.appendChild(aApp);
    }
    row.append(info, acts);
    box.appendChild(row);
  }
}
document.getElementById('run-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = document.getElementById('f-video').files[0];
  if(!f) return;
  const btn = document.getElementById('run-btn');
  const st = document.getElementById('job-status');
  const logEl = document.getElementById('job-log');
  btn.disabled = true; logEl.hidden = false; logEl.textContent = '';
  st.textContent = '上傳至本機暫存中… / Staging local file…';
  const q = new URLSearchParams({
    filename: f.name,
    lang: document.getElementById('f-lang').value,
    start: document.getElementById('f-start').value || '0',
    end: document.getElementById('f-end').value || '',
    cast: document.getElementById('f-cast').value || ''
  });
  const res = await fetch('/api/run?' + q.toString(), {method: 'POST', body: f});
  const job = await res.json();
  if(!res.ok){ st.textContent = '錯誤 / Error: ' + (job.error || res.status); btn.disabled = false; return; }
  const poll = setInterval(async () => {
    const jr = await (await fetch('/api/jobs/' + job.job_id)).json();
    logEl.textContent = (jr.logs || []).join('\\n');
    logEl.scrollTop = logEl.scrollHeight;
    if(jr.status === 'done'){
      clearInterval(poll); btn.disabled = false;
      st.innerHTML = `完成！<a href="/runs/${encodeURIComponent(jr.slug)}/review.html">點此開啟審核頁 · Open Review Page</a>`;
      loadRuns();
    } else if(jr.status === 'error'){
      clearInterval(poll); btn.disabled = false;
      st.textContent = '執行失敗 / Failed: ' + jr.error;
    } else {
      st.textContent = '本機執行中… / Running locally…';
    }
  }, 1000);
});
loadRuns();
</script>
</body>
</html>
"""

REVIEW_INJECT = """
<div id="studio-export-bar" role="region" aria-label="Local Studio Export" style="background:var(--card);border:2px solid var(--ad);border-radius:10px;padding:12px 14px;display:flex;flex-wrap:wrap;gap:10px;align-items:center">
  <strong>本地工作台 · Local Studio:</strong>
  <span style="color:var(--muted);font-size:13.5px">核准或修改上方句子後，直接在本機重混核准版（未核准句子不會輸出）。</span>
  <span style="flex:1"></span>
  <a href="/" style="font-size:13px;margin-right:6px">← 返回列表 / Studio Home</a>
  <button class="primary" id="studio-export-btn" type="button">一鍵匯出核准版 · Export Approved Track</button>
  <div id="studio-export-status" role="status" aria-live="polite" style="width:100%;font-size:13.5px;color:var(--ok)"></div>
</div>
<script>
(function(){
  const bar = document.getElementById('studio-export-bar');
  const anchor = document.querySelector('.bar2');
  if(bar && anchor) anchor.insertAdjacentElement('afterend', bar);
  const btn = document.getElementById('studio-export-btn');
  const statusEl = document.getElementById('studio-export-status');
  if(!btn) return;
  btn.onclick = async () => {
    document.querySelectorAll('.line').forEach(el=>{
      if(el.querySelector('.txt').isContentEditable) el.querySelector('button[data-act=edit]').click();
    });
    const lines = [...document.querySelectorAll('.line')].map(el=>({
      id: el.dataset.id,
      status: (st[el.dataset.id]||{}).status || 'pending',
      original: el.dataset.orig,
      text: (st[el.dataset.id]||{}).text || el.dataset.orig
    }));
    btn.disabled = true;
    statusEl.textContent = '正在本機重混核准句子… / Exporting approved lines locally…';
    try {
      const res = await fetch('/api/export/__KIND__/__SLUG__', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({run: document.body.dataset.run, lines})
      });
      const out = await res.json();
      if(!res.ok) throw new Error(out.error || ('HTTP ' + res.status));
      let links = `<a href="${out.base_url}/ad.vtt" download>ad.vtt</a> · <a href="${out.base_url}/ad.srt" download>ad.srt</a> · <a href="${out.base_url}/ad_track.wav" download>ad_track.wav</a>`;
      if(out.video_mixed) links = `<a href="${out.base_url}/clip_with_ad.mp4" download><strong>clip_with_ad.mp4</strong></a> · ` + links;
      statusEl.innerHTML = `已匯出 ${out.kept} 句核准旁白（略過 ${out.dropped} 句）：` + links;
    } catch(err) {
      statusEl.textContent = '匯出失敗 / Export error: ' + err.message;
    } finally {
      btn.disabled = false;
    }
  };
})();
</script>
"""


def _safe_slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-")
    return s or "run"


def _summarise_run(folder: Path, kind: str, approved_root: Path) -> dict | None:
    sj = folder / "script.json"
    if not sj.exists() or not (folder / "review.html").exists():
        return None
    try:
        doc = json.loads(sj.read_text(encoding="utf-8"))
    except Exception:
        return None
    m = doc.get("metrics", {})
    lang = (doc.get("settings") or {}).get("lang", "en")
    app_vtt = (folder / "approved" / "ad.vtt") if kind == "run" else (approved_root / f"{folder.name}-approved" / "ad.vtt")
    app_url = (f"/runs/{folder.name}/approved/ad.vtt" if kind == "run"
               else f"/runs/{folder.name}-approved/ad.vtt") if app_vtt.exists() else None
    return {
        "slug": folder.name,
        "title": folder.name,
        "kind": kind,
        "lang": lang,
        "lines": m.get("lines", 0),
        "fitted": m.get("fit_after_loop", 0),
        "overlap_s": m.get("ad_overlap_with_detected_dialogue_s", 0.0),
        "peak_gb": m.get("mlx_peak_memory_gb"),
        "approved_url": app_url,
    }


class StudioState:
    def __init__(self, runs_dir: Path, samples_dir: Path | None = None, runner=None):
        self.runs_dir = Path(runs_dir).resolve()
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        default_samples = Path(__file__).resolve().parent.parent / "samples"
        self.samples_dir = Path(samples_dir).resolve() if samples_dir else default_samples
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.runner = runner  # injectable for tests

    def list_runs(self) -> list[dict]:
        items = []
        if self.runs_dir.exists():
            for p in sorted(self.runs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if p.is_dir():
                    r = _summarise_run(p, "run", self.runs_dir)
                    if r:
                        items.append(r)
        if self.samples_dir and self.samples_dir.exists():
            for p in sorted(self.samples_dir.iterdir()):
                if p.is_dir():
                    r = _summarise_run(p, "sample", self.runs_dir)
                    if r:
                        items.append(r)
        return items


def make_handler(state: StudioState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return  # quiet clean local studio logs

        def _json(self, obj, status=HTTPStatus.OK):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _bytes(self, body: bytes, ctype: str, status=HTTPStatus.OK):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_file(self, root: Path, rel: str, inject_kind: str | None = None, slug: str = ""):
            root_r = root.resolve()
            target = (root_r / rel).resolve()
            if not target.is_relative_to(root_r) or not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if inject_kind and target.name == "review.html":
                raw = target.read_text(encoding="utf-8")
                patch = REVIEW_INJECT.replace("__KIND__", inject_kind).replace("__SLUG__", slug)
                raw = raw + patch
                self._bytes(raw.encode("utf-8"), "text/html; charset=utf-8")
                return
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if target.suffix == ".vtt":
                ctype = "text/vtt; charset=utf-8"
            elif target.suffix in (".srt", ".txt", ".yaml"):
                ctype = "text/plain; charset=utf-8"
            size = target.stat().st_size
            rng = self.headers.get("Range")
            if rng and rng.startswith("bytes="):
                m = re.match(r"bytes=(\d+)-(\d*)", rng)
                if m:
                    start = min(int(m.group(1)), max(0, size - 1))
                    end = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
                    length = max(0, end - start + 1)
                    with target.open("rb") as f:
                        f.seek(start)
                        chunk = f.read(length)
                    self.send_response(HTTPStatus.PARTIAL_CONTENT)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                    self.send_header("Content-Length", str(len(chunk)))
                    self.end_headers()
                    self.wfile.write(chunk)
                    return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            with target.open("rb") as f:
                while buf := f.read(65536):
                    self.wfile.write(buf)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = urllib.parse.unquote(parsed.path)
            if path in ("/", "/index.html"):
                self._bytes(STUDIO_HTML.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/api/runs":
                self._json({"runs": state.list_runs()})
                return
            if path.startswith("/api/jobs/"):
                jid = path.split("/api/jobs/", 1)[1]
                with state.lock:
                    job = state.jobs.get(jid)
                if not job:
                    self._json({"error": "unknown job"}, HTTPStatus.NOT_FOUND)
                else:
                    self._json(job)
                return
            for prefix, root, kind in (("/runs/", state.runs_dir, "run"),
                                       ("/samples/", state.samples_dir, "sample")):
                if root and path.startswith(prefix):
                    rest = path[len(prefix):]
                    parts = rest.split("/", 1)
                    slug = _safe_slug(parts[0])
                    rel = parts[1] if len(parts) > 1 and parts[1] else "review.html"
                    self._serve_file(root / slug, rel, inject_kind=kind, slug=slug)
                    return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = urllib.parse.unquote(parsed.path)
            length = int(self.headers.get("Content-Length") or 0)
            if path.startswith("/api/export/"):
                parts = path[len("/api/export/"):].split("/", 1)
                if len(parts) != 2 or parts[0] not in ("run", "sample"):
                    self._json({"error": "bad export path"}, HTTPStatus.BAD_REQUEST)
                    return
                kind, slug = parts[0], _safe_slug(parts[1])
                src_root = state.runs_dir if kind == "run" else state.samples_dir
                run_dir = (src_root / slug).resolve()
                if not run_dir.is_relative_to(src_root.resolve()) or not (run_dir / "script.json").exists():
                    self._json({"error": "run not found"}, HTTPStatus.NOT_FOUND)
                    return
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    if kind == "sample":
                        out_dir = state.runs_dir / f"{slug}-approved"
                        out_dir.mkdir(parents=True, exist_ok=True)
                        app_file = out_dir / "approved.json"
                        base_url = f"/runs/{slug}-approved"
                    else:
                        out_dir = None
                        app_file = run_dir / "approved.json"
                        base_url = f"/runs/{slug}/approved"
                    app_file.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
                    res = approve.apply(run_dir, app_file, out_dir=out_dir)
                    res["base_url"] = base_url
                    self._json(res)
                except Exception as e:
                    self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
                return

            if path == "/api/run":
                qs = urllib.parse.parse_qs(parsed.query)
                fname = _safe_slug((qs.get("filename") or ["clip.mp4"])[0])
                lang = (qs.get("lang") or ["zh"])[0]
                if lang not in ("en", "zh"):
                    self._json({"error": "unsupported lang"}, HTTPStatus.BAD_REQUEST)
                    return
                start_s = float((qs.get("start") or ["0"])[0] or 0.0)
                end_raw = (qs.get("end") or [""])[0].strip()
                end_s = float(end_raw) if end_raw else None
                cast_txt = (qs.get("cast") or [""])[0].strip()
                stamp = time.strftime("%Y%m%d-%H%M%S")
                slug = _safe_slug(f"{Path(fname).stem}-{lang}-{stamp}")
                out_dir = state.runs_dir / slug
                out_dir.mkdir(parents=True, exist_ok=True)
                vid_path = out_dir / fname
                remaining = length
                with vid_path.open("wb") as vf:
                    while remaining > 0:
                        chunk = self.rfile.read(min(65536, remaining))
                        if not chunk:
                            break
                        vf.write(chunk)
                        remaining -= len(chunk)
                cast_path = None
                if cast_txt:
                    cast_path = out_dir / "cast.yaml"
                    cast_path.write_text(cast_txt, encoding="utf-8")
                job_id = uuid.uuid4().hex[:10]
                job = {"job_id": job_id, "slug": slug, "status": "running", "logs": [], "error": None}
                with state.lock:
                    state.jobs[job_id] = job

                def _worker():
                    def _log(msg):
                        with state.lock:
                            job["logs"].append(str(msg))
                    try:
                        s = Settings(lang=lang, tts_voice="zf_xiaobei" if lang == "zh" else Settings.tts_voice)
                        if state.runner:
                            state.runner(vid_path, out_dir, start_s, end_s, cast_path, s, _log)
                        else:
                            from .pipeline import run as run_pipeline
                            run_pipeline(str(vid_path), str(out_dir), start=start_s, end=end_s,
                                         cast_path=str(cast_path) if cast_path else None, settings=s, log=_log)
                            review.build(out_dir)
                        with state.lock:
                            job["status"] = "done"
                    except Exception as exc:
                        with state.lock:
                            job["status"] = "error"
                            job["error"] = str(exc)

                threading.Thread(target=_worker, daemon=True).start()
                self._json({"job_id": job_id, "slug": slug})
                return

            self.send_error(HTTPStatus.NOT_FOUND)

    return Handler


def create_server(host: str = "127.0.0.1", port: int = 7860, runs_dir: str | Path = "runs",
                  samples_dir: str | Path | None = None, runner=None) -> ThreadingHTTPServer:
    state = StudioState(Path(runs_dir), Path(samples_dir) if samples_dir else None, runner=runner)
    return ThreadingHTTPServer((host, port), make_handler(state))


def serve(host: str = "127.0.0.1", port: int = 7860, runs_dir: str | Path = "runs", open_browser: bool = False):
    srv = create_server(host=host, port=port, runs_dir=runs_dir)
    actual_port = srv.server_address[1]
    url = f"http://{host}:{actual_port}/"
    print(f"GapCaster Local Studio listening on {url} (local-only, Ctrl+C to stop)")
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
