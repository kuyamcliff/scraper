package com.videodl.app.download

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.videodl.app.R
import com.videodl.app.ui.DownloadsActivity
import kotlinx.coroutines.*
import java.io.File
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

class DownloadService : Service() {

    companion object {
        const val ACTION_START   = "com.videodl.app.START_DOWNLOAD"
        const val ACTION_CANCEL  = "com.videodl.app.CANCEL_DOWNLOAD"
        const val EXTRA_URL      = "url"
        const val EXTRA_FORMAT   = "format"
        const val EXTRA_TITLE    = "title"
        const val EXTRA_TASK_ID  = "task_id"

        const val NOTIF_CHANNEL_ID  = "download_channel"
        const val NOTIF_CHANNEL_PROGRESS = "progress_channel"
        const val NOTIF_ID_FOREGROUND = 1001

        // Broadcast action for UI updates
        const val ACTION_PROGRESS = "com.videodl.app.DOWNLOAD_PROGRESS"
        const val ACTION_DONE     = "com.videodl.app.DOWNLOAD_DONE"
        const val ACTION_FAILED   = "com.videodl.app.DOWNLOAD_FAILED"

        fun startDownload(ctx: Context, url: String, title: String, format: VideoFormat): String {
            val taskId = UUID.randomUUID().toString()
            val intent = Intent(ctx, DownloadService::class.java).apply {
                action = ACTION_START
                putExtra(EXTRA_URL, url)
                putExtra(EXTRA_TITLE, title)
                putExtra(EXTRA_FORMAT, format)
                putExtra(EXTRA_TASK_ID, taskId)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ctx.startForegroundService(intent)
            } else {
                ctx.startService(intent)
            }
            return taskId
        }
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val activeTasks = ConcurrentHashMap<String, Job>()

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
        YtDlpManager.init(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                val url     = intent.getStringExtra(EXTRA_URL) ?: return START_NOT_STICKY
                val title   = intent.getStringExtra(EXTRA_TITLE) ?: "Video"
                val format  = intent.getParcelableExtra<VideoFormat>(EXTRA_FORMAT)
                    ?: return START_NOT_STICKY
                val taskId  = intent.getStringExtra(EXTRA_TASK_ID) ?: UUID.randomUUID().toString()

                startForeground(NOTIF_ID_FOREGROUND, buildForegroundNotif("Preparing download…"))
                enqueueDownload(taskId, url, title, format)
            }
            ACTION_CANCEL -> {
                val taskId = intent.getStringExtra(EXTRA_TASK_ID) ?: return START_NOT_STICKY
                cancelDownload(taskId)
            }
        }
        return START_NOT_STICKY
    }

    private fun enqueueDownload(taskId: String, url: String, title: String, format: VideoFormat) {
        val job = scope.launch {
            val outputDir = getOutputDir(format.isAudioOnly)

            broadcastProgress(taskId, 0f, "Starting…")

            val result = YtDlpManager.download(
                url = url,
                format = format,
                outputDir = outputDir
            ) { progress, eta, line ->
                val cleanLine = line.take(120)
                broadcastProgress(taskId, progress, cleanLine)
                updateProgressNotif(title, progress.toInt())
            }

            result.fold(
                onSuccess = { file ->
                    broadcastDone(taskId, file.absolutePath)
                    showCompleteNotif(title, file)
                },
                onFailure = { err ->
                    broadcastFailed(taskId, err.message ?: "Unknown error")
                    showErrorNotif(title, err.message ?: "Download failed")
                }
            )

            activeTasks.remove(taskId)
            if (activeTasks.isEmpty()) {
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
        activeTasks[taskId] = job
    }

    private fun cancelDownload(taskId: String) {
        activeTasks[taskId]?.cancel()
        activeTasks.remove(taskId)
        broadcastProgress(taskId, -1f, "Cancelled")
    }

    private fun getOutputDir(audioOnly: Boolean): File {
        val subDir = if (audioOnly) "VideoDownloader/Audio" else "VideoDownloader/Video"
        val dir = File(getExternalFilesDir(null), subDir)
        dir.mkdirs()
        return dir
    }

    // ─── Broadcasts ───────────────────────────────────────────────────────────

    private fun broadcastProgress(taskId: String, progress: Float, status: String) {
        sendBroadcast(Intent(ACTION_PROGRESS).apply {
            putExtra(EXTRA_TASK_ID, taskId)
            putExtra("progress", progress)
            putExtra("status", status)
            setPackage(packageName)
        })
    }

    private fun broadcastDone(taskId: String, filePath: String) {
        sendBroadcast(Intent(ACTION_DONE).apply {
            putExtra(EXTRA_TASK_ID, taskId)
            putExtra("file_path", filePath)
            setPackage(packageName)
        })
    }

    private fun broadcastFailed(taskId: String, error: String) {
        sendBroadcast(Intent(ACTION_FAILED).apply {
            putExtra(EXTRA_TASK_ID, taskId)
            putExtra("error", error)
            setPackage(packageName)
        })
    }

    // ─── Notifications ────────────────────────────────────────────────────────

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(NotificationChannel(
                NOTIF_CHANNEL_ID, "Downloads", NotificationManager.IMPORTANCE_LOW
            ).apply { description = "Active download notifications" })
            nm.createNotificationChannel(NotificationChannel(
                NOTIF_CHANNEL_PROGRESS, "Download Completion", NotificationManager.IMPORTANCE_DEFAULT
            ).apply { description = "Download finished notifications" })
        }
    }

    private fun buildForegroundNotif(text: String): Notification {
        val intent = Intent(this, DownloadsActivity::class.java)
        val pi = PendingIntent.getActivity(this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(this, NOTIF_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("Video Downloader")
            .setContentText(text)
            .setContentIntent(pi)
            .setOngoing(true)
            .build()
    }

    private fun updateProgressNotif(title: String, progress: Int) {
        val nm = getSystemService(NotificationManager::class.java)
        val notif = NotificationCompat.Builder(this, NOTIF_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("Downloading: $title")
            .setContentText("$progress%")
            .setProgress(100, progress, progress == 0)
            .setOngoing(true)
            .build()
        nm.notify(NOTIF_ID_FOREGROUND, notif)
    }

    private fun showCompleteNotif(title: String, file: File) {
        val nm = getSystemService(NotificationManager::class.java)
        val notif = NotificationCompat.Builder(this, NOTIF_CHANNEL_PROGRESS)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle("Download complete")
            .setContentText(title)
            .setAutoCancel(true)
            .build()
        nm.notify(file.hashCode(), notif)
    }

    private fun showErrorNotif(title: String, error: String) {
        val nm = getSystemService(NotificationManager::class.java)
        val notif = NotificationCompat.Builder(this, NOTIF_CHANNEL_PROGRESS)
            .setSmallIcon(android.R.drawable.stat_notify_error)
            .setContentTitle("Download failed: $title")
            .setContentText(error.take(100))
            .setAutoCancel(true)
            .build()
        nm.notify((title + error).hashCode(), notif)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
    }
}
