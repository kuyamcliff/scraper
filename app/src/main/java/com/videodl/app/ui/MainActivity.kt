package com.videodl.app.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.videodl.app.R
import com.videodl.app.databinding.ActivityMainBinding
import com.videodl.app.download.VideoInfo

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val viewModel: MainViewModel by viewModels()

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { /* permissions result handled */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbar)
        supportActionBar?.title = "Video Downloader"

        requestPermissionsIfNeeded()
        setupUI()
        observeViewModel()
        handleIncomingIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIncomingIntent(intent)
    }

    // ─── Intent / Share handling ──────────────────────────────────────────────

    private fun handleIncomingIntent(intent: Intent?) {
        when (intent?.action) {
            Intent.ACTION_SEND -> {
                val sharedText = intent.getStringExtra(Intent.EXTRA_TEXT) ?: return
                // Extract URL from shared text (may contain extra words)
                val url = extractUrl(sharedText)
                if (url != null) {
                    binding.etUrl.setText(url)
                    viewModel.fetchInfo(url)
                }
            }
            Intent.ACTION_VIEW -> {
                val url = intent.dataString ?: return
                binding.etUrl.setText(url)
                viewModel.fetchInfo(url)
            }
        }
    }

    private fun extractUrl(text: String): String? {
        return text.split("\\s+".toRegex())
            .firstOrNull { it.startsWith("http://") || it.startsWith("https://") }
            ?: if (text.startsWith("http://") || text.startsWith("https://")) text else null
    }

    // ─── UI Setup ─────────────────────────────────────────────────────────────

    private fun setupUI() {
        // URL text watcher for live platform detection
        binding.etUrl.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable) {
                viewModel.onUrlChanged(s.toString().trim())
            }
            override fun beforeTextChanged(s: CharSequence, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence, start: Int, before: Int, count: Int) {}
        })

        binding.btnPaste.setOnClickListener {
            val clipboard = getSystemService(android.content.ClipboardManager::class.java)
            val text = clipboard?.primaryClip?.getItemAt(0)?.text?.toString()?.trim()
            if (!text.isNullOrBlank()) {
                binding.etUrl.setText(text)
                if (text.startsWith("http")) {
                    viewModel.fetchInfo(text)
                }
            } else {
                Toast.makeText(this, "Clipboard is empty", Toast.LENGTH_SHORT).show()
            }
        }

        binding.btnAnalyze.setOnClickListener {
            val url = binding.etUrl.text?.toString()?.trim() ?: return@setOnClickListener
            if (url.isBlank()) {
                Toast.makeText(this, "Paste a URL first", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            viewModel.fetchInfo(url)
        }

        binding.btnClear.setOnClickListener {
            binding.etUrl.setText("")
            viewModel.reset()
        }
    }

    // ─── Observe ──────────────────────────────────────────────────────────────

    private fun observeViewModel() {
        viewModel.detectedPlatform.observe(this) { platform ->
            if (platform != null) {
                binding.tvPlatform.visibility = View.VISIBLE
                binding.tvPlatform.text = "${platform.emoji} ${platform.name}"
            } else {
                binding.tvPlatform.visibility = View.GONE
            }
        }

        viewModel.uiState.observe(this) { state ->
            when (state) {
                is UiState.Idle -> {
                    binding.progressBar.visibility = View.GONE
                    binding.cardVideoInfo.visibility = View.GONE
                    binding.tvError.visibility = View.GONE
                    binding.btnAnalyze.isEnabled = true
                }
                is UiState.Loading -> {
                    binding.progressBar.visibility = View.VISIBLE
                    binding.cardVideoInfo.visibility = View.GONE
                    binding.tvError.visibility = View.GONE
                    binding.btnAnalyze.isEnabled = false
                    binding.tvStatus.text = "Fetching video info…"
                }
                is UiState.Success -> {
                    binding.progressBar.visibility = View.GONE
                    binding.tvError.visibility = View.GONE
                    binding.btnAnalyze.isEnabled = true
                    showVideoInfo(state.info)
                }
                is UiState.Error -> {
                    binding.progressBar.visibility = View.GONE
                    binding.cardVideoInfo.visibility = View.GONE
                    binding.btnAnalyze.isEnabled = true
                    binding.tvError.visibility = View.VISIBLE
                    binding.tvError.text = "❌ ${state.message}"
                }
            }
        }
    }

    private fun showVideoInfo(info: VideoInfo) {
        binding.cardVideoInfo.visibility = View.VISIBLE
        binding.tvVideoTitle.text = info.title
        binding.tvUploader.text = info.uploader.ifBlank { info.platform }
        binding.tvDuration.text = if (info.durationFormatted.isNotBlank())
            "⏱ ${info.durationFormatted}" else ""
        binding.tvFormatCount.text = "${info.formats.size} formats available"

        // Load thumbnail
        if (info.thumbnailUrl.isNotBlank()) {
            com.bumptech.glide.Glide.with(this)
                .load(info.thumbnailUrl)
                .centerCrop()
                .placeholder(android.R.drawable.ic_media_play)
                .into(binding.ivThumbnail)
        }

        binding.tvStatus.text = "Tap 'Choose Quality' to download"

        binding.btnChooseQuality.setOnClickListener {
            val intent = Intent(this, FormatPickerActivity::class.java).apply {
                putExtra(FormatPickerActivity.EXTRA_VIDEO_INFO, info)
            }
            startActivity(intent)
        }
    }

    // ─── Permissions ──────────────────────────────────────────────────────────

    private fun requestPermissionsIfNeeded() {
        val perms = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
                perms += Manifest.permission.POST_NOTIFICATIONS
            }
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_MEDIA_VIDEO)
                != PackageManager.PERMISSION_GRANTED) {
                perms += Manifest.permission.READ_MEDIA_VIDEO
            }
        } else if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.Q) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE)
                != PackageManager.PERMISSION_GRANTED) {
                perms += Manifest.permission.WRITE_EXTERNAL_STORAGE
            }
        }
        if (perms.isNotEmpty()) permissionLauncher.launch(perms.toTypedArray())
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.main_menu, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            R.id.action_downloads -> {
                startActivity(Intent(this, DownloadsActivity::class.java))
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }
}
