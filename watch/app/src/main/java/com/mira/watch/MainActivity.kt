package com.mira.watch

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.mira.watch.presentation.MiraWatchApp
import com.mira.watch.theme.MiraWatchTheme

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MiraWatchTheme {
                MiraWatchApp()
            }
        }
    }
}
