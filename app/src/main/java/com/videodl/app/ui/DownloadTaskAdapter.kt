package com.videodl.app.ui

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.videodl.app.databinding.ItemDownloadTaskBinding
import com.videodl.app.download.DownloadStatus
import com.videodl.app.download.DownloadTask

class DownloadTaskAdapter(
    private val tasks: List<DownloadTask>
) : RecyclerView.Adapter<DownloadTaskAdapter.TaskViewHolder>() {

    inner class TaskViewHolder(private val b: ItemDownloadTaskBinding)
        : RecyclerView.ViewHolder(b.root) {

        fun bind(task: DownloadTask) {
            b.tvTaskTitle.text  = task.title.take(60)
            b.tvTaskFormat.text = task.format.displayQuality

            when (task.status) {
                DownloadStatus.QUEUED -> {
                    b.tvTaskStatus.text = "⏳ Queued"
                    b.progressTask.progress = 0
                    b.progressTask.isIndeterminate = false
                }
                DownloadStatus.FETCHING_INFO -> {
                    b.tvTaskStatus.text = "🔍 Fetching info…"
                    b.progressTask.isIndeterminate = true
                }
                DownloadStatus.DOWNLOADING -> {
                    val pct = task.progress.toInt().coerceIn(0, 100)
                    b.tvTaskStatus.text = "⬇️ $pct% ${task.speed.take(40)}"
                    b.progressTask.isIndeterminate = false
                    b.progressTask.progress = pct
                }
                DownloadStatus.POST_PROCESSING -> {
                    b.tvTaskStatus.text = "⚙️ Processing…"
                    b.progressTask.isIndeterminate = true
                }
                DownloadStatus.DONE -> {
                    b.tvTaskStatus.text = "✅ Done"
                    b.progressTask.isIndeterminate = false
                    b.progressTask.progress = 100
                }
                DownloadStatus.FAILED -> {
                    b.tvTaskStatus.text = "❌ ${task.errorMsg.take(80)}"
                    b.progressTask.isIndeterminate = false
                    b.progressTask.progress = 0
                }
                DownloadStatus.CANCELLED -> {
                    b.tvTaskStatus.text = "🚫 Cancelled"
                    b.progressTask.isIndeterminate = false
                    b.progressTask.progress = 0
                }
            }
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): TaskViewHolder {
        val b = ItemDownloadTaskBinding.inflate(
            LayoutInflater.from(parent.context), parent, false)
        return TaskViewHolder(b)
    }

    override fun onBindViewHolder(holder: TaskViewHolder, position: Int) {
        holder.bind(tasks[position])
    }

    override fun getItemCount() = tasks.size
}
