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
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.musicdownloader.store.MenuOrderStore
import com.musicdownloader.ui.screens.AudioSearchScreen
import com.musicdownloader.ui.screens.Top100Screen
import com.musicdownloader.ui.screens.UrlScreen
import com.musicdownloader.ui.screens.VideoSearchScreen
import com.musicdownloader.ui.screens.SettingsScreen

private val ICONS: Map<String, ImageVector> = mapOf(
    "top100" to Icons.Default.Home,
    "audio" to Icons.Default.Search,
    "video" to Icons.Default.PlayArrow,
    "url" to Icons.Default.Share,
)

@Composable
fun AppNav(initialSharedUrl: String = "") {
    val ctx = LocalContext.current
    val order by MenuOrderStore.flow(ctx).collectAsState(initial = MenuOrderStore.DEFAULT)
    val nav = rememberNavController()
    val routes = (order + "settings").distinct()
    Scaffold(bottomBar = {
        NavigationBar {
            val back by nav.currentBackStackEntryAsState()
            val cur = back?.destination?.route
            routes.forEach { route ->
                val label = if (route == "settings") "설정" else MenuOrderStore.LABELS[route] ?: route
                val icon = if (route == "settings") Icons.Default.Settings else ICONS[route] ?: Icons.Default.Home
                NavigationBarItem(
                    selected = cur == route,
                    onClick = { nav.navigate(route) { launchSingleTop = true } },
                    icon = { Icon(icon, contentDescription = label) },
                    label = { Text(label) }
                )
            }
        }
    }) { pad ->
        NavHost(nav, startDestination = routes.firstOrNull() ?: "audio", modifier = Modifier.padding(pad)) {
            composable("top100") { Top100Screen() }
            composable("audio") { AudioSearchScreen() }
            composable("video") { VideoSearchScreen() }
            composable("url") { UrlScreen(initialUrl = initialSharedUrl) }
            composable("settings") { SettingsScreen() }
        }
    }
}
