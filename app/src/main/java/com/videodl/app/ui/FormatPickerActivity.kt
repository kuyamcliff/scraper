package com.videodl.app.ui

import android.os.Bundle
import android.view.MenuItem
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.videodl.app.databinding.ActivityFormatPickerBinding
import com.videodl.app.download.DownloadService
import com.videodl.app.download.VideoFormat
import com.videodl.app.download.VideoInfo

class FormatPickerActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_VIDEO_INFO = "video_info"
    }

    private lateinit var binding: ActivityFormatPickerBinding
    private lateinit var videoInfo: VideoInfo

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityFormatPickerBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbar)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        supportActionBar?.title = "Choose Quality"

        videoInfo = intent.getParcelableExtra(EXTRA_VIDEO_INFO)
            ?: run { finish(); return }

        binding.tvPickerTitle.text = videoInfo.title
        binding.tvPickerMeta.text = buildString {
            if (videoInfo.uploader.isNotBlank()) append(videoInfo.uploader)
            if (videoInfo.durationFormatted.isNotBlank()) {
                if (isNotBlank()) append(" · ")
                append(videoInfo.durationFormatted)
            }
        }

        setupRecycler()
    }

    private fun setupRecycler() {
        val adapter = FormatAdapter(videoInfo.formats) { format ->
            startDownload(format)
        }
        binding.rvFormats.layoutManager = LinearLayoutManager(this)
        binding.rvFormats.adapter = adapter
    }

    private fun startDownload(format: VideoFormat) {
        val taskId = DownloadService.startDownload(
            ctx = this,
            url = videoInfo.url,
            title = videoInfo.title,
            format = format
        )
        Toast.makeText(this,
            "Download started: ${format.displayQuality}",
            Toast.LENGTH_SHORT).show()
        finish()
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == android.R.id.home) { onBackPressedDispatcher.onBackPressed(); return true }
        return super.onOptionsItemSelected(item)
    }
}
