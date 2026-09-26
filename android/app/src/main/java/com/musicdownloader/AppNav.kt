package com.musicdownloader

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.musicdownloader.ui.screens.AudioSearchScreen
import com.musicdownloader.ui.screens.Top100Screen
import com.musicdownloader.ui.screens.UrlScreen
import com.musicdownloader.ui.screens.VideoSearchScreen
import com.musicdownloader.ui.screens.SettingsScreen

@Composable
fun AppNav(initialSharedUrl: String = "") {
    val nav = rememberNavController()
    val items = listOf(
        Triple("top100", "TOP100", Icons.Default.Home),
        Triple("audio", "MP3", Icons.Default.Search),
        Triple("video", "MP4", Icons.Default.PlayArrow),
        Triple("url", "URL", Icons.Default.Share),
        Triple("settings", "설정", Icons.Default.Settings),
    )
    Scaffold(bottomBar = {
        NavigationBar {
            val back by nav.currentBackStackEntryAsState()
            val cur = back?.destination?.route
            items.forEach { (route, label, icon) ->
                NavigationBarItem(
                    selected = cur == route,
                    onClick = { nav.navigate(route) { launchSingleTop = true } },
                    icon = { Icon(icon, contentDescription = label) },
                    label = { Text(label) }
                )
            }
        }
    }) { pad ->
        NavHost(nav, startDestination = "top100", modifier = Modifier.padding(pad)) {
            composable("top100") { Top100Screen() }
            composable("audio") { AudioSearchScreen() }
            composable("video") { VideoSearchScreen() }
            composable("url") { UrlScreen(initialUrl = initialSharedUrl) }
            composable("settings") { SettingsScreen() }
        }
    }
}
