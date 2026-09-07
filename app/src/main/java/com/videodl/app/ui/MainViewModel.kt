package com.videodl.app.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.viewModelScope
import com.videodl.app.download.VideoInfo
import com.videodl.app.download.YtDlpManager
import com.videodl.app.utils.PlatformDetector
import kotlinx.coroutines.launch

sealed class UiState {
    object Idle : UiState()
    object Loading : UiState()
    data class Success(val info: VideoInfo) : UiState()
    data class Error(val message: String) : UiState()
}

class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val _uiState = MutableLiveData<UiState>(UiState.Idle)
    val uiState: LiveData<UiState> = _uiState

    private val _detectedPlatform = MutableLiveData<PlatformDetector.PlatformInfo?>()
    val detectedPlatform: LiveData<PlatformDetector.PlatformInfo?> = _detectedPlatform

    init {
        YtDlpManager.init(app)
    }

    fun onUrlChanged(url: String) {
        if (PlatformDetector.isValidUrl(url)) {
            _detectedPlatform.value = PlatformDetector.detect(url)
        } else {
            _detectedPlatform.value = null
        }
    }

    fun fetchInfo(url: String) {
        if (!PlatformDetector.isValidUrl(url)) {
            _uiState.value = UiState.Error("Please enter a valid URL starting with http:// or https://")
            return
        }

        _uiState.value = UiState.Loading

        viewModelScope.launch {
            val result = YtDlpManager.fetchVideoInfo(url)
            _uiState.value = result.fold(
                onSuccess = { UiState.Success(it) },
                onFailure = { UiState.Error(it.message ?: "Failed to fetch video info") }
            )
        }
    }

    fun reset() {
        _uiState.value = UiState.Idle
        _detectedPlatform.value = null
    }
}
