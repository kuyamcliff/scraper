"""
Nyaa Scraper Telegram Bot
Search nyaa + download via Real-Debrid (HTTPS/port 443) or qbittorrent.

Commands:
  /search <title>       — search nyaa, shows top 8 results
  /dl <n>               — download result N via Real-Debrid (fast, works here)
  /dlqb <n>             — download result N via qbittorrent (needs open ports)
  /magnet <uri>         — add magnet to Real-Debrid
  /downloads            — show active RD downloads + progress
  /files                — list downloaded files
  /rdlist               — show Real-Debrid torrent queue
  /list                 — qbittorrent torrent list
  /status               — system stats
  /start                — help
"""

import asyncio
import os
import re
import time
import logging
import httpx
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from nyaa_scraper.nyaa import NyaaClient
from nyaa_scraper.parser import parse
from realdebrid import RealDebridClient, download_file, RealDebridError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── config ────────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ["TG_BOT_TOKEN"]
ALLOWED_IDS  = set(int(x) for x in os.environ.get("TG_ALLOWED_IDS", "").split(",") if x.strip())
RD_KEY       = os.environ.get("RD_API_KEY", "")
QBIT_URL     = os.environ.get("QBIT_URL", "http://localhost:8080")
QBIT_USER    = os.environ.get("QBIT_USER", "admin")
QBIT_PASS    = os.environ.get("QBIT_PASS", "adminadmin")
SAVE_PATH    = os.environ.get("SAVE_PATH", "/home/user/downloads")

# ── clients ───────────────────────────────────────────────────────────────────
nyaa = NyaaClient()
rd   = RealDebridClient(RD_KEY) if RD_KEY else None

# ── state ─────────────────────────────────────────────────────────────────────
_search_cache: dict[int, list] = {}
_active_downloads: dict[str, dict] = {}  # uid+n → {name, progress, total, done}

# ── qbit helper ───────────────────────────────────────────────────────────────
class QbitClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15)
        self.sid = None

    async def login(self):
        r = await self.client.post(f"{QBIT_URL}/api/v2/auth/login",
            data={"username": QBIT_USER, "password": QBIT_PASS})
        self.sid = r.cookies.get("SID")

    def _h(self): return {"Cookie": f"SID={self.sid}"} if self.sid else {}

    async def torrents(self):
        if not self.sid: await self.login()
        r = await self.client.get(f"{QBIT_URL}/api/v2/torrents/info", headers=self._h())
        return r.json()

    async def add_torrent(self, content: bytes, fname: str = "t.torrent"):
        if not self.sid: await self.login()
        r = await self.client.post(f"{QBIT_URL}/api/v2/torrents/add",
            headers=self._h(),
            files={"torrents": (fname, content, "application/x-bittorrent")},
            data={"savepath": SAVE_PATH})
        return r.text

    async def close(self): await self.client.aclose()

qbit = QbitClient()

# ── guards & helpers ──────────────────────────────────────────────────────────
def guard(fn):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if ALLOWED_IDS and uid not in ALLOWED_IDS:
            await update.message.reply_text("⛔ not allowed")
            return
        return await fn(update, ctx)
    return wrapper

def fmt_size(b: int) -> str:
    for u, d in [("GB", 1<<30), ("MB", 1<<20), ("KB", 1<<10)]:
        if b >= d: return f"{b/d:.1f} {u}"
    return f"{b} B"

def fmt_speed(bps: float) -> str:
    return fmt_size(int(bps)) + "/s"

def pct(done, total): return f"{done/total*100:.1f}%" if total else "?"

def state_emoji(s: str) -> str:
    return {"downloading":"⬇️","uploading":"⬆️","stalledDL":"⏸","stalledUP":"⏸",
            "pausedDL":"⏸","pausedUP":"⏸","checkingDL":"🔍","metaDL":"🔎",
            "error":"❌","missingFiles":"⚠️"}.get(s,"🔄")

# ── commands ──────────────────────────────────────────────────────────────────

@guard
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rd_status = "✅ Real-Debrid connected" if RD_KEY else "⚠️ Real-Debrid not configured (set RD_API_KEY)"
    txt = (
        f"🎌 *Nyaa Scraper Bot*\n{rd_status}\n\n"
        "*Search & Download (Real-Debrid — works here):*\n"
        "/search `<title>` — search nyaa\n"
        "/dl `<n>` — download via Real-Debrid → direct HTTPS\n"
        "/magnet `<uri>` — send magnet to Real-Debrid\n"
        "/downloads — active RD downloads\n"
        "/rdlist — RD torrent queue\n\n"
        "*Files:*\n"
        "/files — list downloaded files\n\n"
        "*qBittorrent (needs open ports):*\n"
        "/dlqb `<n>` — add to qBittorrent\n"
        "/list — qbit torrent list\n"
        "/status — system stats"
    )
    await update.message.reply_text(txt, parse_mode="Markdown")

@guard
async def cmd_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("usage: /search <title>")
        return
    query = " ".join(ctx.args)
    msg = await update.message.reply_text(f"🔍 searching *{query}*…", parse_mode="Markdown")
    try:
        results = await nyaa.search(query, page=1)
        good = [r for r in results if len(r.title) > 4][:8]
        if not good:
            await msg.edit_text("no results")
            return
        uid = update.effective_user.id
        _search_cache[uid] = good
        lines = []
        for i, r in enumerate(good, 1):
            p = parse(r.title)
            ep = f"S{p.season}E{p.episode}" if p.episode else "—"
            lines.append(
                f"`{i}.` [{r.title[:55]}]({r.link})\n"
                f"   {ep}  {p.resolution or '?'}  🌱{r.seeders}  {r.size_human}"
            )
        txt = f"*Results for* `{query}`\n\n" + "\n\n".join(lines) + "\n\n_/dl <n> → Real-Debrid_"
        await msg.edit_text(txt, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ {e}")

@guard
async def cmd_dl(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Download via Real-Debrid — full HTTPS, works in this container."""
    if not rd:
        await update.message.reply_text("⚠️ RD_API_KEY not set. Get one at real-debrid.com")
        return
    uid = update.effective_user.id
    cache = _search_cache.get(uid, [])
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("usage: /dl <number>")
        return
    n = int(ctx.args[0])
    if n < 1 or n > len(cache):
        await update.message.reply_text(f"pick 1–{len(cache)}, run /search first")
        return
    entry = cache[n - 1]
    msg = await update.message.reply_text(
        f"📡 *Sending to Real-Debrid…*\n`{entry.title[:60]}`",
        parse_mode="Markdown")

    async def _run():
        try:
            # get the magnet
            magnet = entry.magnet
            if not magnet:
                # fall back to .torrent
                resp = await nyaa.client.get(entry.torrent_url)
                links = await rd.resolve_torrent_file(
                    resp.content,
                    on_status=lambda s, _: asyncio.ensure_future(
                        msg.edit_text(f"📡 RD status: `{s}`\n`{entry.title[:55]}`",
                                      parse_mode="Markdown")
                    )
                )
            else:
                links = await rd.resolve_magnet(
                    magnet,
                    on_status=lambda s, _: asyncio.ensure_future(
                        msg.edit_text(f"📡 RD status: `{s}`\n`{entry.title[:55]}`",
                                      parse_mode="Markdown")
                    )
                )

            if not links:
                await msg.edit_text("❌ RD returned no links")
                return

            await msg.edit_text(
                f"⬇️ *Downloading {len(links)} file(s)…*\n`{entry.title[:55]}`",
                parse_mode="Markdown")

            for i, lnk in enumerate(links, 1):
                fname = lnk["filename"] or f"file_{i}"
                dest  = Path(SAVE_PATH) / fname
                size  = lnk["filesize"]
                dl_key = f"{uid}_{fname}"
                _active_downloads[dl_key] = {"name": fname, "downloaded": 0, "total": size, "done": False}

                last_edit = [0.0]

                def on_progress(downloaded, total, _fname=fname, _key=dl_key):
                    _active_downloads[_key]["downloaded"] = downloaded
                    _active_downloads[_key]["total"] = total
                    now = time.monotonic()
                    if now - last_edit[0] > 4:
                        last_edit[0] = now
                        spd = downloaded / max(now - start_t, 0.1)
                        asyncio.ensure_future(msg.edit_text(
                            f"⬇️ *{_fname[:45]}*\n{pct(downloaded,total)}  {fmt_size(downloaded)}/{fmt_size(total)}  {fmt_speed(spd)}",
                            parse_mode="Markdown"))

                start_t = time.monotonic()
                await download_file(lnk["download_url"], dest, on_progress=on_progress)
                _active_downloads[dl_key]["done"] = True
                elapsed = time.monotonic() - start_t
                avg_spd = size / max(elapsed, 0.1)
                await msg.edit_text(
                    f"✅ *Done!*\n`{fname}`\n{fmt_size(size)}  avg {fmt_speed(avg_spd)}\nSaved → `{SAVE_PATH}`",
                    parse_mode="Markdown")

        except RealDebridError as e:
            await msg.edit_text(f"❌ Real-Debrid error: {e}")
        except Exception as e:
            await msg.edit_text(f"❌ {e}")

    asyncio.ensure_future(_run())

@guard
async def cmd_magnet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Send a raw magnet to Real-Debrid and download."""
    if not rd:
        await update.message.reply_text("⚠️ RD_API_KEY not set")
        return
    if not ctx.args:
        await update.message.reply_text("usage: /magnet <magnet_uri>")
        return
    magnet = ctx.args[0]
    if not magnet.startswith("magnet:"):
        await update.message.reply_text("doesn't look like a magnet link")
        return
    msg = await update.message.reply_text("📡 sending to Real-Debrid…")
    try:
        tid = await rd.add_magnet(magnet)
        await rd.select_files(tid, "all")
        await msg.edit_text(f"✅ Added to RD queue — use /rdlist to check, /dl once ready")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")

@guard
async def cmd_downloads(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show in-progress direct downloads."""
    active = {k: v for k, v in _active_downloads.items() if not v["done"]}
    done   = {k: v for k, v in _active_downloads.items() if v["done"]}
    if not active and not done:
        await update.message.reply_text("no downloads yet — use /dl <n>")
        return
    lines = []
    for v in list(active.values())[:5]:
        lines.append(f"⬇️ `{v['name'][:45]}`\n   {pct(v['downloaded'], v['total'])}  {fmt_size(v['downloaded'])}/{fmt_size(v['total'])}")
    for v in list(done.values())[-5:]:
        lines.append(f"✅ `{v['name'][:45]}`  {fmt_size(v['total'])}")
    await update.message.reply_text("\n\n".join(lines) or "nothing", parse_mode="Markdown")

@guard
async def cmd_rdlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """List Real-Debrid torrent queue."""
    if not rd:
        await update.message.reply_text("⚠️ RD_API_KEY not set")
        return
    try:
        torrents = await rd.list_torrents()
        if not torrents:
            await update.message.reply_text("RD queue is empty")
            return
        lines = []
        for t in torrents[:8]:
            status = t.get("status", "?")
            prog   = t.get("progress", 0)
            name   = t.get("filename", t.get("hash", "?"))[:50]
            size   = fmt_size(t.get("bytes", 0))
            emoji  = {"downloaded":"✅","downloading":"⬇️","queued":"🕒","error":"❌"}.get(status,"🔄")
            lines.append(f"{emoji} `{name}`\n   {status}  {prog}%  {size}")
        await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

@guard
async def cmd_files(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """List files in downloads folder."""
    p = Path(SAVE_PATH)
    if not p.exists():
        await update.message.reply_text("downloads folder empty")
        return
    files = sorted(p.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)[:10]
    if not files:
        await update.message.reply_text("no files yet")
        return
    lines = [f"`{f.name[:50]}`  {fmt_size(f.stat().st_size)}" for f in files]
    await update.message.reply_text("📁 *Downloads:*\n\n" + "\n".join(lines), parse_mode="Markdown")

@guard
async def cmd_dlqb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Add to qBittorrent (requires open torrent ports)."""
    uid = update.effective_user.id
    cache = _search_cache.get(uid, [])
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("usage: /dlqb <number>")
        return
    n = int(ctx.args[0])
    if n < 1 or n > len(cache):
        await update.message.reply_text(f"pick 1–{len(cache)}")
        return
    entry = cache[n - 1]
    msg = await update.message.reply_text(f"⬇️ adding to qBittorrent…")
    try:
        resp = await nyaa.client.get(entry.torrent_url)
        result = await qbit.add_torrent(resp.content, f"{entry.id}.torrent")
        if "Ok" in result or result == "":
            await msg.edit_text(f"✅ added to qBit!\n*{entry.title}*\n⚠️ needs open ports to download", parse_mode="Markdown")
        else:
            await msg.edit_text(f"⚠️ qbit: {result}")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")

@guard
async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        torrents = await qbit.torrents()
        if not torrents:
            await update.message.reply_text("no qbit torrents")
            return
        lines = []
        for t in torrents[:8]:
            e = state_emoji(t["state"])
            lines.append(
                f"{e} `{t['name'][:45]}`\n"
                f"   {t['progress']*100:.1f}%  {fmt_size(t['size'])}  🌱{t['num_seeds']}"
            )
        await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

@guard
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lines = []
    # RD account
    if rd:
        try:
            user = await rd.user()
            exp  = user.get("expiration", "?")[:10]
            pts  = user.get("points", "?")
            lines.append(f"💳 *Real-Debrid*: {user.get('username')}  expires {exp}  pts {pts}")
        except Exception as e:
            lines.append(f"💳 RD error: {e}")
    else:
        lines.append("💳 Real-Debrid: not configured")

    # downloads folder
    p = Path(SAVE_PATH)
    if p.exists():
        files = list(p.iterdir())
        total = sum(f.stat().st_size for f in files if f.is_file())
        lines.append(f"📁 Downloads: {len(files)} files  {fmt_size(total)}")

    # active downloads
    active = sum(1 for v in _active_downloads.values() if not v["done"])
    lines.append(f"⬇️ Active downloads: {active}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ── main ──────────────────────────────────────────────────────────────────────
async def on_shutdown(app):
    await nyaa.close()
    if rd: await rd.close()
    await qbit.close()

def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_shutdown(on_shutdown)
        .build()
    )
    cmds = [
        ("start",     cmd_start),
        ("help",      cmd_start),
        ("search",    cmd_search),
        ("dl",        cmd_dl),
        ("dlqb",      cmd_dlqb),
        ("magnet",    cmd_magnet),
        ("downloads", cmd_downloads),
        ("rdlist",    cmd_rdlist),
        ("files",     cmd_files),
        ("list",      cmd_list),
        ("status",    cmd_status),
    ]
    for name, fn in cmds:
        app.add_handler(CommandHandler(name, fn))

    log.info("bot starting — polling telegram")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
