package com.mira.watch.presentation

import android.os.VibrationEffect
import android.os.Vibrator
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.foundation.lazy.items
import androidx.wear.compose.foundation.lazy.rememberScalingLazyListState
import androidx.wear.compose.material3.Button
import androidx.wear.compose.material3.ButtonDefaults
import androidx.wear.compose.material3.MaterialTheme
import androidx.wear.compose.material3.Text
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

data class QuickCommand(
    val id: String,
    val label: String,
    val payload: String    // sent to Mira agent via DataLayer
)

private val defaultCommands = listOf(
    QuickCommand("hold_trades", "Hold all trades", "command:hold_trades"),
    QuickCommand("in_meeting", "I'm in a meeting", "command:in_meeting"),
    QuickCommand("focus_mode", "Focus mode on", "command:focus_mode"),
    QuickCommand("resume", "Resume normal ops", "command:resume"),
    QuickCommand("brain_dump", "Start brain dump", "command:brain_dump"),
    QuickCommand("morning_brief", "Morning briefing", "command:morning_brief"),
    QuickCommand("killswitch", "Kill switch", "command:killswitch"),
)

@Composable
fun QuickCommandsScreen(onDone: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val listState = rememberScalingLazyListState()
    var sentCommand by remember { mutableStateOf<String?>(null) }

    ScalingLazyColumn(
        modifier = Modifier.fillMaxSize(),
        state = listState,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        item {
            Text(
                text = "Commands",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(top = 24.dp, bottom = 4.dp)
            )
        }

        items(defaultCommands) { command ->
            val isSent = sentCommand == command.id
            val isKillSwitch = command.id == "killswitch"

            Button(
                onClick = {
                    scope.launch {
                        // Haptic confirmation
                        val vibrator = context.getSystemService(Vibrator::class.java)
                        vibrator?.vibrate(
                            VibrationEffect.createOneShot(50, VibrationEffect.DEFAULT_AMPLITUDE)
                        )

                        sentCommand = command.id

                        // TODO: Send command.payload via DataSyncService
                        // DataSyncService.sendCommand(context, command.payload)

                        delay(1500)
                        sentCommand = null
                    }
                },
                modifier = Modifier
                    .fillMaxWidth(0.9f)
                    .height(44.dp),
                enabled = sentCommand == null,
                colors = ButtonDefaults.buttonColors(
                    containerColor = when {
                        isSent -> MaterialTheme.colorScheme.primary.copy(alpha = 0.5f)
                        isKillSwitch -> MaterialTheme.colorScheme.error
                        else -> MaterialTheme.colorScheme.primaryContainer
                    }
                )
            ) {
                Text(
                    text = if (isSent) "Sent!" else command.label,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}
