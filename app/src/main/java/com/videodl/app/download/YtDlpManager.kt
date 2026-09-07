package com.videodl.app.download

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDLRequest
import com.yausername.youtubedl_android.YoutubeDLResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/**
 * Manages all yt-dlp interactions:
 *  - Initialization
 *  - Fetching video info + formats
 *  - Triggering downloads
 */
object YtDlpManager {

    private const val TAG = "YtDlpManager"
    private val gson = Gson()

    // ─── Init ─────────────────────────────────────────────────────────────────

    fun init(context: Context) {
        try {
            YoutubeDL.getInstance().init(context)
            Log.d(TAG, "yt-dlp initialized")
        } catch (e: Exception) {
            Log.e(TAG, "init failed", e)
        }
    }

    suspend fun updateYtDlp(context: Context): String = withContext(Dispatchers.IO) {
        try {
            val result = YoutubeDL.getInstance().updateYoutubeDL(context, YoutubeDL.UpdateChannel.STABLE)
            result.name
        } catch (e: Exception) {
            Log.e(TAG, "update failed", e)
            "UPDATE_FAILED"
        }
    }

    // ─── Fetch info ───────────────────────────────────────────────────────────

    /**
     * Fetch video metadata + all available formats without downloading.
     * Runs yt-dlp with --dump-json and parses the JSON output.
     */
    suspend fun fetchVideoInfo(url: String): Result<VideoInfo> = withContext(Dispatchers.IO) {
        try {
            val request = YoutubeDLRequest(url).apply {
                addOption("--dump-json")
                addOption("--no-playlist")
                addOption("--no-download")
                addOption("--no-warnings")
                addOption("--skip-download")
                // Use cookies from browser to help with age-restricted content
                // addOption("--cookies-from-browser", "chrome") // optional
            }

            val response: YoutubeDLResponse = YoutubeDL.getInstance().execute(request)
            val json = response.out.trim()

            if (json.isBlank()) {
                return@withContext Result.failure(Exception("yt-dlp returned no data"))
            }

            val info = parseVideoInfo(url, json)
            Result.success(info)
        } catch (e: Exception) {
            Log.e(TAG, "fetchVideoInfo failed for $url", e)
            Result.failure(e)
        }
    }

    // ─── Parse JSON ───────────────────────────────────────────────────────────

    private fun parseVideoInfo(url: String, json: String): VideoInfo {
        val root: JsonObject = JsonParser.parseString(json).asJsonObject

        val title = root.getStr("title") ?: root.getStr("fulltitle") ?: "Untitled"
        val uploader = root.getStr("uploader") ?: root.getStr("channel") ?: ""
        val duration = root.get("duration")?.takeIf { !it.isJsonNull }?.asLong ?: 0L
        val thumbnail = root.getStr("thumbnail") ?: ""
        val extractor = root.getStr("extractor_key") ?: root.getStr("extractor") ?: "Unknown"

        val formatsArray = root.getAsJsonArray("formats") ?: return VideoInfo(
            url = url, title = title, uploader = uploader,
            duration = duration, thumbnailUrl = thumbnail,
            platform = extractor, formats = emptyList()
        )

        val formats = mutableListOf<VideoFormat>()

        for (el in formatsArray) {
            if (!el.isJsonObject) continue
            val f = el.asJsonObject

            val formatId = f.getStr("format_id") ?: continue
            val ext = f.getStr("ext") ?: "mp4"
            val vcodec = f.getStr("vcodec") ?: "none"
            val acodec = f.getStr("acodec") ?: "none"
            val resolution = f.getStr("resolution") ?: ""
            val fps = f.get("fps")?.takeIf { !it.isJsonNull }?.asInt ?: 0
            val tbr = f.get("tbr")?.takeIf { !it.isJsonNull }?.asFloat ?: 0f
            val vbr = f.get("vbr")?.takeIf { !it.isJsonNull }?.asFloat ?: 0f
            val abr = f.get("abr")?.takeIf { !it.isJsonNull }?.asFloat ?: 0f
            val filesize = f.get("filesize")?.takeIf { !it.isJsonNull }?.asLong ?: -1L
            val filesizeApprox = f.get("filesize_approx")?.takeIf { !it.isJsonNull }?.asLong ?: -1L
            val formatNote = f.getStr("format_note") ?: ""
            val height = f.get("height")?.takeIf { !it.isJsonNull }?.asInt ?: 0

            // Skip storyboard/thumbnail tracks
            if (ext == "mhtml" || vcodec.startsWith("mhtml")) continue

            val hasVideo = vcodec != "none" && vcodec.isNotBlank()
            val hasAudio = acodec != "none" && acodec.isNotBlank()
            val isAudioOnly = !hasVideo && hasAudio

            // Build human-readable quality label
            val qualityLabel = when {
                isAudioOnly -> buildAudioLabel(abr, acodec, ext)
                height > 0 -> buildVideoLabel(height, fps, formatNote)
                resolution.isNotBlank() -> resolution
                else -> formatNote.ifBlank { formatId }
            }

            formats += VideoFormat(
                formatId = formatId,
                ext = ext,
                resolution = resolution.ifBlank { if (height > 0) "${height}p" else "unknown" },
                fps = fps,
                vcodec = vcodec,
                acodec = acodec,
                tbr = tbr,
                vbr = vbr,
                abr = abr,
                filesize = filesize,
                filesizeApprox = filesizeApprox,
                qualityLabel = qualityLabel,
                isAudioOnly = isAudioOnly,
                hasVideo = hasVideo,
                hasAudio = hasAudio,
                formatNote = formatNote
            )
        }

        // Sort: best video quality first, then audio-only by bitrate
        val sorted = formats.sortedWith(
            compareByDescending<VideoFormat> { it.hasVideo }
                .thenByDescending { it.tbr }
                .thenByDescending { it.abr }
        )

        return VideoInfo(
            url = url,
            title = title,
            uploader = uploader,
            duration = duration,
            thumbnailUrl = thumbnail,
            platform = extractor,
            formats = sorted
        )
    }

    private fun buildVideoLabel(height: Int, fps: Int, note: String): String {
        val res = when {
            height >= 2160 -> "4K"
            height >= 1440 -> "1440p"
            height >= 1080 -> "1080p"
            height >= 720  -> "720p"
            height >= 480  -> "480p"
            height >= 360  -> "360p"
            height >= 240  -> "240p"
            else           -> "${height}p"
        }
        val fpsLabel = if (fps > 0 && fps != 30) "${fps}fps" else ""
        return listOf(res, fpsLabel).filter { it.isNotBlank() }.joinToString(" ")
    }

    private fun buildAudioLabel(abr: Float, codec: String, ext: String): String {
        val bitrateStr = if (abr > 0) "%.0fkbps".format(abr) else ""
        val codecShort = codec.substringBefore(".").uppercase()
        return listOf("Audio", bitrateStr, codecShort).filter { it.isNotBlank() }.joinToString(" ")
    }

    // ─── Download ─────────────────────────────────────────────────────────────

    /**
     * Download a specific format to outputDir.
     * Uses yt-dlp's own merge capability for DASH streams,
     * then post-processes with FFmpeg for universal compatibility.
     */
    suspend fun download(
        url: String,
        format: VideoFormat,
        outputDir: File,
        onProgress: (Float, Long, String) -> Unit
    ): Result<File> = withContext(Dispatchers.IO) {
        try {
            outputDir.mkdirs()

            val outputTemplate = "${outputDir.absolutePath}/%(title)s.%(ext)s"

            val request = YoutubeDLRequest(url).apply {
                addOption("--no-playlist")
                addOption("--no-warnings")
                addOption("-o", outputTemplate)

                if (format.isAudioOnly) {
                    // Audio only → extract best audio and convert to M4A (AAC)
                    addOption("-f", format.formatId)
                    addOption("-x")                         // extract audio
                    addOption("--audio-format", "m4a")     // output AAC/M4A
                    addOption("--audio-quality", "0")      // best
                    addOption("--ffmpeg-location", getFfmpegPath())
                } else {
                    // Video: select format + merge with best audio if needed
                    val fmtArg = if (!format.hasAudio) {
                        // Video-only DASH stream → merge with best audio
                        "${format.formatId}+bestaudio[ext=m4a]/bestaudio"
                    } else {
                        format.formatId
                    }
                    addOption("-f", fmtArg)
                    addOption("--merge-output-format", "mp4")
                    addOption("--remux-video", "mp4")
                    addOption("--ffmpeg-location", getFfmpegPath())
                    // Post-process: re-encode to universally compatible H.264+AAC
                    addOption("--postprocessor-args",
                        "ffmpeg:-c:v libx264 -profile:v main -level 4.0 -crf 18 -preset fast " +
                        "-pix_fmt yuv420p -c:a aac -b:a 192k -ac 2 -ar 44100 -movflags +faststart")
                }

                // Embed thumbnail and metadata where possible
                addOption("--embed-thumbnail")
                addOption("--add-metadata")
                addOption("--no-part")           // no partial .part files littering the folder
            }

            val response: YoutubeDLResponse = YoutubeDL.getInstance().execute(
                request,
                processId = url.hashCode().toString()
            ) { progress, etaInSeconds, line ->
                onProgress(progress, etaInSeconds, line ?: "")
            }

            // Find the downloaded file
            val downloadedFile = outputDir.listFiles()
                ?.filter { it.isFile && !it.name.endsWith(".part") }
                ?.maxByOrNull { it.lastModified() }
                ?: return@withContext Result.failure(Exception("Downloaded file not found"))

            Result.success(downloadedFile)
        } catch (e: Exception) {
            Log.e(TAG, "download failed", e)
            Result.failure(e)
        }
    }

    fun cancelDownload(url: String) {
        try {
            YoutubeDL.getInstance().destroyProcessById(url.hashCode().toString())
        } catch (e: Exception) {
            Log.e(TAG, "cancelDownload error", e)
        }
    }

    private fun getFfmpegPath(): String {
        // ffmpeg-kit provides the binary path; yt-dlp will use it for merging
        return "ffmpeg"   // on the PATH via ffmpeg-kit
    }

    // ─── Extension helpers ────────────────────────────────────────────────────

    private fun JsonObject.getStr(key: String): String? =
        get(key)?.takeIf { !it.isJsonNull }?.asString?.trim()?.takeIf { it.isNotBlank() }
}
