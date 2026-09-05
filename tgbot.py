"""
Nyaa Scraper Telegram Bot
Control qbittorrent + nyaa search straight from Telegram.

Commands:
  /search <title>       — search nyaa, shows top 5 results
  /dl <number>          — download result N from last search
  /magnet <magnet_uri>  — add a magnet link directly
  /list                 — show active torrents + progress
  /pause <hash>         — pause a torrent
  /resume <hash>        — resume a torrent
  /delete <hash>        — delete torrent (keeps files)
  /nuke <hash>          — delete torrent + files
  /status               — qbit stats summary
  /start                — show help
"""

import asyncio
import os
import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
)
from nyaa_scraper.nyaa import NyaaClient
from nyaa_scraper.parser import parse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── config ────────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ["TG_BOT_TOKEN"]
ALLOWED_IDS = set(int(x) for x in os.environ.get("TG_ALLOWED_IDS", "").split(",") if x.strip())
QBIT_URL    = os.environ.get("QBIT_URL", "http://localhost:8080")
QBIT_USER   = os.environ.get("QBIT_USER", "admin")
QBIT_PASS   = os.environ.get("QBIT_PASS", "adminadmin")
SAVE_PATH   = os.environ.get("SAVE_PATH", "/home/user/downloads")

# ── qbittorrent client ────────────────────────────────────────────────────────
class QbitClient:
    def __init__(self):
        self.base = QBIT_URL.rstrip("/")
        self.client = httpx.AsyncClient(timeout=15)
        self.sid = None

    async def login(self):
        r = await self.client.post(f"{self.base}/api/v2/auth/login",
            data={"username": QBIT_USER, "password": QBIT_PASS})
        self.sid = r.cookies.get("SID")
        return self.sid

    def _headers(self):
        return {"Cookie": f"SID={self.sid}"} if self.sid else {}

    async def _get(self, path, **kwargs):
        if not self.sid: await self.login()
        return await self.client.get(f"{self.base}{path}", headers=self._headers(), **kwargs)

    async def _post(self, path, **kwargs):
        if not self.sid: await self.login()
        return await self.client.post(f"{self.base}{path}", headers=self._headers(), **kwargs)

    async def torrents(self):
        r = await self._get("/api/v2/torrents/info")
        return r.json()

    async def add_torrent_file(self, content: bytes, filename: str = "torrent.torrent"):
        r = await self._post("/api/v2/torrents/add",
            files={"torrents": (filename, content, "application/x-bittorrent")},
            data={"savepath": SAVE_PATH})
        return r.text

    async def add_magnet(self, magnet: str):
        r = await self._post("/api/v2/torrents/add",
            data={"urls": magnet, "savepath": SAVE_PATH})
        return r.text

    async def pause(self, hashes: str):
        await self._post("/api/v2/torrents/pause", data={"hashes": hashes})

    async def resume(self, hashes: str):
        await self._post("/api/v2/torrents/resume", data={"hashes": hashes})

    async def delete(self, hashes: str, delete_files: bool = False):
        await self._post("/api/v2/torrents/delete",
            data={"hashes": hashes, "deleteFiles": str(delete_files).lower()})

    async def main_data(self):
        r = await self._get("/api/v2/sync/maindata")
        return r.json()

    async def close(self):
        await self.client.aclose()

qbit = QbitClient()
nyaa = NyaaClient()

# per-user last search results cache
_search_cache: dict[int, list] = {}

# ── guards ────────────────────────────────────────────────────────────────────
def guard(fn):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if ALLOWED_IDS and uid not in ALLOWED_IDS:
            await update.message.reply_text("⛔ not allowed")
            return
        return await fn(update, ctx)
    return wrapper

# ── helpers ───────────────────────────────────────────────────────────────────
def fmt_size(b: int) -> str:
    for u, d in [("GB", 1<<30), ("MB", 1<<20), ("KB", 1<<10)]:
        if b >= d: return f"{b/d:.1f} {u}"
    return f"{b} B"

def fmt_speed(b: int) -> str:
    return fmt_size(b) + "/s"

def state_emoji(s: str) -> str:
    return {"downloading": "⬇️", "uploading": "⬆️", "stalledDL": "⏸", "stalledUP": "⏸",
            "pausedDL": "⏸", "pausedUP": "⏸", "checkingDL": "🔍", "metaDL": "🔎",
            "error": "❌", "missingFiles": "⚠️"}.get(s, "🔄")

def torrent_line(t: dict) -> str:
    emoji = state_emoji(t["state"])
    prog  = t["progress"] * 100
    name  = t["name"][:45]
    size  = fmt_size(t["size"])
    speed = fmt_speed(t["dlspeed"]) if t["dlspeed"] > 0 else ""
    eta   = f"  ETA {t['eta']//60}m" if t.get("eta", 0) > 0 and t["eta"] < 86400 else ""
    spd   = f"  {speed}" if speed else ""
    return f"{emoji} `{name}`\n   {prog:.1f}%  {size}{spd}{eta}\n   `{t['hash'][:12]}…`"

# ── commands ──────────────────────────────────────────────────────────────────
@guard
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = (
        "🎌 *Nyaa Scraper Bot*\n\n"
        "/search `<title>` — search nyaa\n"
        "/dl `<n>` — download result n from last search\n"
        "/magnet `<uri>` — add magnet directly\n"
        "/list — active torrents\n"
        "/pause `<hash>` — pause\n"
        "/resume `<hash>` — resume\n"
        "/delete `<hash>` — delete torrent\n"
        "/nuke `<hash>` — delete torrent + files\n"
        "/status — global stats"
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
        # filter bare-number titles
        good = [r for r in results if len(r.title) > 4][:8]
        if not good:
            await msg.edit_text("no results found")
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
        txt = f"*Results for* `{query}`\n\n" + "\n\n".join(lines) + "\n\n_/dl <n> to download_"
        await msg.edit_text(txt, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ error: {e}")

@guard
async def cmd_dl(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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
    msg = await update.message.reply_text(f"⬇️ fetching *{entry.title[:60]}*…", parse_mode="Markdown")
    try:
        resp = await nyaa.client.get(entry.torrent_url)
        result = await qbit.add_torrent_file(resp.content, f"{entry.id}.torrent")
        if "Ok" in result or result == "":
            await msg.edit_text(
                f"✅ added to qbit!\n\n*{entry.title}*\n🌱 {entry.seeders} seeders",
                parse_mode="Markdown")
        else:
            await msg.edit_text(f"⚠️ qbit said: {result}")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")

@guard
async def cmd_magnet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("usage: /magnet <magnet_uri>")
        return
    magnet = ctx.args[0]
    if not magnet.startswith("magnet:"):
        await update.message.reply_text("that doesn't look like a magnet link")
        return
    result = await qbit.add_magnet(magnet)
    if "Ok" in result or result == "":
        await update.message.reply_text("✅ magnet added to qbit!")
    else:
        await update.message.reply_text(f"⚠️ {result}")

@guard
async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        torrents = await qbit.torrents()
        if not torrents:
            await update.message.reply_text("no active torrents")
            return
        lines = [torrent_line(t) for t in torrents[:10]]
        await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

@guard
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        torrents = await qbit.torrents()
        total_dl = sum(t["dlspeed"] for t in torrents)
        total_ul = sum(t["upspeed"] for t in torrents)
        active   = sum(1 for t in torrents if t["state"] == "downloading")
        seeding  = sum(1 for t in torrents if t["state"] == "uploading")
        txt = (
            f"📊 *qBittorrent Status*\n\n"
            f"Total torrents: {len(torrents)}\n"
            f"Downloading: {active}  Seeding: {seeding}\n"
            f"⬇️ {fmt_speed(total_dl)}  ⬆️ {fmt_speed(total_ul)}"
        )
        await update.message.reply_text(txt, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

@guard
async def cmd_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("usage: /pause <hash>")
        return
    await qbit.pause(ctx.args[0])
    await update.message.reply_text("⏸ paused")

@guard
async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("usage: /resume <hash>")
        return
    await qbit.resume(ctx.args[0])
    await update.message.reply_text("▶️ resumed")

@guard
async def cmd_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("usage: /delete <hash>")
        return
    await qbit.delete(ctx.args[0], delete_files=False)
    await update.message.reply_text("🗑 removed (files kept)")

@guard
async def cmd_nuke(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("usage: /nuke <hash>")
        return
    await qbit.delete(ctx.args[0], delete_files=True)
    await update.message.reply_text("💥 deleted torrent + files")

# ── main ──────────────────────────────────────────────────────────────────────
async def on_shutdown(app):
    await qbit.close()
    await nyaa.close()

def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_shutdown(on_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_start))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("dl",     cmd_dl))
    app.add_handler(CommandHandler("magnet", cmd_magnet))
    app.add_handler(CommandHandler("list",   cmd_list))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("pause",  cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CommandHandler("nuke",   cmd_nuke))

    log.info("bot starting — polling telegram")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
