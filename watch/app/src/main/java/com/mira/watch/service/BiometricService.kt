package com.mira.watch.service

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.health.services.client.ExerciseUpdateCallback
import androidx.health.services.client.HealthServices
import androidx.health.services.client.HealthServicesClient
import androidx.health.services.client.PassiveListenerCallback
import androidx.health.services.client.PassiveMonitoringClient
import androidx.health.services.client.data.Availability
import androidx.health.services.client.data.DataPointContainer
import androidx.health.services.client.data.DataType
import androidx.health.services.client.data.ExerciseUpdate
import androidx.health.services.client.data.PassiveListenerConfig
import com.mira.watch.MainActivity
import com.mira.watch.MiraWatchApplication
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Collects biometric data via Health Services API and forwards it
 * to the phone/desktop through DataSyncService.
 *
 * Collected metrics:
 * - Heart rate (real-time when available)
 * - Heart rate variability (HRV)
 * - Daily step count
 * - Sleep stages (when sleep tracking is active)
 *
 * Battery-aware: uses passive monitoring (low power) rather than
 * active exercise sessions. Heavy processing is offloaded to desktop.
 */
class BiometricService : Service() {

    companion object {
        private const val TAG = "MiraBiometric"
        private const val NOTIFICATION_ID = 100
        private const val SYNC_INTERVAL_MS = 5 * 60 * 1000L  // 5 minutes

        fun start(context: Context) {
            val intent = Intent(context, BiometricService::class.java)
            context.startForegroundService(intent)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, BiometricService::class.java))
        }
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private lateinit var passiveClient: PassiveMonitoringClient

    // Buffered readings to batch-send
    private val heartRateBuffer = mutableListOf<Pair<Long, Double>>()  // timestamp, bpm
    private val stepBuffer = mutableListOf<Pair<Long, Long>>()          // timestamp, steps
    private val hrvBuffer = mutableListOf<Pair<Long, Double>>()         // timestamp, ms

    override fun onCreate() {
        super.onCreate()
        val healthClient: HealthServicesClient = HealthServices.getClient(this)
        passiveClient = healthClient.passiveMonitoringClient
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, buildNotification())
        registerPassiveListeners()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        scope.cancel()
        unregisterPassiveListeners()
        super.onDestroy()
    }

    private fun registerPassiveListeners() {
        scope.launch {
            try {
                val config = PassiveListenerConfig.builder()
                    .setDataTypes(
                        setOf(
                            DataType.HEART_RATE_BPM,
                            DataType.STEPS_DAILY,
                        )
                    )
                    .build()

                passiveClient.setPassiveListenerCallback(config, passiveCallback)
                Log.i(TAG, "Passive biometric listeners registered")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to register passive listeners", e)
            }
        }
    }

    private fun unregisterPassiveListeners() {
        scope.launch {
            try {
                passiveClient.clearPassiveListenerCallbackAsync()
                Log.i(TAG, "Passive listeners cleared")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to clear passive listeners", e)
            }
        }
    }

    private val passiveCallback = object : PassiveListenerCallback {
        override fun onNewDataPointsReceived(dataPoints: DataPointContainer) {
            // Heart rate
            dataPoints.getData(DataType.HEART_RATE_BPM).forEach { dp ->
                val bpm = dp.value
                val ts = System.currentTimeMillis()
                synchronized(heartRateBuffer) {
                    heartRateBuffer.add(ts to bpm)
                }
                Log.d(TAG, "HR: $bpm bpm")
            }

            // Steps
            dataPoints.getData(DataType.STEPS_DAILY).forEach { dp ->
                val steps = dp.value
                val ts = System.currentTimeMillis()
                synchronized(stepBuffer) {
                    stepBuffer.add(ts to steps)
                }
                Log.d(TAG, "Steps: $steps")
            }

            // Batch sync if enough data accumulated
            maybeFlushToDesktop()
        }
    }

    private fun maybeFlushToDesktop() {
        scope.launch {
            val payload = buildSyncPayload() ?: return@launch
            DataSyncService.sendBiometricData(this@BiometricService, payload)
        }
    }

    private fun buildSyncPayload(): Map<String, Any>? {
        val data = mutableMapOf<String, Any>()
        var hasData = false

        synchronized(heartRateBuffer) {
            if (heartRateBuffer.isNotEmpty()) {
                data["heart_rate"] = heartRateBuffer.toList()
                heartRateBuffer.clear()
                hasData = true
            }
        }
        synchronized(stepBuffer) {
            if (stepBuffer.isNotEmpty()) {
                data["steps"] = stepBuffer.toList()
                stepBuffer.clear()
                hasData = true
            }
        }
        synchronized(hrvBuffer) {
            if (hrvBuffer.isNotEmpty()) {
                data["hrv"] = hrvBuffer.toList()
                hrvBuffer.clear()
                hasData = true
            }
        }

        return if (hasData) data else null
    }

    private fun buildNotification(): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, MiraWatchApplication.CHANNEL_BIOMETRIC)
            .setContentTitle("Mira Health")
            .setContentText("Tracking biometrics")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }
}
