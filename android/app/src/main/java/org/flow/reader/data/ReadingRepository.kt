package org.flow.reader.data

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import kotlinx.coroutines.flow.Flow
import org.flow.reader.data.local.FlowDatabase
import org.flow.reader.data.local.MeterEntity
import org.flow.reader.data.local.ReadingEntity
import org.flow.reader.data.local.ReadingStatus
import org.flow.reader.data.remote.FlowApi
import org.flow.reader.data.remote.LoginRequest
import org.flow.reader.data.remote.SyncReading
import org.flow.reader.data.remote.SyncRequest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID

data class SyncOutcome(
    val uploaded: Int,
    val duplicates: Int,
    val failed: Int,
    val error: String? = null,
) {
    val ok: Boolean get() = error == null && failed == 0
}

class ReadingRepository(
    private val context: Context,
    private val db: FlowDatabase,
    private val api: FlowApi,
    private val auth: AuthStore,
) {
    val meters: Flow<List<MeterEntity>> = db.meters().observeAll()
    val readings: Flow<List<ReadingEntity>> = db.readings().observeAll()
    val pendingCount: Flow<Int> = db.readings().observeUnsyncedCount()

    fun isOnline(): Boolean {
        val cm = context.getSystemService(ConnectivityManager::class.java) ?: return false
        val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    suspend fun signIn(email: String, password: String) {
        val token = api.login(LoginRequest(email.trim(), password))
        auth.token = token.accessToken
        val me = api.me()
        auth.userId = me.id
        auth.userName = me.fullName
        auth.communityId = me.communityId
    }

    /** Replaces the cached meter list with what the server says this operator covers. */
    suspend fun downloadMeters(): Int {
        val now = System.currentTimeMillis()
        val rows = api.readingContext().map {
            MeterEntity(
                meterId = it.meterId,
                householdId = it.householdId,
                accountNumber = it.accountNumber,
                headOfHousehold = it.headOfHousehold,
                address = it.address,
                communityId = it.communityId,
                serialNumber = it.serialNumber,
                lastReadingValue = it.lastReadingValue,
                lastReadingDate = it.lastReadingDate,
                avgConsumptionM3 = it.avgConsumptionM3,
                communityName = it.communityName,
                daysSinceLastReading = it.daysSinceLastReading,
                expectedConsumptionM3 = it.expectedConsumptionM3,
                expectedReadingValue = it.expectedReadingValue,
                syncedAt = now,
            )
        }
        db.meters().upsertAll(rows)
        db.meters().deleteMissing(rows.map { it.meterId })
        auth.lastSyncAt = now
        return rows.size
    }

    suspend fun meter(meterId: String): MeterEntity? = db.meters().byId(meterId)

    suspend fun hasMeters(): Boolean = db.meters().count() > 0

    /** Saves a reading locally. Nothing here needs the network. */
    suspend fun saveReading(meter: MeterEntity, value: Double, notes: String?): ReadingEntity {
        val now = System.currentTimeMillis()
        val reading = ReadingEntity(
            clientId = UUID.randomUUID().toString(),
            meterId = meter.meterId,
            accountNumber = meter.accountNumber,
            headOfHousehold = meter.headOfHousehold,
            readingValue = value,
            previousValue = meter.lastReadingValue,
            readingDate = isoNow(now),
            notes = notes?.takeIf { it.isNotBlank() },
            status = ReadingStatus.PENDING,
            serverId = null,
            createdAt = now,
            uploadedAt = null,
            lastError = null,
            attempts = 0,
        )
        db.readings().insert(reading)
        // Keep the cached meter in step so the next reading shows the right previous value.
        db.meters().updateLastReading(meter.meterId, value, reading.readingDate)
        return reading
    }

    /**
     * Uploads everything not yet confirmed by the server. Local rows are only marked
     * synced on an explicit per-item success, so a dropped response means a retry, not
     * a lost reading — and the server's client_id check makes that retry harmless.
     */
    suspend fun sync(): SyncOutcome {
        val pending = db.readings().unsynced()
        if (pending.isEmpty()) {
            auth.lastSyncAt = System.currentTimeMillis()
            return SyncOutcome(0, 0, 0)
        }
        if (!isOnline()) return SyncOutcome(0, 0, pending.size, "offline")

        val response = try {
            api.push(
                SyncRequest(
                    pending.map {
                        SyncReading(
                            clientId = it.clientId,
                            meterId = it.meterId,
                            readingValue = it.readingValue,
                            readingDate = it.readingDate,
                            notes = it.notes,
                        )
                    }
                )
            )
        } catch (e: Exception) {
            val message = e.message ?: e::class.java.simpleName
            pending.forEach { db.readings().markFailed(it.clientId, message) }
            return SyncOutcome(0, 0, pending.size, message)
        }

        var uploaded = 0
        var duplicates = 0
        var failed = 0
        val now = System.currentTimeMillis()
        response.readings.forEach { item ->
            if (item.success) {
                db.readings().markSynced(
                    clientId = item.clientId,
                    serverId = item.serverId,
                    uploadedAt = now,
                )
                if (item.duplicate) duplicates++ else uploaded++
            } else {
                failed++
                db.readings().markFailed(item.clientId, item.error ?: "Upload rejected")
            }
        }
        auth.lastSyncAt = now
        // Confirmed readings stay visible for a week as the operator's own receipt.
        db.readings().pruneSynced(now - 7L * 24 * 60 * 60 * 1000)
        return SyncOutcome(uploaded, duplicates, failed)
    }

    companion object {
        fun isoNow(millis: Long): String {
            val fmt = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
            fmt.timeZone = TimeZone.getTimeZone("UTC")
            return fmt.format(Date(millis))
        }
    }
}
