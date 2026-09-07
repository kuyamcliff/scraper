package com.videodl.app.download

import android.os.Parcelable
import kotlinx.parcelize.Parcelize

@Parcelize
data class VideoFormat(
    val formatId: String,
    val ext: String,
    val resolution: String,       // e.g. "1920x1080" or "audio only"
    val fps: Int,                 // 0 for audio-only
    val vcodec: String,           // "none" for audio-only
    val acodec: String,           // "none" for video-only
    val tbr: Float,               // total bitrate kbps
    val vbr: Float,               // video bitrate kbps
    val abr: Float,               // audio bitrate kbps
    val filesize: Long,           // bytes, -1 if unknown
    val filesizeApprox: Long,     // estimated bytes
    val qualityLabel: String,     // e.g. "1080p60", "720p", "Audio 192k"
    val isAudioOnly: Boolean,
    val hasVideo: Boolean,
    val hasAudio: Boolean,
    val formatNote: String
) : Parcelable {

    val displaySize: String get() {
        val bytes = if (filesize > 0) filesize else filesizeApprox
        return if (bytes > 0) formatBytes(bytes) else "~size unknown"
    }

    val displayQuality: String get() = buildString {
        if (isAudioOnly) {
            append("🎵 ")
            if (qualityLabel.isNotEmpty()) append(qualityLabel)
            else if (abr > 0) append("Audio %.0fkbps".format(abr))
            else append("Audio")
        } else {
            append("🎬 ")
            append(if (qualityLabel.isNotEmpty()) qualityLabel else resolution)
            if (fps > 0 && fps != 30) append(" ${fps}fps")
        }
    }

    val codecInfo: String get() = buildString {
        val v = if (vcodec != "none" && vcodec.isNotBlank()) vcodec.substringBefore(".") else null
        val a = if (acodec != "none" && acodec.isNotBlank()) acodec.substringBefore(".") else null
        if (v != null && a != null) append("$v + $a")
        else if (v != null) append(v)
        else if (a != null) append(a)
        if (ext.isNotBlank()) append(" · $ext")
    }

    private fun formatBytes(bytes: Long): String {
        val units = arrayOf("B", "KB", "MB", "GB")
        var value = bytes.toDouble()
        var idx = 0
        while (value >= 1024 && idx < units.size - 1) { value /= 1024.0; idx++ }
        return if (idx == 0) "${value.toLong()} B" else "%.1f %s".format(value, units[idx])
    }
}

@Parcelize
data class VideoInfo(
    val url: String,
    val title: String,
    val uploader: String,
    val duration: Long,           // seconds
    val thumbnailUrl: String,
    val platform: String,
    val formats: List<VideoFormat>
) : Parcelable {
    val durationFormatted: String get() {
        if (duration <= 0) return ""
        val h = duration / 3600
        val m = (duration % 3600) / 60
        val s = duration % 60
        return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
    }
}
