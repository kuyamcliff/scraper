package com.videodl.app.utils

object FormatSize {

    fun formatBytes(bytes: Long): String {
        if (bytes <= 0) return "~size unknown"
        val units = arrayOf("B", "KB", "MB", "GB")
        var value = bytes.toDouble()
        var unitIndex = 0
        while (value >= 1024 && unitIndex < units.size - 1) {
            value /= 1024.0
            unitIndex++
        }
        return if (unitIndex == 0) "${value.toLong()} ${units[unitIndex]}"
        else "%.1f %s".format(value, units[unitIndex])
    }

    fun estimateSize(formatId: String, durationSecs: Long, bitrateKbps: Int): Long {
        if (bitrateKbps <= 0 || durationSecs <= 0) return -1L
        // bytes = (bitrate_kbps * 1000 / 8) * duration_seconds
        return (bitrateKbps.toLong() * 1000L / 8L) * durationSecs
    }
}
