package com.videodl.app.utils

import androidx.annotation.DrawableRes
import com.videodl.app.R

data class Platform(
    val name: String,
    val iconRes: Int,
    val color: Int
)

object PlatformDetector {

    data class PlatformInfo(
        val name: String,
        val emoji: String,
        val accentHex: String
    )

    private val PLATFORM_PATTERNS = listOf(
        // Video platforms
        PlatformInfo("YouTube",       "▶️",  "#FF0000") to listOf(
            "youtube.com/watch", "youtu.be/", "youtube.com/shorts", "youtube.com/live",
            "m.youtube.com"
        ),
        PlatformInfo("YouTube Music", "🎵",  "#FF0000") to listOf("music.youtube.com"),
        PlatformInfo("TikTok",        "🎵",  "#010101") to listOf("tiktok.com/", "vm.tiktok.com"),
        PlatformInfo("Instagram",     "📸",  "#C13584") to listOf(
            "instagram.com/reel", "instagram.com/p/", "instagram.com/tv/",
            "instagram.com/stories/"
        ),
        PlatformInfo("Twitter/X",     "🐦",  "#1DA1F2") to listOf(
            "twitter.com/", "x.com/", "t.co/"
        ),
        PlatformInfo("Facebook",      "👤",  "#1877F2") to listOf(
            "facebook.com/watch", "facebook.com/video", "fb.watch", "fb.com"
        ),
        PlatformInfo("Reddit",        "🤖",  "#FF4500") to listOf(
            "reddit.com/r/", "v.redd.it", "redd.it"
        ),
        PlatformInfo("Twitch",        "🎮",  "#9146FF") to listOf(
            "twitch.tv/", "clips.twitch.tv"
        ),
        PlatformInfo("Vimeo",         "🎬",  "#1AB7EA") to listOf("vimeo.com/"),
        PlatformInfo("Dailymotion",   "📹",  "#0066DC") to listOf("dailymotion.com/", "dai.ly/"),
        PlatformInfo("Rumble",        "📺",  "#85C742") to listOf("rumble.com/"),
        PlatformInfo("Bilibili",      "📺",  "#00A1D6") to listOf("bilibili.com/", "b23.tv"),
        PlatformInfo("Niconico",      "🎌",  "#252525") to listOf("nicovideo.jp/", "nico.ms"),
        PlatformInfo("SoundCloud",    "🔊",  "#FF5500") to listOf("soundcloud.com/"),
        PlatformInfo("Spotify",       "🎧",  "#1DB954") to listOf("spotify.com/", "open.spotify.com"),
        PlatformInfo("Apple Music",   "🍎",  "#FC3C44") to listOf("music.apple.com"),
        PlatformInfo("Bandcamp",      "🎸",  "#1DA0C3") to listOf("bandcamp.com/"),
        PlatformInfo("Mixcloud",      "🎚️",  "#52AAD8") to listOf("mixcloud.com/"),
        PlatformInfo("Odysee",        "📡",  "#EF1970") to listOf("odysee.com/", "lbry.tv"),
        PlatformInfo("PeerTube",      "📡",  "#F1680D") to listOf("peertube"),
        PlatformInfo("Streamable",    "🎞️",  "#1CAAD9") to listOf("streamable.com/"),
        PlatformInfo("Imgur",         "🖼️",  "#1BB76E") to listOf("imgur.com/"),
        PlatformInfo("Gfycat",        "🐱",  "#00C6AF") to listOf("gfycat.com/"),
        PlatformInfo("Pinterest",     "📌",  "#E60023") to listOf("pinterest.com/", "pin.it"),
        PlatformInfo("LinkedIn",      "💼",  "#0077B5") to listOf("linkedin.com/posts", "linkedin.com/feed"),
        PlatformInfo("Snapchat",      "👻",  "#FFFC00") to listOf("snapchat.com/"),
        PlatformInfo("Kick",          "🟢",  "#53FC18") to listOf("kick.com/"),
        PlatformInfo("Crunchyroll",   "🍥",  "#F47521") to listOf("crunchyroll.com/"),
        PlatformInfo("Funimation",    "🎏",  "#410099") to listOf("funimation.com/"),
        PlatformInfo("Pornhub",       "🔞",  "#FF9000") to listOf("pornhub.com/"),
        PlatformInfo("XVideos",       "🔞",  "#CC0000") to listOf("xvideos.com/"),
        PlatformInfo("xHamster",      "🔞",  "#E87722") to listOf("xhamster.com/"),
        PlatformInfo("YouTube Kids",  "👶",  "#00BBF0") to listOf("youtubekids.com"),
        PlatformInfo("Vevo",          "🎤",  "#EE1A23") to listOf("vevo.com/"),
        PlatformInfo("Metacafe",      "📽️",  "#FF3333") to listOf("metacafe.com/"),
        PlatformInfo("Break",         "😂",  "#27AE60") to listOf("break.com/"),
        PlatformInfo("9GAG",          "😅",  "#000000") to listOf("9gag.com/"),
        PlatformInfo("Telegram",      "✈️",  "#2CA5E0") to listOf("t.me/", "telegram.me/"),
        PlatformInfo("Discord",       "🎮",  "#5865F2") to listOf("cdn.discordapp.com/", "discord.gg/"),
        PlatformInfo("Dropbox",       "📦",  "#0061FF") to listOf("dropbox.com/"),
        PlatformInfo("Google Drive",  "☁️",  "#4285F4") to listOf("drive.google.com/"),
        PlatformInfo("OneDrive",      "☁️",  "#094AB2") to listOf("onedrive.live.com/", "1drv.ms"),
    )

    fun detect(url: String): PlatformInfo {
        val lower = url.lowercase()
        for ((info, patterns) in PLATFORM_PATTERNS) {
            if (patterns.any { lower.contains(it) }) return info
        }
        return PlatformInfo("Unknown", "🌐", "#607D8B")
    }

    fun isValidUrl(url: String): Boolean {
        return url.startsWith("http://") || url.startsWith("https://")
    }
}
