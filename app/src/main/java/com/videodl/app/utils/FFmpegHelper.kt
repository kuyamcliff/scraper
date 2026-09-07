package com.videodl.app.utils

import android.content.Context
import android.util.Log
import java.io.File

/**
 * FFmpeg helper — uses the ffmpeg binary bundled by youtubedl-android:ffmpeg.
 *
 * The YoutubeDL.execute() call automatically appends --ffmpeg-location to every
 * yt-dlp invocation, so post-processing (--postprocessor-args, --audio-format,
 * --merge-output-format) is handled transparently by yt-dlp itself.
 *
 * This helper is available for direct ffmpeg calls if needed (e.g., independent
 * remux/transcode outside of yt-dlp), and exposes the binary path so callers can
 * build custom ProcessBuilder commands.
 *
 * Universal settings used everywhere:
 *   -c:v libx264 -profile:v main -level 4.0 -crf 18 -preset fast -pix_fmt yuv420p
 *   -c:a aac -b:a 192k -ac 2 -ar 44100
 *   -movflags +faststart → .mp4
 *
 * Opens in: VLC, MX Player, CapCut, Premiere Pro, After Effects,
 *           DaVinci Resolve, iMovie, QuickTime, WMP, Galaxy Gallery, etc.
 */
object FFmpegHelper {

    private const val TAG = "FFmpegHelper"

    // Convention: youtubedl-android stores its binaries here.
    private const val BASE_DIR = "youtubedl-android"
    private const val FFMPEG_BIN = "ffmpeg"

    fun init(context: Context) {
        try {
            com.yausername.ffmpeg.FFmpeg.getInstance().init(context)
            Log.d(TAG, "FFmpeg init OK — binary at ${ffmpegBinaryFor(context)}")
        } catch (e: Exception) {
            Log.e(TAG, "FFmpeg init failed", e)
        }
    }

    /**
     * Returns the ffmpeg binary file extracted to the app's private storage.
     * Searches the conventional paths used by youtubedl-android.
     */
    fun ffmpegBinaryFor(context: Context): File? {
        val base = File(context.noBackupFilesDir, BASE_DIR)
        // Typical paths used by the library
        val candidates = listOf(
            File(base, "packages/ffmpeg/bin/$FFMPEG_BIN"),
            File(base, "ffmpeg/bin/$FFMPEG_BIN"),
            File(base, "usr/bin/$FFMPEG_BIN"),
            File(base, "bin/$FFMPEG_BIN"),
        )
        return candidates.firstOrNull { it.exists() && it.canExecute() }
    }

    /**
     * Run ffmpeg with the given args using the bundled binary.
     * @return true if exit code is 0.
     */
    fun run(context: Context, vararg args: String, onLog: ((String) -> Unit)? = null): Boolean {
        val binary = ffmpegBinaryFor(context) ?: run {
            Log.e(TAG, "ffmpeg binary not found; skipping post-process")
            return false
        }
        val cmd = listOf(binary.absolutePath) + args.toList()
        Log.d(TAG, "ffmpeg cmd: ${cmd.joinToString(" ").take(300)}")

        return try {
            val proc = ProcessBuilder(cmd)
                .redirectErrorStream(true)
                .start()

            proc.inputStream.bufferedReader().use { reader ->
                reader.forEachLine { line ->
                    Log.d(TAG, line)
                    onLog?.invoke(line)
                }
            }

            val exit = proc.waitFor()
            if (exit != 0) Log.e(TAG, "ffmpeg exit=$exit")
            exit == 0
        } catch (e: Exception) {
            Log.e(TAG, "ffmpeg exec error", e)
            false
        }
    }

    /**
     * Remux or transcode a file to universal H.264/AAC MP4.
     */
    fun convertToUniversal(
        context: Context,
        inputPath: String,
        outputPath: String,
        audioOnly: Boolean = false
    ): Boolean {
        val args = mutableListOf("-y", "-i", inputPath)
        if (audioOnly) {
            args += listOf("-vn", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "44100",
                "-movflags", "+faststart")
        } else {
            args += listOf(
                "-c:v", "libx264", "-profile:v", "main", "-level", "4.0",
                "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "44100",
                "-movflags", "+faststart"
            )
        }
        args += outputPath
        return run(context, *args.toTypedArray())
    }

    /**
     * Merge separate video + audio streams into a universal MP4.
     */
    fun mergeStreams(context: Context, videoPath: String, audioPath: String, outputPath: String): Boolean {
        return run(context,
            "-y",
            "-i", videoPath,
            "-i", audioPath,
            "-c:v", "libx264", "-profile:v", "main", "-level", "4.0",
            "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "44100",
            "-movflags", "+faststart",
            outputPath
        )
    }
}
