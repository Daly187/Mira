package com.mira.watch

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class MiraWatchApplication : Application() {

    companion object {
        const val CHANNEL_ALERTS = "mira_alerts"
        const val CHANNEL_MOOD = "mira_mood"
        const val CHANNEL_BIOMETRIC = "mira_biometric"
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }

    private fun createNotificationChannels() {
        val manager = getSystemService(NotificationManager::class.java)

        val alertChannel = NotificationChannel(
            CHANNEL_ALERTS,
            "Mira Alerts",
            NotificationManager.IMPORTANCE_LOW  // discreet vibration only
        ).apply {
            description = "Key event notifications from Mira"
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 100, 50, 100) // gentle double-tap
            setShowBadge(false)
        }

        val moodChannel = NotificationChannel(
            CHANNEL_MOOD,
            "Mood Check-ins",
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = "Twice-daily mood check-in prompts"
        }

        val biometricChannel = NotificationChannel(
            CHANNEL_BIOMETRIC,
            "Biometric Tracking",
            NotificationManager.IMPORTANCE_MIN
        ).apply {
            description = "Background biometric data collection"
        }

        manager.createNotificationChannels(
            listOf(alertChannel, moodChannel, biometricChannel)
        )
    }
}
