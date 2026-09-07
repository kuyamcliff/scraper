# 📥 Video Downloader — Android App

> **100% on-device.** No cloud, no servers, no accounts. Powered by **yt-dlp** + **FFmpeg**.

## Features

- **1000+ platforms** — YouTube, TikTok, Instagram, Twitter/X, Facebook, Reddit, Twitch, Vimeo, Dailymotion, SoundCloud, Bilibili, and everything else yt-dlp supports
- **Auto platform detection** — paste any link, the app instantly recognises the source
- **All available qualities** — fetches every format yt-dlp sees: 4K, 1080p, 720p, 480p, audio-only tracks — each showing codec, resolution, and estimated file size
- **Universal output codec** — all downloads are post-processed to **H.264 (Main L4.0) + AAC 192k** inside an **MP4 faststart** container, so the file opens in every app:
  - VLC, MX Player, Samsung/Google Gallery
  - CapCut, Adobe Premiere Pro, After Effects, DaVinci Resolve
  - Windows Media Player, QuickTime, iMovie
  - Any other mainstream player or editor
- **Share-to-download** — share a link from any browser/app directly to Video Downloader
- **Background download service** — downloads continue while you use other apps
- **Download queue & progress** — live progress bar, ETA, speed

---

## Architecture

```
app/
├── download/
│   ├── YtDlpManager.kt       # yt-dlp wrapper — fetchInfo, download
│   ├── VideoFormat.kt        # Format/VideoInfo data models
│   ├── DownloadTask.kt       # Download task state model
│   └── DownloadService.kt    # Foreground service, broadcasts progress
├── ui/
│   ├── MainActivity.kt       # URL input, platform detection, video info card
│   ├── MainViewModel.kt      # Fetch info, UI state
│   ├── FormatPickerActivity  # Format list → triggers download
│   ├── FormatAdapter.kt      # RecyclerView adapter for formats
│   ├── DownloadsActivity.kt  # Live download queue
│   └── DownloadTaskAdapter   # RecyclerView for tasks
└── utils/
    ├── PlatformDetector.kt   # URL → Platform name/emoji
    ├── FormatSize.kt         # Bytes formatting
    └── FFmpegHelper.kt       # FFmpeg post-processing (H.264/AAC/MP4)
```

### Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| `youtubedl-android` | 0.17+ | Bundles Python 3 + yt-dlp binary for ARM/x86 |
| `ffmpeg-kit-full` | 6.0-2 | Full FFmpeg build (libx264, aac, all codecs) |
| `ffmpeg-kit-full` | 6.0-2 | Post-processing to universal H.264/AAC |
| Glide | 4.16 | Thumbnail loading |
| Gson | 2.10 | JSON parsing of yt-dlp --dump-json |
| Coroutines | 1.7.3 | Async fetch + download |

---

## FFmpeg Settings — Why These?

```
-c:v libx264 -profile:v main -level 4.0 -crf 18 -preset fast -pix_fmt yuv420p
-c:a aac -b:a 192k -ac 2 -ar 44100
-movflags +faststart
Container: .mp4
```

| Setting | Value | Reason |
|---------|-------|--------|
| Video codec | H.264 (libx264) | Hardware-decoded on every Android/iOS/desktop since 2010 |
| Profile | Main | Supported everywhere; Baseline is for old phones only |
| Level | 4.0 | Handles up to 1080p60 — high enough for all content |
| CRF | 18 | Near-lossless quality; transparent to the eye |
| Pixel format | yuv420p | 8-bit 4:2:0 — only format ALL hardware decoders accept |
| Audio codec | AAC-LC | Universal; MP3 is legacy, Opus/Vorbis not supported in NLEs |
| Audio bitrate | 192k stereo | CD quality equivalent for AAC |
| Sample rate | 44100 Hz | Universal sample rate — 48000 also fine but 44100 is safer |
| movflags | +faststart | Moves MOOV atom to file start → instant playback / streaming |

---

## Build Instructions

### Requirements

- Android Studio Hedgehog (2023.1.1) or newer
- Android SDK 34
- Kotlin 1.9+
- JDK 17

### Steps

1. **Clone** this repository
2. Open in **Android Studio**
3. Set `sdk.dir` in `local.properties` to your Android SDK path:
   ```
   sdk.dir=/Users/yourname/Library/Android/sdk
   ```
4. Let Gradle sync — it will download all dependencies including yt-dlp binary
5. Build → **Build APK** or run on device

### Build APK from CLI

```bash
./gradlew assembleDebug
# APK at: app/build/outputs/apk/debug/app-debug.apk
```

For release (needs keystore):
```bash
./gradlew assembleRelease
```

---

## Permissions

| Permission | Why |
|-----------|-----|
| `INTERNET` | Fetch video info and stream download |
| `WRITE_EXTERNAL_STORAGE` (≤ API 28) | Save downloaded files |
| `READ_MEDIA_VIDEO` / `READ_MEDIA_AUDIO` (API 33+) | Save to Downloads |
| `POST_NOTIFICATIONS` | Download progress notifications |
| `FOREGROUND_SERVICE_DATA_SYNC` | Background download service |

---

## Output Paths

- Videos: `Android/data/com.videodl.app/files/VideoDownloader/Video/`
- Audio: `Android/data/com.videodl.app/files/VideoDownloader/Audio/`

Files are accessible via Files app, USB, or any file manager.

---

## Legal

This tool is for downloading content you own or have permission to download. Respect copyright and platform Terms of Service.
