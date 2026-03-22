package com.mira.watch.service

import android.content.Context
import android.util.Log
import com.google.android.gms.wearable.DataClient
import com.google.android.gms.wearable.DataMap
import com.google.android.gms.wearable.MessageClient
import com.google.android.gms.wearable.MessageEvent
import com.google.android.gms.wearable.PutDataMapRequest
import com.google.android.gms.wearable.Wearable
import com.google.android.gms.wearable.WearableListenerService
import com.google.gson.Gson
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

/**
 * Handles bidirectional data sync between watch and phone/desktop
 * via the Wearable DataLayer API.
 *
 * Outbound (watch -> phone/desktop):
 *  - Voice recordings (thought capture, brain dump)
 *  - Mood check-in values
 *  - Quick commands
 *  - Biometric data batches
 *
 * Inbound (phone/desktop -> watch):
 *  - Mira alert notifications
 *  - Mood check-in prompts
 *  - Updated quick command list
 *  - Configuration changes
 *
 * All heavy processing (STT, analysis) happens on desktop.
 * Watch only captures and relays raw data.
 */
class DataSyncService : WearableListenerService() {

    companion object {
        private const val TAG = "MiraDataSync"
        private val gson = Gson()

        // Message paths
        const val PATH_COMMAND = "/mira/command"
        const val PATH_MOOD = "/mira/mood"
        const val PATH_THOUGHT = "/mira/thought"
        const val PATH_BIOMETRIC = "/mira/biometric"
        const val PATH_ALERT = "/mira/alert"

        // Data paths (for larger payloads via DataLayer)
        const val DATA_VOICE_RECORDING = "/mira/voice_recording"
        const val DATA_BIOMETRIC_BATCH = "/mira/biometric_batch"

        private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

        /**
         * Send a quick command to the phone/desktop agent.
         */
        fun sendCommand(context: Context, command: String) {
            scope.launch {
                try {
                    val client: MessageClient = Wearable.getMessageClient(context)
                    val nodes = Wearable.getNodeClient(context).connectedNodes.await()

                    for (node in nodes) {
                        client.sendMessage(
                            node.id,
                            PATH_COMMAND,
                            command.toByteArray(Charsets.UTF_8)
                        ).await()
                        Log.i(TAG, "Command sent to ${node.displayName}: $command")
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to send command", e)
                }
            }
        }

        /**
         * Send a mood check-in value (1-5).
         */
        fun sendMood(context: Context, moodValue: Int) {
            scope.launch {
                try {
                    val payload = mapOf(
                        "mood" to moodValue,
                        "timestamp" to System.currentTimeMillis()
                    )
                    val bytes = gson.toJson(payload).toByteArray(Charsets.UTF_8)
                    val client = Wearable.getMessageClient(context)
                    val nodes = Wearable.getNodeClient(context).connectedNodes.await()

                    for (node in nodes) {
                        client.sendMessage(node.id, PATH_MOOD, bytes).await()
                    }
                    Log.i(TAG, "Mood sent: $moodValue")
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to send mood", e)
                }
            }
        }

        /**
         * Send a voice recording as a DataItem (supports larger payloads).
         */
        fun sendVoiceRecording(context: Context, audioBytes: ByteArray, durationMs: Long) {
            scope.launch {
                try {
                    val dataClient: DataClient = Wearable.getDataClient(context)
                    val request = PutDataMapRequest.create(DATA_VOICE_RECORDING).apply {
                        dataMap.putByteArray("audio", audioBytes)
                        dataMap.putLong("duration_ms", durationMs)
                        dataMap.putLong("timestamp", System.currentTimeMillis())
                        dataMap.putString("format", "pcm_16bit_16khz")
                    }.asPutDataRequest().setUrgent()

                    dataClient.putDataItem(request).await()
                    Log.i(TAG, "Voice recording sent: ${audioBytes.size} bytes")
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to send voice recording", e)
                }
            }
        }

        /**
         * Send biometric data batch to phone/desktop.
         */
        fun sendBiometricData(context: Context, data: Map<String, Any>) {
            scope.launch {
                try {
                    val json = gson.toJson(data)
                    val client = Wearable.getMessageClient(context)
                    val nodes = Wearable.getNodeClient(context).connectedNodes.await()

                    for (node in nodes) {
                        client.sendMessage(
                            node.id,
                            PATH_BIOMETRIC,
                            json.toByteArray(Charsets.UTF_8)
                        ).await()
                    }
                    Log.d(TAG, "Biometric batch sent: ${json.length} chars")
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to send biometric data", e)
                }
            }
        }
    }

    /**
     * Handle inbound messages from phone/desktop.
     */
    override fun onMessageReceived(messageEvent: MessageEvent) {
        Log.i(TAG, "Message received on path: ${messageEvent.path}")

        when (messageEvent.path) {
            PATH_ALERT -> {
                val alertJson = String(messageEvent.data, Charsets.UTF_8)
                handleIncomingAlert(alertJson)
            }
        }
    }

    private fun handleIncomingAlert(alertJson: String) {
        try {
            val alert = gson.fromJson(alertJson, Map::class.java)
            val title = alert["title"] as? String ?: "Mira"
            val body = alert["body"] as? String ?: ""

            NotificationService.showDiscreetAlert(
                context = this,
                title = title,
                body = body
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed to handle alert", e)
        }
    }
}
