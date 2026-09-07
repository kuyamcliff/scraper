package com.videodl.app.ui

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.videodl.app.databinding.ItemFormatBinding
import com.videodl.app.download.VideoFormat

class FormatAdapter(
    private val formats: List<VideoFormat>,
    private val onDownload: (VideoFormat) -> Unit
) : RecyclerView.Adapter<FormatAdapter.FormatViewHolder>() {

    inner class FormatViewHolder(private val b: ItemFormatBinding)
        : RecyclerView.ViewHolder(b.root) {

        fun bind(format: VideoFormat) {
            b.tvQuality.text    = format.displayQuality
            b.tvCodec.text      = format.codecInfo
            b.tvSize.text       = format.displaySize
            b.tvFormatId.text   = format.formatId

            // Tag audio-only rows differently
            if (format.isAudioOnly) {
                b.root.setCardBackgroundColor(
                    b.root.context.getColor(android.R.color.transparent)
                )
                b.tvQualityBadge.text = "AUDIO"
                b.tvQualityBadge.setBackgroundColor(
                    android.graphics.Color.parseColor("#FF5722")
                )
            } else {
                b.tvQualityBadge.text = when {
                    format.qualityLabel.startsWith("4K") -> "4K"
                    format.qualityLabel.startsWith("1440") -> "2K"
                    format.qualityLabel.startsWith("1080") -> "FHD"
                    format.qualityLabel.startsWith("720")  -> "HD"
                    else -> "SD"
                }
                b.tvQualityBadge.setBackgroundColor(
                    when (b.tvQualityBadge.text) {
                        "4K"  -> android.graphics.Color.parseColor("#9C27B0")
                        "2K"  -> android.graphics.Color.parseColor("#3F51B5")
                        "FHD" -> android.graphics.Color.parseColor("#2196F3")
                        "HD"  -> android.graphics.Color.parseColor("#4CAF50")
                        else  -> android.graphics.Color.parseColor("#607D8B")
                    }
                )
            }

            b.btnDownload.setOnClickListener { onDownload(format) }
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): FormatViewHolder {
        val binding = ItemFormatBinding.inflate(
            LayoutInflater.from(parent.context), parent, false)
        return FormatViewHolder(binding)
    }

    override fun onBindViewHolder(holder: FormatViewHolder, position: Int) {
        holder.bind(formats[position])
    }

    override fun getItemCount() = formats.size
}
