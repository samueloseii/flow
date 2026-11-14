package org.flow.reader

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import org.flow.reader.data.local.MeterEntity
import org.flow.reader.ui.Banner
import org.flow.reader.ui.FlowTheme
import org.flow.reader.ui.FlowViewModel
import org.flow.reader.ui.HistoryScreen
import org.flow.reader.ui.LoginScreen
import org.flow.reader.ui.MeterListScreen
import org.flow.reader.ui.RecordReadingScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { FlowTheme { FlowAppRoot() } }
    }
}

private sealed interface Screen {
    data object Meters : Screen
    data object History : Screen
    data class Record(val meter: MeterEntity) : Screen
}

@Composable
@Suppress("UnusedMaterial3ScaffoldPaddingParameter")
private fun FlowAppRoot(vm: FlowViewModel = viewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val meters by vm.meters.collectAsStateWithLifecycle()
    val readings by vm.readings.collectAsStateWithLifecycle()
    val pending by vm.pendingCount.collectAsStateWithLifecycle()
    var screen by remember { mutableStateOf<Screen>(Screen.Meters) }
    val snackbar = remember { SnackbarHostState() }

    val savedOffline = stringResource(R.string.saved_offline)
    val saved = stringResource(R.string.saved)
    val synced = stringResource(R.string.synced)
    val syncFailed = stringResource(R.string.sync_failed)

    LaunchedEffect(state.banner) {
        val message = when (state.banner) {
            Banner.SAVED_OFFLINE -> savedOffline
            Banner.SAVED -> saved
            Banner.SYNCED -> synced
            Banner.SYNC_FAILED -> syncFailed
            Banner.NONE -> null
        }
        if (message != null) {
            snackbar.showSnackbar(message)
            vm.clearBanner()
        }
    }

    if (!state.signedIn) {
        LoginScreen(state) { email, password -> vm.signIn(email, password) }
        return
    }

    Scaffold(snackbarHost = { SnackbarHost(snackbar) }) { _ ->
        when (val current = screen) {
            Screen.Meters -> MeterListScreen(
                state = state,
                meters = meters,
                pending = pending,
                onRefresh = { vm.refresh() },
                onSelect = { screen = Screen.Record(it) },
                onHistory = { screen = Screen.History },
                onSignOut = { vm.signOut() },
            )

            Screen.History -> HistoryScreen(
                state = state,
                readings = readings,
                pending = pending,
                onBack = { screen = Screen.Meters },
                onSync = { vm.refresh() },
            )

            is Screen.Record -> RecordReadingScreen(
                meter = current.meter,
                onBack = { screen = Screen.Meters },
                onSave = { value, notes ->
                    vm.saveReading(current.meter, value, notes)
                    screen = Screen.Meters
                },
            )
        }
    }
}
