package com.videodl.app.download

import android.os.Parcelable
import kotlinx.parcelize.Parcelize

enum class DownloadStatus {
    QUEUED, FETCHING_INFO, DOWNLOADING, POST_PROCESSING, DONE, FAILED, CANCELLED
}

@Parcelize
data class DownloadTask(
    val id: String,              // UUID
    val url: String,
    val title: String,
    val format: VideoFormat,
    var status: DownloadStatus = DownloadStatus.QUEUED,
    var progress: Float = 0f,
    var eta: Long = 0L,          // seconds
    var speed: String = "",
    var filePath: String = "",
    var errorMsg: String = "",
    val createdAt: Long = System.currentTimeMillis()
) : Parcelable
