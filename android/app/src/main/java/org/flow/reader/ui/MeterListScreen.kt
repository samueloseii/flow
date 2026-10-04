package org.flow.reader.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
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
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.flow.reader.R
import org.flow.reader.data.local.MeterEntity

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
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            FlowTopBar(
                title = stringRes(R.string.meters),
                actions = {
                    IconButton(onClick = onRefresh, enabled = !state.busy) {
                        Icon(Icons.Default.Refresh, contentDescription = stringRes(R.string.refresh))
                    }
                    IconButton(onClick = onSignOut) {
                        Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = stringRes(R.string.sign_out))
                    }
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
                placeholder = { Text(stringRes(R.string.search_meters)) },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                singleLine = true,
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                    focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedBorderColor = MaterialTheme.colorScheme.outlineVariant,
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
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
                Text(
                    stringRes(R.string.meters_count, filtered.size),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(start = 20.dp, top = 12.dp, bottom = 4.dp),
                )
                LazyColumn(
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 24.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(filtered, key = { it.meterId }) { meter ->
                        MeterRow(meter) { onSelect(meter) }
                    }
                }
            }
        }
    }
}

private fun initials(name: String): String =
    name.split(' ').filter { it.isNotBlank() }.take(2).joinToString("") { it.first().uppercase() }

@Composable
private fun MeterRow(meter: MeterEntity, onClick: () -> Unit) {
    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Box(
                Modifier
                    .size(42.dp)
                    .background(FlowSky, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(initials(meter.headOfHousehold), color = FlowBlueDark, fontWeight = FontWeight.SemiBold)
            }
            Column(Modifier.weight(1f)) {
                Text(
                    meter.headOfHousehold,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    "${meter.accountNumber} · ${meter.serialNumber}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    "${formatNumber(meter.lastReadingValue)} m³",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = FlowBlueDark,
                )
                Text(
                    stringRes(R.string.last_short),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Icon(
                Icons.AutoMirrored.Filled.KeyboardArrowRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.outline,
            )
        }
    }
}

@Composable
fun SyncStatusBar(state: UiState, pending: Int, onClick: () -> Unit) {
    val failed = state.banner == Banner.SYNC_FAILED
    val color = when {
        !state.online -> FlowWarning
        failed -> FlowDanger
        else -> FlowSuccess
    }
    val label = when {
        !state.online -> stringRes(R.string.offline)
        failed -> stringRes(R.string.sync_error)
        else -> stringRes(R.string.online)
    }
    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
            .clickable(onClick = onClick),
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Box(
                Modifier
                    .size(36.dp)
                    .background(color.copy(alpha = 0.12f), CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Box(Modifier.size(12.dp).background(color, CircleShape))
            }
            Column(Modifier.weight(1f)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(label, style = MaterialTheme.typography.bodyMedium, color = color, fontWeight = FontWeight.SemiBold)
                    Text(
                        if (pending > 0) pluralStringResource(R.plurals.pending_readings, pending, pending)
                        else stringRes(R.string.no_pending),
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (pending > 0) Color(0xFF0F172A) else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
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
    }
}
