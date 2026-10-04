package org.flow.reader.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.flow.reader.R
import org.flow.reader.data.local.MeterEntity

@Composable
fun RecordReadingScreen(
    meter: MeterEntity,
    onBack: () -> Unit,
    onSave: (Double, String?) -> Unit,
) {
    var value by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf("") }
    val parsed = value.replace(',', '.').toDoubleOrNull()
    val consumption = parsed?.let { it - meter.lastReadingValue }
    val fieldColors = OutlinedTextFieldDefaults.colors(
        unfocusedContainerColor = MaterialTheme.colorScheme.surface,
        focusedContainerColor = MaterialTheme.colorScheme.surface,
    )

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            FlowTopBar(
                title = stringRes(R.string.record_reading),
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .imePadding()
                .padding(16.dp)
        ) {
            Text(meter.headOfHousehold, style = MaterialTheme.typography.titleLarge)
            Text(
                "${stringRes(R.string.account, meter.accountNumber)} · ${meter.serialNumber}",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Column(
                Modifier
                    .padding(top = 16.dp)
                    .fillMaxWidth()
                    .background(FlowGradient, RoundedCornerShape(18.dp))
                    .padding(18.dp)
            ) {
                Text(
                    stringRes(R.string.previous_reading),
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White.copy(alpha = 0.8f),
                )
                Text(
                    "${formatNumber(meter.lastReadingValue)} m³",
                    fontSize = 34.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White,
                )
                meter.lastReadingDate?.let {
                    Text(
                        it.take(10),
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White.copy(alpha = 0.8f),
                    )
                }
            }

            OutlinedTextField(
                value = value,
                onValueChange = { new -> value = new.filter { it.isDigit() || it == '.' || it == ',' } },
                label = { Text(stringRes(R.string.new_reading)) },
                singleLine = true,
                shape = RoundedCornerShape(12.dp),
                colors = fieldColors,
                textStyle = MaterialTheme.typography.titleLarge,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Decimal,
                    imeAction = ImeAction.Next,
                ),
                modifier = Modifier
                    .padding(top = 20.dp)
                    .fillMaxWidth(),
            )

            consumption?.let { ConsumptionCard(it, warningFor(it, meter)) }

            OutlinedTextField(
                value = notes,
                onValueChange = { notes = it },
                label = { Text(stringRes(R.string.notes)) },
                shape = RoundedCornerShape(12.dp),
                colors = fieldColors,
                modifier = Modifier
                    .padding(top = 16.dp)
                    .fillMaxWidth(),
            )

            Button(
                onClick = { parsed?.let { onSave(it, notes) } },
                enabled = parsed != null,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .padding(top = 24.dp)
                    .fillMaxWidth()
                    .height(56.dp),
            ) { Text(stringRes(R.string.save)) }
        }
    }
}

@Composable
private fun ConsumptionCard(consumption: Double, warning: String?) {
    val tint = if (warning != null) FlowWarning else FlowSuccess
    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = tint.copy(alpha = 0.08f)),
        modifier = Modifier
            .padding(top = 12.dp)
            .fillMaxWidth(),
    ) {
        Row(
            Modifier.padding(14.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Icon(
                if (warning != null) Icons.Filled.Warning else Icons.Filled.CheckCircle,
                contentDescription = null,
                tint = tint,
            )
            Column {
                Text(
                    stringRes(R.string.consumption, formatNumber(consumption)),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                )
                warning?.let {
                    Text(it, color = tint, style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}

@Composable
private fun warningFor(consumption: Double, meter: MeterEntity): String? = when {
    consumption < 0 -> stringRes(R.string.warn_lower)
    consumption == 0.0 -> stringRes(R.string.warn_zero)
    meter.avgConsumptionM3 > 0 && consumption > meter.avgConsumptionM3 * 1.25 ->
        stringRes(R.string.warn_high)
    else -> null
}
