package com.videodl.app.utils

import android.util.Log
import com.arthenica.ffmpegkit.FFmpegKit
import com.arthenica.ffmpegkit.ReturnCode
import java.io.File

/**
 * FFmpeg post-processing helper.
 *
 * Universal output settings:
 *  - Video: H.264 (libx264) Main profile, CRF 18 (near-lossless), yuv420p pixel format
 *  - Audio: AAC-LC 192k stereo
 *  - Container: MP4 with faststart (moov atom at start for streaming)
 *
 * This combination opens in: VLC, MX Player, Samsung Gallery, Google Photos,
 * CapCut, Adobe Premiere Pro, After Effects, DaVinci Resolve, Windows Media Player,
 * QuickTime, iMovie, and every other mainstream player/editor.
 */
object FFmpegHelper {

    private const val TAG = "FFmpegHelper"

    /**
     * Remux / transcode input file to universally compatible MP4.
     * Called after yt-dlp downloads raw streams (e.g., webm, opus, etc.)
     * to ensure the final file plays everywhere.
     *
     * @param inputPath  source file from yt-dlp
     * @param outputPath destination .mp4 path
     * @param isAudioOnly if true, strip video and encode audio only to AAC
     * @param onProgress  0..100 progress callback
     * @return true on success
     */
    fun convertToUniversal(
        inputPath: String,
        outputPath: String,
        isAudioOnly: Boolean = false,
        durationMs: Long = 0L,
        onProgress: ((Int) -> Unit)? = null
    ): Boolean {
        val args = buildFFmpegArgs(inputPath, outputPath, isAudioOnly)
        Log.d(TAG, "FFmpeg command: ffmpeg ${args.joinToString(" ")}")

        val session = FFmpegKit.executeWithArguments(
            args.toTypedArray()
        ) { log ->
            Log.d(TAG, log.message ?: "")
        }

        if (!ReturnCode.isSuccess(session.returnCode)) {
            Log.e(TAG, "FFmpeg failed: rc=${session.returnCode}, " +
                    "output=${session.allLogsAsString?.takeLast(500)}")
            return false
        }
        onProgress?.invoke(100)
        return true
    }

    /**
     * Quick remux (no re-encode) — used when yt-dlp already delivers H.264+AAC
     * in an MP4 container; just copy streams for speed.
     */
    fun remuxToMp4(inputPath: String, outputPath: String): Boolean {
        val args = arrayOf(
            "-y",
            "-i", inputPath,
            "-c", "copy",
            "-movflags", "+faststart",
            outputPath
        )
        val session = FFmpegKit.executeWithArguments(args)
        return ReturnCode.isSuccess(session.returnCode)
    }

    /**
     * Merge separate video + audio streams (yt-dlp DASH/HLS splits them).
     */
    fun mergeStreams(
        videoPath: String,
        audioPath: String,
        outputPath: String,
        isVideoH264: Boolean = false,
        isAudioAac: Boolean = false
    ): Boolean {
        val args = mutableListOf(
            "-y",
            "-i", videoPath,
            "-i", audioPath
        )

        if (isVideoH264 && isAudioAac) {
            // Both already in target codec → copy only
            args += listOf("-c:v", "copy", "-c:a", "copy")
        } else if (isVideoH264) {
            args += listOf("-c:v", "copy")
            args += listOf("-c:a", "aac", "-b:a", "192k", "-ac", "2")
        } else if (isAudioAac) {
            args += listOf(
                "-c:v", "libx264",
                "-profile:v", "main",
                "-level", "4.0",
                "-crf", "18",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-c:a", "copy"
            )
        } else {
            // Full transcode both streams
            args += buildTranscodeArgs()
        }

        args += listOf("-movflags", "+faststart", outputPath)

        val session = FFmpegKit.executeWithArguments(args.toTypedArray())
        if (!ReturnCode.isSuccess(session.returnCode)) {
            Log.e(TAG, "mergeStreams failed: ${session.allLogsAsString?.takeLast(300)}")
            return false
        }
        return true
    }

    /**
     * Extract audio to M4A (AAC inside MPEG-4 container) — opens in every music player.
     */
    fun extractAudio(inputPath: String, outputPath: String): Boolean {
        val args = arrayOf(
            "-y",
            "-i", inputPath,
            "-vn",                 // drop video
            "-c:a", "aac",
            "-b:a", "192k",
            "-ac", "2",            // stereo
            "-ar", "44100",        // 44.1 kHz — universal sample rate
            "-movflags", "+faststart",
            outputPath
        )
        val session = FFmpegKit.executeWithArguments(args)
        return ReturnCode.isSuccess(session.returnCode)
    }

    // ─── Private helpers ─────────────────────────────────────────────────────

    private fun buildFFmpegArgs(
        input: String, output: String, audioOnly: Boolean
    ): List<String> {
        val args = mutableListOf("-y", "-i", input)
        if (audioOnly) {
            args += listOf(
                "-vn",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ac", "2",
                "-ar", "44100",
                "-movflags", "+faststart"
            )
        } else {
            args += buildTranscodeArgs()
            args += listOf("-movflags", "+faststart")
        }
        args += output
        return args
    }

    private fun buildTranscodeArgs(): List<String> = listOf(
        // ── Video: H.264 Main @ L4.0, near-lossless, broadest compat ────────
        "-c:v", "libx264",
        "-profile:v", "main",       // Baseline works on very old phones; main is fine everywhere
        "-level", "4.0",            // Supports up to 1080p60 without issues
        "-crf", "18",               // Visually lossless (0=lossless, 23=default, 28=low)
        "-preset", "fast",          // Balance speed vs. compression
        "-pix_fmt", "yuv420p",      // 8-bit 4:2:0 — only format all hardware decoders accept
        // ── Audio: AAC-LC stereo 44.1kHz ─────────────────────────────────────
        "-c:a", "aac",
        "-b:a", "192k",
        "-ac", "2",
        "-ar", "44100"
    )

    fun cancelAll() {
        FFmpegKit.cancel()
    }
}
