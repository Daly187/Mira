package com.mira.watch.presentation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.wear.compose.material3.Button
import androidx.wear.compose.material3.ButtonDefaults
import androidx.wear.compose.material3.MaterialTheme
import androidx.wear.compose.material3.Text
import com.mira.watch.theme.MiraError
import com.mira.watch.theme.MiraPurple
import com.mira.watch.theme.MiraPurpleLight
import com.mira.watch.theme.MiraSuccess
import kotlinx.coroutines.delay

private val moodLabels = listOf("Rough", "Low", "Okay", "Good", "Great")
private val moodColors = listOf(
    Color(0xFFE74C3C),  // 1 - red
    Color(0xFFE67E22),  // 2 - orange
    Color(0xFFF1C40F),  // 3 - yellow
    Color(0xFF2ECC71),  // 4 - green
    Color(0xFF9B59B6),  // 5 - purple (Mira brand)
)

@Composable
fun MoodCheckScreen(onDone: () -> Unit) {
    var selectedMood by remember { mutableIntStateOf(0) } // 0 = none selected
    var submitted by remember { mutableStateOf(false) }

    // Auto-dismiss after submission
    LaunchedEffect(submitted) {
        if (submitted) {
            delay(1500)
            onDone()
        }
    }

    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        if (submitted) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text(
                    text = moodLabels[selectedMood - 1],
                    style = MaterialTheme.typography.titleMedium,
                    color = moodColors[selectedMood - 1]
                )
                Text(
                    text = "Logged",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        } else {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.padding(horizontal = 8.dp)
            ) {
                Text(
                    text = "How are you\nfeeling?",
                    style = MaterialTheme.typography.bodyMedium,
                    textAlign = TextAlign.Center,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.padding(top = 16.dp)
                )

                // First row: 1, 2, 3
                Row(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    for (i in 1..3) {
                        MoodButton(
                            value = i,
                            color = moodColors[i - 1],
                            isSelected = selectedMood == i,
                            onClick = {
                                selectedMood = i
                                submitted = true
                                // TODO: Send mood via DataSyncService
                            }
                        )
                    }
                }

                // Second row: 4, 5
                Row(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    for (i in 4..5) {
                        MoodButton(
                            value = i,
                            color = moodColors[i - 1],
                            isSelected = selectedMood == i,
                            onClick = {
                                selectedMood = i
                                submitted = true
                                // TODO: Send mood via DataSyncService
                            }
                        )
                    }
                }

                Text(
                    text = "Tap to log",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun MoodButton(
    value: Int,
    color: Color,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    Button(
        onClick = onClick,
        modifier = Modifier.size(42.dp),
        shape = CircleShape,
        colors = ButtonDefaults.buttonColors(
            containerColor = if (isSelected) color else color.copy(alpha = 0.3f)
        )
    ) {
        Text(
            text = "$value",
            style = MaterialTheme.typography.titleMedium,
            color = Color.White
        )
    }
}
