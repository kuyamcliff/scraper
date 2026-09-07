package com.videodl.app.download

import android.content.Context
import android.util.Log
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
 *
 * NOTE: YoutubeDL.execute() internally appends --ffmpeg-location pointing to
 * the ffmpeg binary bundled in the :ffmpeg module, so we do NOT need to add it manually.
 */
object YtDlpManager {

    private const val TAG = "YtDlpManager"

    // ─── Init ─────────────────────────────────────────────────────────────────

    fun init(context: Context) {
        try {
            YoutubeDL.getInstance().init(context)
            com.yausername.ffmpeg.FFmpeg.getInstance().init(context)
            Log.d(TAG, "yt-dlp + ffmpeg initialized")
        } catch (e: Exception) {
            Log.e(TAG, "init failed", e)
        }
    }

    suspend fun updateYtDlp(context: Context): String = withContext(Dispatchers.IO) {
        try {
            // updateYoutubeDL(context) — UpdateChannel defaults to STABLE
            val result = YoutubeDL.getInstance().updateYoutubeDL(context)
            result?.name ?: "NO_UPDATE"
        } catch (e: Exception) {
            Log.e(TAG, "update failed", e)
            "UPDATE_FAILED"
        }
    }

    // ─── Fetch info ───────────────────────────────────────────────────────────

    /**
     * Fetch video metadata + all available formats without downloading.
     */
    suspend fun fetchVideoInfo(url: String): Result<VideoInfo> = withContext(Dispatchers.IO) {
        try {
            val request = YoutubeDLRequest(url).apply {
                addOption("--dump-json")
                addOption("--no-playlist")
                addOption("--skip-download")
                addOption("--no-warnings")
            }

            val response: YoutubeDLResponse = YoutubeDL.getInstance().execute(request, null, null)
            val json = response.out.trim()

            if (json.isBlank()) {
                return@withContext Result.failure(Exception("yt-dlp returned no data. Check the URL."))
            }

            // yt-dlp may return multiple JSON objects for playlists; take the first
            val firstJson = json.lineSequence().firstOrNull { it.trimStart().startsWith("{") }
                ?: json

            val info = parseVideoInfo(url, firstJson)
            Result.success(info)
        } catch (e: Exception) {
            Log.e(TAG, "fetchVideoInfo failed for $url", e)
            Result.failure(e)
        }
    }

    // ─── Parse JSON ───────────────────────────────────────────────────────────

    private fun parseVideoInfo(url: String, json: String): VideoInfo {
        val root: JsonObject = JsonParser.parseString(json).asJsonObject

        val title     = root.getStr("title") ?: root.getStr("fulltitle") ?: "Untitled"
        val uploader  = root.getStr("uploader") ?: root.getStr("channel") ?: ""
        val duration  = root.get("duration")?.takeIf { !it.isJsonNull }?.asLong ?: 0L
        val thumbnail = root.getStr("thumbnail") ?: ""
        val extractor = root.getStr("extractor_key") ?: root.getStr("extractor") ?: "Unknown"

        val formatsArray = root.getAsJsonArray("formats")
            ?: return VideoInfo(url, title, uploader, duration, thumbnail, extractor, emptyList())

        val formats = mutableListOf<VideoFormat>()

        for (el in formatsArray) {
            if (!el.isJsonObject) continue
            val f = el.asJsonObject

            val formatId = f.getStr("format_id") ?: continue
            val ext      = f.getStr("ext") ?: "mp4"
            val vcodec   = f.getStr("vcodec") ?: "none"
            val acodec   = f.getStr("acodec") ?: "none"
            val res      = f.getStr("resolution") ?: ""
            val fps      = f.get("fps")?.takeIf { !it.isJsonNull }?.asInt ?: 0
            val tbr      = f.get("tbr")?.takeIf { !it.isJsonNull }?.asFloat ?: 0f
            val vbr      = f.get("vbr")?.takeIf { !it.isJsonNull }?.asFloat ?: 0f
            val abr      = f.get("abr")?.takeIf { !it.isJsonNull }?.asFloat ?: 0f
            val filesize = f.get("filesize")?.takeIf { !it.isJsonNull }?.asLong ?: -1L
            val filesizeApprox = f.get("filesize_approx")?.takeIf { !it.isJsonNull }?.asLong ?: -1L
            val note     = f.getStr("format_note") ?: ""
            val height   = f.get("height")?.takeIf { !it.isJsonNull }?.asInt ?: 0

            // Skip storyboard / thumbnail tracks
            if (ext == "mhtml" || vcodec.startsWith("mhtml")) continue

            val hasVideo   = vcodec != "none" && vcodec.isNotBlank()
            val hasAudio   = acodec != "none" && acodec.isNotBlank()
            val isAudioOnly = !hasVideo && hasAudio

            val qualityLabel = when {
                isAudioOnly -> buildAudioLabel(abr, acodec)
                height > 0  -> buildVideoLabel(height, fps)
                res.isNotBlank() -> res
                else -> note.ifBlank { formatId }
            }

            formats += VideoFormat(
                formatId       = formatId,
                ext            = ext,
                resolution     = res.ifBlank { if (height > 0) "${height}p" else "?" },
                fps            = fps,
                vcodec         = vcodec,
                acodec         = acodec,
                tbr            = tbr,
                vbr            = vbr,
                abr            = abr,
                filesize       = filesize,
                filesizeApprox = filesizeApprox,
                qualityLabel   = qualityLabel,
                isAudioOnly    = isAudioOnly,
                hasVideo       = hasVideo,
                hasAudio       = hasAudio,
                formatNote     = note
            )
        }

        val sorted = formats.sortedWith(
            compareByDescending<VideoFormat> { it.hasVideo }
                .thenByDescending { it.tbr }
                .thenByDescending { it.abr }
        )

        return VideoInfo(url, title, uploader, duration, thumbnail, extractor, sorted)
    }

    private fun buildVideoLabel(height: Int, fps: Int): String {
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
        return if (fps > 0 && fps != 30) "$res ${fps}fps" else res
    }

    private fun buildAudioLabel(abr: Float, codec: String): String {
        val bits = if (abr > 0) "%.0fkbps".format(abr) else ""
        val c = codec.substringBefore(".").uppercase()
        return listOf("Audio", bits, c).filter { it.isNotBlank() }.joinToString(" ")
    }

    // ─── Download ─────────────────────────────────────────────────────────────

    /**
     * Download a specific format to outputDir.
     * yt-dlp merges DASH streams and the library automatically passes the bundled
     * ffmpeg binary via --ffmpeg-location.
     *
     * Post-processing flags enforce universal H.264/AAC in MP4 output.
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
            val processId = url.hashCode().toString()

            val request = YoutubeDLRequest(url).apply {
                addOption("--no-playlist")
                addOption("--no-warnings")
                addOption("-o", outputTemplate)
                addOption("--no-part")

                if (format.isAudioOnly) {
                    addOption("-f", format.formatId)
                    addOption("-x")
                    addOption("--audio-format", "m4a")
                    addOption("--audio-quality", "0")
                } else {
                    val fmtArg = if (!format.hasAudio) {
                        "${format.formatId}+bestaudio[ext=m4a]/bestaudio"
                    } else {
                        format.formatId
                    }
                    addOption("-f", fmtArg)
                    addOption("--merge-output-format", "mp4")
                    addOption("--remux-video", "mp4")
                    // Universal H.264/AAC post-processing — runs via bundled ffmpeg
                    addOption(
                        "--postprocessor-args",
                        "ffmpeg:-c:v libx264 -profile:v main -level 4.0 -crf 18 -preset fast " +
                        "-pix_fmt yuv420p -c:a aac -b:a 192k -ac 2 -ar 44100 -movflags +faststart"
                    )
                }

                addOption("--add-metadata")
            }

            // Pass processId positionally (named args unsupported for Java-compiled library)
            val response: YoutubeDLResponse = YoutubeDL.getInstance()
                .execute(request, processId) { progress, eta, line ->
                    onProgress(progress, eta, line ?: "")
                }

            val downloadedFile = outputDir.listFiles()
                ?.filter { it.isFile && !it.name.endsWith(".part") }
                ?.maxByOrNull { it.lastModified() }
                ?: return@withContext Result.failure(Exception("Downloaded file not found in ${outputDir.path}"))

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

    // ─── Helpers ──────────────────────────────────────────────────────────────

    private fun JsonObject.getStr(key: String): String? =
        get(key)?.takeIf { !it.isJsonNull }?.asString?.trim()?.takeIf { it.isNotBlank() }
}
