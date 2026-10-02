package org.flow.reader.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.flow.reader.R
import org.flow.reader.data.local.MeterEntity

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MeterListScreen(
    state: UiState,
    meters: List<MeterEntity>,
    pending: Int,
    onRefresh: () -> Unit,
    onSelect: (MeterEntity) -> Unit,
    onHistory: () -> Unit,
    onSignOut: () -> Unit,
) {
    var query by remember { mutableStateOf("") }
    val filtered = remember(meters, query) {
        if (query.isBlank()) meters
        else meters.filter {
            it.headOfHousehold.contains(query, true) || it.accountNumber.contains(query, true)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringRes(R.string.meters)) },
                actions = {
                    IconButton(onClick = onRefresh, enabled = !state.busy) {
                        Icon(Icons.Default.Refresh, contentDescription = stringRes(R.string.refresh))
                    }
                    TextButton(onClick = onSignOut) { Text(stringRes(R.string.sign_out)) }
                },
            )
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            SyncStatusBar(state, pending, onHistory)

            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                label = { Text(stringRes(R.string.search_meters)) },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
            )

            if (filtered.isEmpty()) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        stringRes(R.string.no_meters),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(32.dp),
                    )
                }
            } else {
                LazyColumn {
                    items(filtered, key = { it.meterId }) { meter ->
                        MeterRow(meter) { onSelect(meter) }
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}

@Composable
private fun MeterRow(meter: MeterEntity, onClick: () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 14.dp)
    ) {
        Text(meter.headOfHousehold, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
        Text(
            "${stringRes(R.string.account, meter.accountNumber)} · ${meter.serialNumber} · " +
                "${stringRes(R.string.previous_reading)} ${formatNumber(meter.lastReadingValue)} m³",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
fun SyncStatusBar(state: UiState, pending: Int, onClick: () -> Unit) {
    val failed = state.banner == Banner.SYNC_FAILED
    val color = when {
        !state.online -> Color(0xFF92400E)
        failed -> Color(0xFFB91C1C)
        else -> Color(0xFF15803D)
    }
    val label = when {
        !state.online -> stringRes(R.string.offline)
        failed -> stringRes(R.string.sync_error)
        else -> stringRes(R.string.online)
    }
    Row(
        Modifier
            .fillMaxWidth()
            .background(color.copy(alpha = 0.08f), RoundedCornerShape(0.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Box(Modifier.size(10.dp).background(color, CircleShape))
        Text(label, style = MaterialTheme.typography.bodyMedium, color = color, fontWeight = FontWeight.Medium)
        Text(
            if (pending > 0) pluralStringResource(R.plurals.pending_readings, pending, pending)
            else stringRes(R.string.no_pending),
            style = MaterialTheme.typography.bodyMedium,
        )
        Text(
            stringRes(
                R.string.last_sync,
                if (state.lastSyncAt == 0L) stringRes(R.string.never) else formatTime(state.lastSyncAt),
            ),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
