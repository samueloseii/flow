package org.flow.reader.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

/** A meter the operator is responsible for, downloaded while online. */
@Entity(tableName = "meters")
data class MeterEntity(
    @PrimaryKey val meterId: String,
    val householdId: String,
    val accountNumber: String,
    val headOfHousehold: String,
    val address: String?,
    val communityId: String,
    val serialNumber: String,
    val lastReadingValue: Double,
    val lastReadingDate: String?,
    val avgConsumptionM3: Double,
    val communityName: String? = null,
    val daysSinceLastReading: Int? = null,
    val expectedConsumptionM3: Double? = null,
    val expectedReadingValue: Double? = null,
    val syncedAt: Long,
)

enum class ReadingStatus { PENDING, SYNCED, FAILED }

/**
 * A reading captured on the device. [clientId] is minted here and travels with the
 * reading, so re-sending a batch the server already stored cannot duplicate it.
 */
@Entity(tableName = "pending_readings")
data class ReadingEntity(
    @PrimaryKey val clientId: String,
    val meterId: String,
    val accountNumber: String,
    val headOfHousehold: String,
    val readingValue: Double,
    val previousValue: Double,
    val readingDate: String,
    val notes: String?,
    val status: ReadingStatus,
    val serverId: String?,
    val createdAt: Long,
    val uploadedAt: Long?,
    val lastError: String?,
    val attempts: Int,
) {
    val consumption: Double get() = readingValue - previousValue
}
