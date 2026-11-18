"""Static review page for a run: timeline, every AD line with its evidence, attempts and flags.

Compliant with WCAG 2.1 / 2.2 Level AA (and Taiwan MODA Web Accessibility 2.1 AA):
- Language of page (`lang="zh-Hant"` / `lang="en"`) and language of parts (`lang="en"` on English shot facts)
- Full landmark structure (`<header>`, `<main>`, `<footer>`) and keyboard skip link
- ≥4.5:1 text contrast in both light and dark colour schemes; non-colour status indicators (`✓` / `⚠`)
- Heading per AD line (`<h2>`), unique accessible names and `aria-pressed` states on Approve/Edit/Reject,
  keyboard save/cancel (`Ctrl+Enter` / `Escape`) in inline editing, and polite `aria-live` announcements
"""
import base64
import hashlib
import html
import json
import re
from pathlib import Path

CSS = """
:root{--bg:#f4f5f2;--card:#ffffff;--ink:#1b1f1d;--muted:#525c56;--rule:#cfd5cc;--ctrl:#67706a;--dlg:#3d4a44;--gap:#e6ece4;--ad:#b43b08;--ad-ink:#ffffff;--ok:#1b6338;--warn:#7c4700;--no:#b91c1c;--focus:#0052a3}
@media (prefers-color-scheme:dark){:root{--bg:#121513;--card:#1a1e1c;--ink:#e8ece9;--muted:#a6b0aa;--rule:#323b36;--ctrl:#78847d;--dlg:#8fa197;--gap:#232d27;--ad:#fb923c;--ad-ink:#241102;--ok:#7ae0a5;--warn:#f3c65f;--no:#fca5a5;--focus:#fde047}}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
*{box-sizing:border-box}html{scroll-padding-top:88px}body{margin:0;background:var(--bg);color:var(--ink);font:15.5px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC","PingFang TC",sans-serif;overflow-wrap:break-word}
a{color:inherit;text-decoration:underline;text-underline-offset:3px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.skip{position:absolute;left:-9999px;top:0;background:var(--ad);color:var(--ad-ink);padding:10px 16px;border-radius:0 0 8px 0;z-index:20;font-weight:700;text-decoration:none}
.skip:focus{left:0;outline:3px solid var(--focus);outline-offset:2px}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px;display:flex;flex-direction:column;gap:22px}
header,main,footer{display:flex;flex-direction:column;gap:20px}
h1{margin:0;font-size:26px;letter-spacing:-.01em}h1 span{color:var(--ad)}
.sub{color:var(--muted)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kpi{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:12px 14px}
.kpi b{display:block;font-size:24px;font-variant-numeric:tabular-nums}.kpi small{color:var(--muted)}
.tl{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:14px}
.tl svg{width:100%;height:auto;display:block}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--muted);margin-top:6px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px;border:1px solid var(--rule)}
video{width:100%;border-radius:10px;background:#000}
.lines-list{display:flex;flex-direction:column;gap:16px}
.line{display:grid;grid-template-columns:180px 1fr 240px;gap:16px;background:var(--card);border:2px solid var(--rule);border-radius:10px;padding:14px}
.line img{width:100%;border-radius:6px;display:block}
.t-hd{margin:6px 0 2px;font:600 13.5px/1.4 ui-monospace,Menlo,monospace;color:var(--muted)}
.t{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:var(--muted)}
.txt{font-size:17.5px;font-weight:600;margin:4px 0 8px;padding:2px 4px;border-radius:4px}
.att{font-size:13px;color:var(--muted);border-left:2px solid var(--rule);padding-left:10px;display:flex;flex-direction:column;gap:3px;margin-bottom:6px}
.att .x{text-decoration:line-through}
.fit{font-family:ui-monospace,Menlo,monospace;font-size:13px}
.bar{height:8px;border-radius:4px;background:var(--gap);position:relative;margin:4px 0 10px}
.bar i{position:absolute;inset:0 auto 0 0;border-radius:4px;background:var(--ok)}
.chip{display:inline-block;font-size:12.5px;font-weight:700;padding:2px 9px;border-radius:999px;margin:2px 4px 2px 0;background:var(--gap)}
.chip.ok{color:var(--ok)}.chip.warn{color:var(--warn)}
.facts{font-size:13px;color:var(--muted)}
audio{width:100%;height:36px;margin-top:4px}
.bar2{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:10px;align-items:center;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--rule)}
.bar2 b{font-variant-numeric:tabular-nums}
button{font:inherit;font-size:13.5px;font-weight:700;min-height:40px;padding:7px 13px;border-radius:8px;border:1.5px solid var(--ctrl);background:var(--card);color:var(--ink);cursor:pointer}
button:focus-visible,a:focus-visible,video:focus-visible,audio:focus-visible,.txt:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
button.ok{border-color:var(--ok);color:var(--ok)}
button.ok[aria-pressed="true"]{background:var(--ok);color:var(--card)}
button.no{border-color:var(--no);color:var(--no)}
button.no[aria-pressed="true"]{background:var(--no);color:var(--card)}
button.primary{background:var(--ad);border-color:var(--ad);color:var(--ad-ink)}
.acts{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.line[data-state=approved]{border-color:var(--ok)}
.line[data-state=edited]{border-color:var(--ad)}
.line[data-state=rejected]{border-style:dashed;border-color:var(--no)}
.state{font-size:12.5px;font-weight:700;letter-spacing:.04em;color:var(--muted)}
.txt[contenteditable=true]{outline:3px dashed var(--ad);outline-offset:3px;background:var(--bg)}
footer{padding-top:10px;border-top:1px solid var(--rule);font-size:13px;color:var(--muted)}
@media (max-width:820px){.line{grid-template-columns:1fr}}
"""

JS = r"""
const ZH=document.documentElement.lang.startsWith('zh');
const LBL=ZH
  ?{pending:'待審核',approved:'已核准',edited:'已修改',rejected:'已剔除',edit:'修改',save:'儲存',
    ann:(id,s)=>`${id} 狀態已設為：${s}`,editing:id=>`正在編輯 ${id} 旁白文字，按 Ctrl+Enter 儲存，按 Escape 取消`}
  :{pending:'pending',approved:'approved',edited:'edited',rejected:'rejected',edit:'Edit',save:'Save',
    ann:(id,s)=>`${id} marked ${s}`,editing:id=>`Editing ${id} text; press Ctrl+Enter to save or Escape to cancel`};
const KEY='gapcaster-review:'+document.body.dataset.run;
let st={};try{st=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}};
const say=msg=>{const box=document.getElementById('sr-status');if(box)box.textContent=msg;};
function paint(){let c={approved:0,edited:0,rejected:0,pending:0};
 document.querySelectorAll('.line').forEach(el=>{const id=el.dataset.id,s=st[id];const state=s?s.status:'pending';el.dataset.state=state;
  el.querySelector('.state').textContent=LBL[state]||state;if(s&&s.text)el.querySelector('.txt').textContent=s.text;c[state]++;
  const bOk=el.querySelector('button[data-act=approve]'),bNo=el.querySelector('button[data-act=reject]');
  if(bOk)bOk.setAttribute('aria-pressed',(state==='approved'||state==='edited')?'true':'false');
  if(bNo)bNo.setAttribute('aria-pressed',state==='rejected'?'true':'false');});
 for(const k in c)document.getElementById('n-'+k).textContent=c[k];}
function setEditMode(el,on){
 const t=el.querySelector('.txt'),b=el.querySelector('button[data-act=edit]'),id=el.dataset.id;
 if(on){t.dataset.before=t.textContent;t.contentEditable='true';t.setAttribute('role','textbox');t.setAttribute('aria-multiline','true');
  t.setAttribute('aria-label',ZH?`編輯 ${id} 旁白文字`:`Edit narration text for ${id}`);b.textContent=LBL.save;
  b.setAttribute('aria-label',(ZH?'儲存 ':'Save ')+id);t.focus();say(LBL.editing(id));}
 else{t.contentEditable='false';t.removeAttribute('role');t.removeAttribute('aria-multiline');t.removeAttribute('aria-label');
  b.textContent=LBL.edit;b.setAttribute('aria-label',(ZH?'修改 ':'Edit ')+id);}
}
function finishEdit(el){const t=el.querySelector('.txt');if(t.isContentEditable)setEditMode(el,false);return t.textContent.trim();}
document.addEventListener('click',e=>{const b=e.target.closest('button[data-act]');if(!b)return;const el=b.closest('.line'),id=el.dataset.id,t=el.querySelector('.txt');
 if(b.dataset.act==='approve'){const nt=finishEdit(el);const stName=nt===el.dataset.orig?'approved':'edited';st[id]={status:stName,text:nt};say(LBL.ann(id,LBL[stName]));}
 if(b.dataset.act==='reject'){st[id]={status:'rejected',text:finishEdit(el)};say(LBL.ann(id,LBL.rejected));}
 if(b.dataset.act==='edit'){if(t.isContentEditable){const orig=el.dataset.orig,nt=finishEdit(el);const stName=nt===orig?'approved':'edited';st[id]={status:stName,text:nt};say(LBL.ann(id,LBL[stName]));}
  else{setEditMode(el,true);return;}}
 save();paint();});
document.addEventListener('keydown',e=>{const t=e.target.closest('.txt[contenteditable=true]');if(!t)return;const el=t.closest('.line');
 if(e.key==='Escape'){e.preventDefault();if(t.dataset.before!==undefined)t.textContent=t.dataset.before;setEditMode(el,false);el.querySelector('button[data-act=edit]').focus();}
 if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();el.querySelector('button[data-act=edit]').click();el.querySelector('button[data-act=edit]').focus();}});
function download(name,data,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([data],{type}));a.download=name;a.click();}
document.getElementById('dl-json').onclick=()=>{document.querySelectorAll('.line').forEach(el=>{if(el.querySelector('.txt').isContentEditable)el.querySelector('button[data-act=edit]').click();});
 const lines=[...document.querySelectorAll('.line')].map(el=>({id:el.dataset.id,status:(st[el.dataset.id]||{}).status||'pending',original:el.dataset.orig,text:(st[el.dataset.id]||{}).text||el.dataset.orig}));
 download('approved.json',JSON.stringify({run:document.body.dataset.run,lines},null,1),'application/json');};
document.getElementById('dl-vtt').onclick=()=>{let v='WEBVTT\nKind: descriptions\n\n';document.querySelectorAll('.line').forEach(el=>{const s=st[el.dataset.id];if(!s||s.status==='rejected'||s.status==='pending')return;
 v+=el.dataset.id+'\n'+el.dataset.a+' --> '+el.dataset.b+'\n'+s.text+'\n\n';});download('approved.vtt',v,'text/vtt');};
paint();
"""


def _img64(p, width=None):
    try:
        return "data:image/jpeg;base64," + base64.b64encode(Path(p).read_bytes()).decode()
    except OSError:
        return ""


def timeline_svg(doc, zh: bool = False):
    total = doc["metrics"]["clip_seconds"]
    W, H = 1000, 74
    x = lambda t: 10 + (W - 20) * t / total
    label = (f"時間軸：全長 {total:.0f} 秒，{len(doc['dialogue'])} 段對白，{len(doc['lines'])} 句口述影像草稿"
             if zh else f"Timeline: {total:.0f}s clip, {len(doc['dialogue'])} dialogue spans, {len(doc['lines'])} draft AD lines")
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(label)}">']
    parts.append(f'<rect x="10" y="10" width="{W-20}" height="22" rx="4" fill="var(--gap)"/>')
    for s in doc["dialogue"]:
        parts.append(f'<rect x="{x(s["start"]):.1f}" y="10" width="{max(1,x(s["end"])-x(s["start"])):.1f}" height="22" fill="var(--dlg)"/>')
    for r in doc["lines"]:
        if r.get("duration"):
            parts.append(f'<rect x="{x(r["start"]):.1f}" y="38" width="{max(2,x(r["start"]+r["duration"])-x(r["start"])):.1f}" height="14" rx="3" fill="var(--ad)"><title>{html.escape(r["text"])}</title></rect>')
    for t in range(0, int(total) + 1, 10):
        parts.append(f'<text x="{x(t):.1f}" y="68" font-size="10" fill="var(--muted)" text-anchor="middle">{t}s</text>')
    parts.append("</svg>")
    return "".join(parts)


def build(run_dir):
    run = Path(run_dir)
    old_imgs = {}
    if (run / "review.html").exists():
        old_html = (run / "review.html").read_text(encoding="utf-8", errors="ignore")
        old_imgs = dict(re.findall(r'data-id="(AD\d+)"[^>]*><div><img[^>]*src="(data:image/[^"]+)"', old_html))
    doc = json.loads((run / "script.json").read_text(encoding="utf-8"))
    m = doc["metrics"]
    zh = (doc.get("settings") or {}).get("lang") == "zh"
    html_lang = "zh-Hant" if zh else "en"
    shots = {s["id"]: s for s in doc["shots"]}
    inj = m.get("injected_error_test")
    if zh:
        kpis = [(f'{m["fit_after_loop"]}/{m["lines"]}', "塞進對白空檔句數"),
                (f'{m["first_try_fit"]}/{m["lines"]}', "首稿即貼合句數")]
        if "ad_overlap_with_reference_subtitles_s" in m:
            kpis.append((f'{m["ad_overlap_with_reference_subtitles_s"]:.1f} s', "與參考字幕重疊秒數"))
        kpis += [(f'{m["ad_overlap_with_detected_dialogue_s"]:.1f} s', "壓到偵測語音秒數"),
                 (f'{m["seconds_per_content_minute"]:.0f} s', "每分鐘影片處理秒數"),
                 (f'{m["shots"]}', "分析鏡頭數")]
        if inj and "hard" in inj:
            kpis.append((f'{inj["easy"]["caught"]}/{inj["easy"]["planted"]} · {inj["hard"]["caught"]}/{inj["hard"]["planted"]}', "植入錯誤攔截（明顯 · 隱蔽）"))
        elif inj:
            kpis.append((f'{inj["caught"]}/{inj["planted"]}', "植入錯誤攔截數"))
    else:
        kpis = [(f'{m["fit_after_loop"]}/{m["lines"]}', "lines fit their silence"),
                (f'{m["first_try_fit"]}/{m["lines"]}', "fit on the first draft")]
        if "ad_overlap_with_reference_subtitles_s" in m:
            kpis.append((f'{m["ad_overlap_with_reference_subtitles_s"]:.1f} s', "AD over official subtitle cues"))
        kpis += [(f'{m["ad_overlap_with_detected_dialogue_s"]:.1f} s', "AD over detected speech"),
                 (f'{m["seconds_per_content_minute"]:.0f} s', "processing per content minute"),
                 (f'{m["shots"]}', "shots analysed")]
        if inj and "hard" in inj:
            kpis.append((f'{inj["easy"]["caught"]}/{inj["easy"]["planted"]} · {inj["hard"]["caught"]}/{inj["hard"]["planted"]}', "planted errors flagged (easy · hard)"))
        elif inj:
            kpis.append((f'{inj["caught"]}/{inj["planted"]}', "planted false details flagged"))

    digest = hashlib.sha1(json.dumps([(r["id"], r["start"], r["text"]) for r in doc["lines"]]).encode()).hexdigest()[:12]
    run_id = html.escape(f'{doc["source"]["file"]}:{doc["source"]["start"]:.0f}-{doc["source"]["end"]:.0f}:{digest}')
    title = "GapCaster 口述影像審核頁" if zh else "GapCaster review"
    skip_txt = "跳至旁白審核列表" if zh else "Skip to draft lines"
    sub_txt = (f'{html.escape(doc["source"]["file"])} · {doc["source"]["start"]:.0f}–{doc["source"]["end"]:.0f} 秒 · 共 {m["lines"]} 句 AI 口述初稿待人工審核'
               if zh else f'{html.escape(doc["source"]["file"])} · {doc["source"]["start"]:.0f}–{doc["source"]["end"]:.0f} s · {m["lines"]} draft lines awaiting describer approval')

    out = [f'<!doctype html><html lang="{html_lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head><body data-run="{run_id}">']
    out.append(f'<a class="skip" href="#lines">{skip_txt}</a><div id="sr-status" class="sr-only" role="status" aria-live="polite"></div><div class="wrap">')
    out.append(f'<header><div><h1>Gap<span>Caster</span> {"審核頁" if zh else "review"}</h1><div class="sub">{sub_txt}</div></div></header>')
    out.append('<main id="main">')
    if zh:
        out.append('<div class="bar2" role="region" aria-label="審核統計與匯出"><span>審核進度：</span> <b id="n-approved">0</b> 已核准 · <b id="n-edited">0</b> 已修改 · <b id="n-rejected">0</b> 已剔除 · <b id="n-pending">0</b> 待審核 <span style="flex:1"></span>'
                   '<button class="primary" id="dl-json" type="button">下載 approved.json</button><button id="dl-vtt" type="button">下載核准版 .vtt</button></div>')
    else:
        out.append('<div class="bar2" role="region" aria-label="Review summary and export"><span>Describer review:</span> <b id="n-approved">0</b> approved · <b id="n-edited">0</b> edited · <b id="n-rejected">0</b> rejected · <b id="n-pending">0</b> pending <span style="flex:1"></span>'
                   '<button class="primary" id="dl-json" type="button">Download approved.json</button><button id="dl-vtt" type="button">Download approved .vtt</button></div>')
    out.append('<div class="kpis" role="region" aria-label="' + ("實測指標" if zh else "Run metrics") + '">' + "".join(f'<div class="kpi"><b>{a}</b><small>{b}</small></div>' for a, b in kpis) + '</div>')
    leg = ('<span><i style="background:var(--dlg)"></i>對白 (dialogue)</span><span><i style="background:var(--gap)"></i>空檔 (silence)</span><span><i style="background:var(--ad)"></i>口述影像 (AD)</span>'
           if zh else '<span><i style="background:var(--dlg)"></i>dialogue</span><span><i style="background:var(--gap)"></i>silence</span><span><i style="background:var(--ad)"></i>audio description</span>')
    out.append(f'<div class="tl">{timeline_svg(doc, zh)}<div class="legend">{leg}</div></div>')
    if (run / "clip_with_ad.mp4").exists():
        poster = run / "poster.jpg"
        if not poster.exists():
            from . import media
            media.frame(run / "clip_with_ad.mp4", m["clip_seconds"] * 0.57, poster, width=1280)
        v_lbl = "預覽混入合成口述初稿之影片" if zh else "Preview clip with draft audio description"
        out.append(f'<video controls preload="none" poster="poster.jpg" src="clip_with_ad.mp4" aria-label="{v_lbl}"></video>')
    out.append('<section id="lines" class="lines-list" aria-label="' + ("口述旁白草稿列表" if zh else "Draft audio description lines") + '">')
    from .export import ts as _ts
    for r in doc["lines"]:
        sh = shots.get(r["shots"][0]) if r["shots"] else None
        img = (_img64(run / sh["frames"][0]) if sh and sh.get("frames") else "") or old_imgs.get(r["id"], "")
        key_fact = str((sh.get("facts") or {}).get("key", ""))[:120] if sh else ""
        alt_txt = (f'{r["id"]} 於 {r["start"]:.1f} 秒之關鍵畫面' + (f'（{key_fact}）' if key_fact else '')
                   if zh else f'Keyframe for {r["id"]} at {r["start"]:.1f}s' + (f': {key_fact}' if key_fact else ''))
        fit_pct = min(100, 100 * (r["duration"] or 0) / max(0.01, r["avail"]))
        atts = "".join(
            f'<div class="{"" if a["fit"] else "x"}">{html.escape(a["text"])} <span class="t">— {html.escape(a["reason"])}</span></div>'
            for a in r["attempts"][:-1]) if len(r["attempts"]) > 1 else ""
        if zh:
            chips = {"fit": '<span class="chip ok">✓ 符合空檔</span>', "style": '<span class="chip warn">⚠ 風格把關攔下</span>'}.get(r["status"], '<span class="chip warn">⚠ 超出空檔</span>')
        else:
            chips = {"fit": '<span class="chip ok">✓ fits</span>', "style": '<span class="chip warn">⚠ held by style gate</span>'}.get(r["status"], '<span class="chip warn">⚠ does not fit</span>')
        chips += "".join(f'<span class="chip warn">⚠ {html.escape(f)}</span>' for f in r["flags"])
        facts = "<br>".join(f'{i}: {html.escape(str((shots[i].get("facts") or {}).get("key", "")))}' for i in r["shots"] if i in shots)
        a_lbl = f'試聽 {r["id"]} 語音（{r["start"]:.1f}秒）' if zh else f'Play {r["id"]} narration audio ({r["start"]:.1f}s)'
        audio = f'<audio controls preload="none" src="{html.escape(r["audio"])}" aria-label="{html.escape(a_lbl)}"></audio>' if r.get("audio") else ""
        a_ts, b_ts = _ts(r["start"], "."), _ts(r["start"] + (r["duration"] or 0), ".")
        fit_str = (f'語音 {(r["duration"] or 0):.1f} 秒 ／ 空檔 {r["avail"]:.1f} 秒' + (f' · {r["speed"]}×' if r.get("speed") and r["speed"] != 1.0 else '')
                   if zh else f'{(r["duration"] or 0):.1f} s of {r["avail"]:.1f} s silence' + (f' · {r["speed"]}×' if r.get("speed") and r["speed"] != 1.0 else ''))
        atts_lbl = "先前草稿" if zh else "Earlier drafts"
        ev_lbl = "畫面事實依據（英文）" if zh else "Evidence"
        facts_attr = ' lang="en"' if zh else ""
        btn_ok = f'<button class="ok" type="button" data-act="approve" aria-pressed="false" aria-label="{"核准 " if zh else "Approve "}{r["id"]}">{"核准" if zh else "Approve"}</button>'
        btn_ed = f'<button type="button" data-act="edit" aria-label="{"修改 " if zh else "Edit "}{r["id"]}">{"修改" if zh else "Edit"}</button>'
        btn_no = f'<button class="no" type="button" data-act="reject" aria-pressed="false" aria-label="{"剔除 " if zh else "Reject "}{r["id"]}">{"剔除" if zh else "Reject"}</button>'
        out.append(f'''<article class="line" aria-labelledby="hd-{r["id"]}" data-id="{r["id"]}" data-orig="{html.escape(r["text"])}" data-a="{a_ts}" data-b="{b_ts}"><div>{f'<img alt="{html.escape(alt_txt)}" src="{img}">' if img else ''}<h2 class="t-hd" id="hd-{r["id"]}">{r["id"]} · {r["start"]:.1f}s</h2><div class="state">{"待審核" if zh else "pending"}</div></div>
<div><div class="txt">{html.escape(r["text"])}</div>{f'<div class="att"><b>{atts_lbl}</b>{atts}</div>' if atts else ''}<div class="facts">{ev_lbl} · <span{facts_attr}>{facts}</span></div></div>
<div><div class="fit">{fit_str}</div><div class="bar" role="presentation"><i style="width:{fit_pct:.0f}%"></i></div>{chips}{audio}<div class="acts" role="group" aria-label="{r["id"]} {"審核操作" if zh else "review actions"}">{btn_ok}{btn_ed}{btn_no}</div></div></article>''')
    out.append('</section></main>')
    foot_txt = ("GapCaster 本機口述影像草稿審核頁 · 鍵盤提示：點擊「修改」後可按 Ctrl+Enter 儲存、Escape 取消；未經核准之句子不會匯出。"
                if zh else "GapCaster local review page · Tip: while editing a line, press Ctrl+Enter to save or Escape to cancel; unapproved lines are never exported.")
    out.append(f'<footer><div>{foot_txt}</div></footer></div><script>{JS}</script></body></html>')
    p = run / "review.html"
    p.write_text("\n".join(out), encoding="utf-8")
    return str(p)
