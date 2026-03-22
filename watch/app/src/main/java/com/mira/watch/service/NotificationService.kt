package com.mira.watch.service

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.VibrationEffect
import android.os.Vibrator
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.mira.watch.MainActivity
import com.mira.watch.MiraWatchApplication

/**
 * Manages discreet Mira alert notifications on the watch.
 *
 * Design principles:
 *  - Gentle vibration patterns (not jarring buzzes)
 *  - Minimal text on the watch face
 *  - Priority levels: LOW (info), MEDIUM (action needed), HIGH (urgent)
 *  - All alerts are brief — details available on phone/desktop
 */
object NotificationService {

    private const val TAG = "MiraNotify"
    private var notificationCounter = 1000

    /**
     * Vibration patterns for different alert priorities.
     * Designed to be discreet — gentle taps rather than aggressive buzzes.
     */
    enum class AlertPriority(val vibrationPattern: LongArray, val amplitude: Int) {
        LOW(
            vibrationPattern = longArrayOf(0, 80),
            amplitude = 60    // single gentle tap
        ),
        MEDIUM(
            vibrationPattern = longArrayOf(0, 80, 100, 80),
            amplitude = 100   // double tap
        ),
        HIGH(
            vibrationPattern = longArrayOf(0, 100, 80, 100, 80, 150),
            amplitude = 180   // triple tap with emphasis
        )
    }

    /**
     * Show a discreet alert notification with gentle haptic feedback.
     */
    fun showDiscreetAlert(
        context: Context,
        title: String,
        body: String,
        priority: AlertPriority = AlertPriority.MEDIUM
    ) {
        try {
            // Haptic first — user feels the alert before seeing it
            triggerHaptic(context, priority)

            val pendingIntent = PendingIntent.getActivity(
                context, 0,
                Intent(context, MainActivity::class.java),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
            )

            val notificationId = notificationCounter++
            val notification = NotificationCompat.Builder(
                context,
                MiraWatchApplication.CHANNEL_ALERTS
            )
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(title)
                .setContentText(body)
                .setContentIntent(pendingIntent)
                .setAutoCancel(true)
                .setCategory(NotificationCompat.CATEGORY_MESSAGE)
                .setPriority(
                    when (priority) {
                        AlertPriority.LOW -> NotificationCompat.PRIORITY_LOW
                        AlertPriority.MEDIUM -> NotificationCompat.PRIORITY_DEFAULT
                        AlertPriority.HIGH -> NotificationCompat.PRIORITY_HIGH
                    }
                )
                // Keep it minimal on the watch face
                .setStyle(
                    NotificationCompat.BigTextStyle().bigText(body)
                )
                .build()

            NotificationManagerCompat.from(context).notify(notificationId, notification)
            Log.i(TAG, "Alert shown: $title ($priority)")

        } catch (e: SecurityException) {
            Log.e(TAG, "Missing POST_NOTIFICATIONS permission", e)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to show notification", e)
        }
    }

    /**
     * Show a mood check-in prompt notification.
     */
    fun showMoodCheckPrompt(context: Context) {
        try {
            val pendingIntent = PendingIntent.getActivity(
                context, 0,
                Intent(context, MainActivity::class.java).apply {
                    putExtra("navigate_to", "mood_check")
                },
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
            )

            val notification = NotificationCompat.Builder(
                context,
                MiraWatchApplication.CHANNEL_MOOD
            )
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle("Mira")
                .setContentText("Quick mood check?")
                .setContentIntent(pendingIntent)
                .setAutoCancel(true)
                .build()

            NotificationManagerCompat.from(context).notify(2000, notification)

            // Gentle single tap
            triggerHaptic(context, AlertPriority.LOW)

        } catch (e: Exception) {
            Log.e(TAG, "Failed to show mood prompt", e)
        }
    }

    /**
     * Trigger a discreet haptic pattern.
     */
    private fun triggerHaptic(context: Context, priority: AlertPriority) {
        try {
            val vibrator = context.getSystemService(Vibrator::class.java)
            if (vibrator?.hasVibrator() == true) {
                val effect = VibrationEffect.createWaveform(
                    priority.vibrationPattern,
                    intArrayOf(0, priority.amplitude, 0, priority.amplitude, 0, priority.amplitude),
                    -1  // no repeat
                )
                vibrator.vibrate(effect)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Haptic failed", e)
        }
    }
}
