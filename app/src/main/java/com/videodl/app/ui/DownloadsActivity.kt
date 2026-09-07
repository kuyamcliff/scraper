package com.videodl.app.ui

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Bundle
import android.view.MenuItem
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.LinearLayoutManager
import com.videodl.app.databinding.ActivityDownloadsBinding
import com.videodl.app.download.DownloadService
import com.videodl.app.download.DownloadStatus
import com.videodl.app.download.DownloadTask
import com.videodl.app.download.VideoFormat
import java.util.UUID

class DownloadsActivity : AppCompatActivity() {

    private lateinit var binding: ActivityDownloadsBinding
    private val tasks = mutableListOf<DownloadTask>()
    private lateinit var adapter: DownloadTaskAdapter

    private val progressReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            val taskId  = intent.getStringExtra(DownloadService.EXTRA_TASK_ID) ?: return
            val task    = tasks.find { it.id == taskId } ?: return
            val idx     = tasks.indexOf(task)

            when (intent.action) {
                DownloadService.ACTION_PROGRESS -> {
                    val progress = intent.getFloatExtra("progress", 0f)
                    val status   = intent.getStringExtra("status") ?: ""
                    task.progress = progress
                    task.status   = DownloadStatus.DOWNLOADING
                    task.speed    = status
                    adapter.notifyItemChanged(idx)
                }
                DownloadService.ACTION_DONE -> {
                    val filePath = intent.getStringExtra("file_path") ?: ""
                    task.status   = DownloadStatus.DONE
                    task.progress = 100f
                    task.filePath = filePath
                    adapter.notifyItemChanged(idx)
                }
                DownloadService.ACTION_FAILED -> {
                    val error = intent.getStringExtra("error") ?: "Unknown"
                    task.status   = DownloadStatus.FAILED
                    task.errorMsg = error
                    adapter.notifyItemChanged(idx)
                }
            }

            updateEmptyState()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityDownloadsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbar)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        supportActionBar?.title = "Downloads"

        adapter = DownloadTaskAdapter(tasks)
        binding.rvDownloads.layoutManager = LinearLayoutManager(this)
        binding.rvDownloads.adapter = adapter

        updateEmptyState()
    }

    override fun onResume() {
        super.onResume()
        val filter = IntentFilter().apply {
            addAction(DownloadService.ACTION_PROGRESS)
            addAction(DownloadService.ACTION_DONE)
            addAction(DownloadService.ACTION_FAILED)
        }
        ContextCompat.registerReceiver(this, progressReceiver, filter,
            ContextCompat.RECEIVER_NOT_EXPORTED)
    }

    override fun onPause() {
        super.onPause()
        unregisterReceiver(progressReceiver)
    }

    private fun updateEmptyState() {
        binding.tvEmpty.visibility = if (tasks.isEmpty()) View.VISIBLE else View.GONE
        binding.rvDownloads.visibility = if (tasks.isEmpty()) View.GONE else View.VISIBLE
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == android.R.id.home) { onBackPressedDispatcher.onBackPressed(); return true }
        return super.onOptionsItemSelected(item)
    }
}
