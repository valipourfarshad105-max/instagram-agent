"""داشبورد تأیید و کنترل ایجنت (FastAPI + HTML تک‌فایل، بدون وابستگی به CDN).

اجرا:  python -m agent.cli dashboard
"""
from __future__ import annotations

import base64
import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from .config import Cfg, env, load_config
from .notify import get_logger
from .pipeline import approve, produce, publish_post, reject
from .store import STATUSES, ScheduledPost, Store

log = get_logger("dashboard")

STATE_LABELS = {
    "draft": ("پیش‌نویس", "#64748b"),
    "generating": ("در حال ساخت", "#0ea5e9"),
    "pending": ("در انتظار تأیید", "#f59e0b"),
    "approved": ("تأییدشده (در صف)", "#8b5cf6"),
    "publishing": ("در حال انتشار", "#3b82f6"),
    "published": ("منتشرشده", "#22c55e"),
    "failed": ("خطا", "#ef4444"),
    "rejected": ("رد‌شده", "#94a3b8"),
}

HTML = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$TITLE · داشبورد ایجنت اینستاگرام</title>
<style>
  :root { --bg:#0b1020; --card:#131a30; --line:#26304d; --txt:#e8ecf7; --mut:#93a0c0;
          --acc:$ACCENT; --ok:#22c55e; --warn:#f59e0b; --bad:#ef4444; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font-family:Vazirmatn,"Segoe UI",Tahoma,system-ui,sans-serif; }
  header { padding:22px 26px; border-bottom:1px solid var(--line); display:flex;
           flex-wrap:wrap; gap:14px; align-items:center; justify-content:space-between;
           background:linear-gradient(120deg,#101736,#161f42); position:sticky; top:0; z-index:5; }
  h1 { margin:0; font-size:20px; }
  .sub { color:var(--mut); font-size:13px; margin-top:4px; }
  .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
  button { font-family:inherit; font-size:13px; padding:8px 14px; border-radius:10px;
           border:1px solid var(--line); background:#1b2444; color:var(--txt); cursor:pointer;
           transition:.15s; }
  button:hover { background:#243058; transform:translateY(-1px); }
  button.primary { background:var(--acc); border-color:var(--acc); color:#fff; font-weight:700; }
  button.ok { background:#14532d; border-color:#166534; }
  button.bad { background:#4c1d1d; border-color:#7f1d1d; }
  button:disabled { opacity:.5; cursor:not-allowed; transform:none; }
  input, textarea { font-family:inherit; background:#0e1428; color:var(--txt);
           border:1px solid var(--line); border-radius:10px; padding:9px 12px; font-size:13px; width:100%; }
  main { padding:22px; max-width:1150px; margin:0 auto; }
  .stats { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:18px; }
  .stat { background:var(--card); border:1px solid var(--line); border-radius:14px;
          padding:12px 16px; min-width:120px; }
  .stat b { display:block; font-size:22px; }
  .stat span { color:var(--mut); font-size:12px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:16px;
          padding:16px; margin-bottom:14px; display:grid; grid-template-columns:150px 1fr; gap:16px; }
  @media (max-width:720px){ .card { grid-template-columns:1fr; } }
  .thumb { width:100%; aspect-ratio:9/16; border-radius:12px; object-fit:cover; background:#0a0f1e; }
  .badge { display:inline-block; font-size:11px; padding:3px 9px; border-radius:99px;
           color:#fff; font-weight:700; }
  .meta { color:var(--mut); font-size:12px; margin:6px 0; display:flex; gap:12px; flex-wrap:wrap; }
  .cap { font-size:13.5px; line-height:1.9; white-space:pre-wrap; background:#0e1428;
         border:1px solid var(--line); border-radius:12px; padding:10px 12px; margin:8px 0; }
  .scenes { margin:8px 0; font-size:12.5px; color:var(--mut); line-height:1.9; }
  .scenes b { color:var(--txt); }
  .actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
  .empty { text-align:center; color:var(--mut); padding:60px 20px; }
  video { width:100%; border-radius:10px; background:#000; max-height:260px; }
  .toast { position:fixed; bottom:18px; left:18px; background:#1b2444; border:1px solid var(--line);
           padding:12px 16px; border-radius:12px; font-size:13px; opacity:0; transition:.3s;
           pointer-events:none; max-width:340px; }
  .toast.show { opacity:1; }
  .spinner { display:inline-block; width:12px; height:12px; border:2px solid #ffffff55;
             border-top-color:#fff; border-radius:50%; animation:spin .8s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
</style>
</head>
<body>
<header>
  <div>
    <h1>$TITLE</h1>
    <div class="sub">داشبورد ایجنت اینستاگرام · حالت: $MODE · منطقهٔ زمانی: $TZ</div>
  </div>
  <div class="row">
    <input id="topic" placeholder="موضوع دلخواه (اختیاری)" style="width:230px">
    <button class="primary" onclick="generate()">✚ ساخت پست جدید</button>
    <button onclick="load()">↻ بازخوانی</button>
  </div>
</header>
<main>
  <div class="stats" id="stats"></div>
  <div id="posts"><div class="empty">در حال بارگذاری ...</div></div>
</main>
<div class="toast" id="toast"></div>
<script>
const LABELS = $LABELS;
let busy = false;

function toast(msg){ const t=document.getElementById('toast'); t.textContent=msg;
  t.classList.add('show'); clearTimeout(t._h); t._h=setTimeout(()=>t.classList.remove('show'), 4500); }

async function api(path, body){
  const res = await fetch(path, { method: body ? 'POST' : 'GET',
    headers: {'Content-Type':'application/json'}, body: body ? JSON.stringify(body) : undefined });
  if(!res.ok){ const txt = await res.text(); throw new Error(txt.slice(0,200)); }
  return res.headers.get('content-type')?.includes('json') ? res.json() : res.text();
}

function esc(s){ return (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

async function load(){
  try {
    const data = await api('/api/state');
    document.getElementById('stats').innerHTML = Object.entries(data.stats)
      .filter(([k,v]) => v > 0)
      .map(([k,v]) => `<div class="stat"><b>${v}</b><span>${(LABELS[k]||[k])[0]}</span></div>`).join('')
      + `<div class="stat"><b>${data.schedule}</b><span>ساعت‌های اجرا</span></div>`;
    const posts = data.posts;
    if(!posts.length){ document.getElementById('posts').innerHTML =
      '<div class="empty">هنوز پستی ساخته نشده. روی «ساخت پست جدید» بزنید یا اسلات زمان‌بندی را اجرا کنید.</div>'; return; }
    document.getElementById('posts').innerHTML = posts.map(render).join('');
  } catch(e){ toast('خطا در بارگذاری: ' + e.message); }
}

function render(p){
  const [label, color] = LABELS[p.status] || ['نامعلوم','#64748b'];
  const canApprove = ['pending','draft','failed'].includes(p.status);
  const canPublish = ['pending','approved','failed'].includes(p.status) && p.has_video;
  const scenes = (p.scenes||[]).map(s => `• ${esc(s.text)} <span style="opacity:.7">— ${esc(s.narration||'')}</span>`).join('<br>');
  const video = p.has_video
    ? `<video controls preload="metadata" poster="${p.cover_url||''}"><source src="${p.video_url_http||''}" type="video/mp4"></video>`
    : `<img class="thumb" src="${p.cover_url||''}" alt="">`;
  return `<div class="card" id="post-${p.id}">
    <div>${video}</div>
    <div>
      <div class="row" style="justify-content:space-between">
        <div><span class="badge" style="background:${color}">${label}</span>
          <b style="margin-inline-start:8px">${esc(p.title||p.topic)}</b></div>
        <div class="meta"><span>${esc(p.id)}</span><span>${esc((p.created_at||'').slice(0,16).replace('T',' '))}</span>
        ${p.provider?`<span>${esc(p.provider)}</span>`:''}${p.duration?`<span>${p.duration} ثانیه</span>`:''}</div>
      </div>
      <div class="cap" id="cap-${p.id}" contenteditable="true">${esc(p.caption)}</div>
      <div class="cap" id="tags-${p.id}" contenteditable="true" style="color:#9ecbff">${esc((p.hashtags||[]).join(' '))}</div>
      ${scenes ? `<details><summary class="meta" style="cursor:pointer">سناریوی صحنه‌ها</summary><div class="scenes">${scenes}</div></details>` : ''}
      ${p.error?`<div class="meta" style="color:#ef4444">⚠️ ${esc(p.error)}</div>`:''}
      <div class="actions">
        ${canApprove?`<button class="ok" onclick="act('${p.id}','approve')">✅ تأیید</button>`:''}
        ${['pending','draft'].includes(p.status)?`<button class="bad" onclick="act('${p.id}','reject')">✖ رد</button>`:''}
        ${canPublish?`<button class="primary" onclick="act('${p.id}','publish')">🚀 انتشار فوری</button>`:''}
        <button onclick="save('${p.id}')">💾 ذخیرهٔ متن</button>
        <button onclick="act('${p.id}','rebuild')">🎬 ساخت مجدد ویدیو</button>
        <button class="bad" onclick="act('${p.id}','delete')">🗑 حذف</button>
      </div>
    </div></div>`;
}

async function act(id, action){
  if (action === 'delete' && !confirm('این پست حذف شود؟')) return;
  if (action === 'publish' && !confirm('الان در اینستاگرام منتشر شود؟')) return;
  try { toast('در حال انجام ...'); await api(`/api/post/${id}/${action}`, {});
        toast('انجام شد.'); load(); }
  catch(e){ toast('خطا: ' + e.message); }
}

async function save(id){
  const caption = document.getElementById('cap-'+id).innerText.trim();
  const hashtags = document.getElementById('tags-'+id).innerText.trim().split(/\\s+/).filter(Boolean);
  try { await api(`/api/post/${id}/update`, { caption, hashtags }); toast('متن ذخیره شد.'); }
  catch(e){ toast('خطا: ' + e.message); }
}

async function generate(){
  const topic = document.getElementById('topic').value.trim();
  try { toast('در حال ساخت محتوا (ممکن است چند دقیقه طول بکشد) ...');
        await api('/api/generate', { topic: topic || null }); toast('پیش‌نویس ساخته شد.'); load(); }
  catch(e){ toast('خطا: ' + e.message); }
}

load();
setInterval(load, 12000);
</script>
</body>
</html>
"""


def to_api(post: ScheduledPost, request: Request | None = None) -> dict:
    base = str(request.base_url).rstrip("/") if request else ""
    video_http = ""
    if post.video_path and Path(post.video_path).exists():
        video_http = f"{base}/media/{post.id}/reel.mp4"
    cover = f"{base}/media/{post.id}/cover.jpg" if post.cover_path else ""
    duration = (post.meta or {}).get("scene_durations")
    return {
        "id": post.id,
        "status": post.status,
        "topic": post.topic,
        "title": post.title,
        "caption": post.caption,
        "hashtags": post.hashtags,
        "scenes": [{"text": s.text, "narration": s.narration} for s in post.scenes],
        "created_at": post.created_at,
        "provider": (post.meta or {}).get("provider", ""),
        "duration": round(sum(duration), 1) if duration else None,
        "error": post.error,
        "ig_media_id": post.ig_media_id,
        "has_video": bool(post.video_path and Path(post.video_path).exists()),
        "video_url_http": video_http,
        "cover_url": cover,
    }


def create_app(cfg: Cfg | None = None, store: Store | None = None) -> FastAPI:
    cfg = cfg or load_config()
    store = store or Store(cfg)
    app = FastAPI(title="Instagram Agent Dashboard", docs_url=None, redoc_url=None)

    def _auth(request: Request) -> None:
        password = env("DASHBOARD_PASSWORD")
        if not password:
            return
        header = request.headers.get("authorization", "")
        if header.startswith("Basic "):
            try:
                decoded = base64.b64decode(header[6:]).decode("utf-8", "ignore")
                if decoded.split(":", 1)[-1] == password:
                    return
            except Exception:  # noqa: BLE001
                pass
        raise HTTPException(status_code=401, detail="Unauthorized",
                            headers={"WWW-Authenticate": 'Basic realm="agent"'})

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        _auth(request)
        html = (HTML
                .replace("$TITLE", cfg.brand.name)
                .replace("$MODE", "خودکار" if cfg.publish.mode == "auto" else "تأیید دستی")
                .replace("$TZ", cfg.publish.timezone)
                .replace("$ACCENT", cfg.video.color_primary)
                .replace("$LABELS", str({k: list(v) for k, v in STATE_LABELS.items()}).replace("'", '"')))
        return HTMLResponse(html)

    @app.get("/api/state")
    def state(request: Request):
        _auth(request)
        stats = store.stats()
        posts = [to_api(p, request) for p in store.list(limit=60)]
        return JSONResponse({
            "stats": stats,
            "posts": posts,
            "schedule": "، ".join(cfg.publish.schedule),
            "mode": cfg.publish.mode,
        })

    @app.post("/api/post/{post_id}/approve")
    def api_approve(post_id: str, request: Request):
        _auth(request)
        approve(cfg, store, post_id)
        return {"ok": True, "post_id": post_id, "status": "approved"}

    @app.post("/api/post/{post_id}/reject")
    def api_reject(post_id: str, request: Request):
        _auth(request)
        reject(cfg, store, post_id)
        return {"ok": True}

    @app.post("/api/post/{post_id}/delete")
    def api_delete(post_id: str, request: Request):
        _auth(request)
        import shutil

        post = store.get(post_id)
        if not post:
            raise HTTPException(404, "پست پیدا نشد")
        work_dir = cfg.get_path("out") / post_id
        shutil.rmtree(work_dir, ignore_errors=True)
        store.update(post_id, status="rejected")
        return {"ok": True}

    @app.post("/api/post/{post_id}/update")
    def api_update(post_id: str, payload: dict, request: Request):
        _auth(request)
        store.update(post_id, caption=(payload.get("caption") or "").strip(),
                     hashtags=payload.get("hashtags") or [])
        return {"ok": True}

    @app.post("/api/post/{post_id}/publish")
    def api_publish(post_id: str, request: Request, background: BackgroundTasks):
        _auth(request)
        post = store.get(post_id)
        if not post:
            raise HTTPException(404, "پست پیدا نشد")
        if post.status == "pending":
            store.update(post_id, status="approved")

        def _job():
            try:
                publish_post(cfg, store, post_id)
            except Exception as exc:  # noqa: BLE001
                log.error("انتشار از داشبورد ناموفق بود: %s", exc)

        background.add_task(_job)
        return {"ok": True, "message": "انتشار در پس‌زمینه شروع شد"}

    @app.post("/api/post/{post_id}/rebuild")
    def api_rebuild(post_id: str, request: Request, background: BackgroundTasks):
        _auth(request)
        post = store.get(post_id)
        if not post:
            raise HTTPException(404, "پست پیدا نشد")

        def _job():
            from .video.reels import build_reel

            try:
                work = cfg.get_path("out") / post_id
                video = build_reel(store.get(post_id), cfg, work)
                store.update(post_id, video_path=str(video), cover_path=post.cover_path,
                             status="pending" if cfg.publish.mode == "approve" else "approved",
                             error="")
            except Exception as exc:  # noqa: BLE001
                log.error("ساخت مجدد ویدیو ناموفق بود: %s", exc)
                store.update(post_id, status="failed", error=str(exc)[:500])

        background.add_task(_job)
        return {"ok": True, "message": "ساخت مجدد ویدیو شروع شد"}

    @app.post("/api/generate")
    def api_generate(payload: dict, request: Request, background: BackgroundTasks):
        _auth(request)
        topic = (payload or {}).get("topic") or None

        def _job():
            try:
                produce(cfg, store, topic=topic)
            except Exception as exc:  # noqa: BLE001
                log.error("تولید از داشبورد ناموفق بود: %s", exc)

        background.add_task(_job)
        return {"ok": True, "message": "ساخت پست جدید شروع شد"}

    @app.get("/media/{post_id}/reel.mp4")
    def media_video(post_id: str, request: Request):
        _auth(request)
        post = store.get(post_id)
        path = Path(post.video_path) if post and post.video_path else None
        if not path or not path.exists():
            raise HTTPException(404, "ویدیو پیدا نشد")
        return FileResponse(path, media_type="video/mp4", filename=f"{post_id}.mp4")

    @app.get("/media/{post_id}/cover.jpg")
    def media_cover(post_id: str, request: Request):
        _auth(request)
        post = store.get(post_id)
        path = Path(post.cover_path) if post and post.cover_path else None
        if not path or not path.exists():
            raise HTTPException(404, "کاور پیدا نشد")
        return FileResponse(path, media_type="image/jpeg")

    @app.get("/health")
    def health():
        return {"ok": True, "posts": store.stats()}

    return app


def run_dashboard(cfg: Cfg | None = None) -> None:
    import uvicorn

    cfg = cfg or load_config()
    host = env("DASHBOARD_HOST", "0.0.0.0")
    port = int(env("DASHBOARD_PORT", "8000") or 8000)
    log.info("داشبورد روی http://%s:%s بالا می‌آید", host, port)
    uvicorn.run(create_app(cfg), host=host, port=port, log_level="info")


app = None  # برای uvicorn در حالت ماژولی ساخته می‌شود


def get_app():
    """برای uvicorn: agent.dashboard:get_app --factory"""
    return create_app()


if os.getenv("AGENT_DASHBOARD_AUTOSTART"):  # pragma: no cover
    app = create_app()
