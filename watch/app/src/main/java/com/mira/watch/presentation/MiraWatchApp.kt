package com.mira.watch.presentation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.foundation.lazy.rememberScalingLazyListState
import androidx.wear.compose.material3.Button
import androidx.wear.compose.material3.ButtonDefaults
import androidx.wear.compose.material3.Icon
import androidx.wear.compose.material3.MaterialTheme
import androidx.wear.compose.material3.Text
import androidx.wear.compose.navigation.SwipeDismissableNavHost
import androidx.wear.compose.navigation.composable
import androidx.wear.compose.navigation.rememberSwipeDismissableNavController

object Routes {
    const val HOME = "home"
    const val THOUGHT_CAPTURE = "thought_capture"
    const val MOOD_CHECK = "mood_check"
    const val QUICK_COMMANDS = "quick_commands"
}

@Composable
fun MiraWatchApp() {
    val navController = rememberSwipeDismissableNavController()

    SwipeDismissableNavHost(
        navController = navController,
        startDestination = Routes.HOME
    ) {
        composable(Routes.HOME) {
            HomeScreen(
                onThoughtCapture = { navController.navigate(Routes.THOUGHT_CAPTURE) },
                onMoodCheck = { navController.navigate(Routes.MOOD_CHECK) },
                onQuickCommands = { navController.navigate(Routes.QUICK_COMMANDS) }
            )
        }
        composable(Routes.THOUGHT_CAPTURE) {
            ThoughtCaptureScreen(
                onDone = { navController.popBackStack() }
            )
        }
        composable(Routes.MOOD_CHECK) {
            MoodCheckScreen(
                onDone = { navController.popBackStack() }
            )
        }
        composable(Routes.QUICK_COMMANDS) {
            QuickCommandsScreen(
                onDone = { navController.popBackStack() }
            )
        }
    }
}

@Composable
fun HomeScreen(
    onThoughtCapture: () -> Unit,
    onMoodCheck: () -> Unit,
    onQuickCommands: () -> Unit
) {
    val listState = rememberScalingLazyListState()

    ScalingLazyColumn(
        modifier = Modifier.fillMaxSize(),
        state = listState,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        item {
            Text(
                text = "Mira",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.primary,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 24.dp, bottom = 4.dp)
            )
        }

        // Quick thought capture — primary action
        item {
            Button(
                onClick = onThoughtCapture,
                modifier = Modifier
                    .fillMaxWidth(0.9f)
                    .height(48.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primary
                )
            ) {
                Text("Capture Thought")
            }
        }

        // Mood check-in
        item {
            Button(
                onClick = onMoodCheck,
                modifier = Modifier
                    .fillMaxWidth(0.9f)
                    .height(48.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                )
            ) {
                Text("Mood Check")
            }
        }

        // Quick commands
        item {
            Button(
                onClick = onQuickCommands,
                modifier = Modifier
                    .fillMaxWidth(0.9f)
                    .height(48.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                )
            ) {
                Text("Commands")
            }
        }
    }
}
