package org.flow.reader.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.flow.reader.R
import org.flow.reader.data.local.ReadingEntity
import org.flow.reader.data.local.ReadingStatus

@Composable
fun HistoryScreen(
    state: UiState,
    readings: List<ReadingEntity>,
    pending: Int,
    onBack: () -> Unit,
    onSync: () -> Unit,
) {
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            FlowTopBar(
                title = stringRes(R.string.readings_history),
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
            )
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            SyncStatusBar(state, pending) {}
            Button(
                onClick = onSync,
                enabled = !state.busy,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .padding(horizontal = 16.dp)
                    .fillMaxWidth()
                    .height(52.dp),
            ) { Text(stringRes(R.string.sync_now)) }

            if (readings.isEmpty()) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        stringRes(R.string.no_pending),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(readings, key = { it.clientId }) { reading -> ReadingRow(reading) }
                }
            }
        }
    }
}

@Composable
private fun ReadingRow(reading: ReadingEntity) {
    val (label, color) = when (reading.status) {
        ReadingStatus.SYNCED -> stringRes(R.string.status_synced) to FlowSuccess
        ReadingStatus.FAILED -> stringRes(R.string.status_failed) to FlowDanger
        ReadingStatus.PENDING -> stringRes(R.string.status_pending) to FlowWarning
    }
    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 12.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(reading.headOfHousehold, fontWeight = FontWeight.SemiBold)
                Text(
                    label,
                    color = color,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier
                        .background(color.copy(alpha = 0.12f), RoundedCornerShape(50))
                        .padding(horizontal = 10.dp, vertical = 4.dp),
                )
            }
            Text(
                "${formatNumber(reading.readingValue)} m³ · " +
                    stringRes(R.string.consumption, formatNumber(reading.consumption)),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 4.dp),
            )
            Text(
                formatTime(reading.createdAt),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            reading.lastError?.takeIf { reading.status == ReadingStatus.FAILED }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = FlowDanger)
            }
        }
    }
}
