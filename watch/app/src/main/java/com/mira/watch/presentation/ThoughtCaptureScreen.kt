package com.mira.watch.presentation

import android.Manifest
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.wear.compose.material3.Button
import androidx.wear.compose.material3.ButtonDefaults
import androidx.wear.compose.material3.CircularProgressIndicator
import androidx.wear.compose.material3.MaterialTheme
import androidx.wear.compose.material3.Text
import kotlinx.coroutines.delay

private const val MAX_RECORDING_SECONDS = 60
private const val SAMPLE_RATE = 16000

enum class CaptureState {
    IDLE, RECORDING, SENDING, DONE, ERROR
}

@Composable
fun ThoughtCaptureScreen(onDone: () -> Unit) {
    var state by remember { mutableStateOf(CaptureState.IDLE) }
    var secondsElapsed by remember { mutableFloatStateOf(0f) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    // Timer for recording progress
    LaunchedEffect(state) {
        if (state == CaptureState.RECORDING) {
            secondsElapsed = 0f
            while (secondsElapsed < MAX_RECORDING_SECONDS && state == CaptureState.RECORDING) {
                delay(100)
                secondsElapsed += 0.1f
            }
            if (state == CaptureState.RECORDING) {
                // Auto-stop at 60s
                state = CaptureState.SENDING
            }
        }
    }

    // Auto-dismiss after done
    LaunchedEffect(state) {
        if (state == CaptureState.DONE) {
            delay(1500)
            onDone()
        }
    }

    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        when (state) {
            CaptureState.IDLE -> {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text(
                        text = "Tap to capture\na thought",
                        style = MaterialTheme.typography.bodyMedium,
                        textAlign = TextAlign.Center,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Button(
                        onClick = { state = CaptureState.RECORDING },
                        modifier = Modifier.size(64.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.primary
                        )
                    ) {
                        Text(
                            text = "\uD83C\uDF99",  // microphone emoji
                            style = MaterialTheme.typography.titleLarge
                        )
                    }
                    Text(
                        text = "60s max",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            CaptureState.RECORDING -> {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(
                            progress = { secondsElapsed / MAX_RECORDING_SECONDS },
                            modifier = Modifier.size(80.dp),
                            strokeWidth = 4.dp
                        )
                        Text(
                            text = "${secondsElapsed.toInt()}s",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                    Text(
                        text = "Recording...",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                    Button(
                        onClick = { state = CaptureState.SENDING },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.primaryContainer
                        )
                    ) {
                        Text("Done")
                    }
                }
            }

            CaptureState.SENDING -> {
                LaunchedEffect(Unit) {
                    // TODO: Send audio bytes via DataSyncService to phone/desktop
                    // For now simulate network delay
                    delay(1000)
                    state = CaptureState.DONE
                }
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(48.dp)
                    )
                    Text(
                        text = "Sending to Mira...",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            CaptureState.DONE -> {
                Text(
                    text = "Captured!",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary
                )
            }

            CaptureState.ERROR -> {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(
                        text = errorMessage ?: "Error",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                        textAlign = TextAlign.Center
                    )
                    Button(onClick = { state = CaptureState.IDLE }) {
                        Text("Retry")
                    }
                }
            }
        }
    }
}
