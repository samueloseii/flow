package org.flow.reader.data.remote

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

@Serializable
data class LoginRequest(val email: String, val password: String)

@Serializable
data class TokenResponse(
    @SerialName("access_token") val accessToken: String,
)

@Serializable
data class MeResponse(
    val id: String,
    val email: String,
    @SerialName("full_name") val fullName: String,
    val role: String,
    @SerialName("community_id") val communityId: String? = null,
)

@Serializable
data class ReadingContext(
    @SerialName("household_id") val householdId: String,
    @SerialName("account_number") val accountNumber: String,
    @SerialName("head_of_household") val headOfHousehold: String,
    val address: String? = null,
    @SerialName("community_id") val communityId: String,
    @SerialName("meter_id") val meterId: String,
    @SerialName("serial_number") val serialNumber: String,
    @SerialName("last_reading_value") val lastReadingValue: Double = 0.0,
    @SerialName("last_reading_date") val lastReadingDate: String? = null,
    @SerialName("avg_consumption_m3") val avgConsumptionM3: Double = 0.0,
    @SerialName("community_name") val communityName: String? = null,
    @SerialName("avg_daily_consumption_m3") val avgDailyConsumptionM3: Double? = null,
    @SerialName("days_since_last_reading") val daysSinceLastReading: Int? = null,
    @SerialName("expected_consumption_m3") val expectedConsumptionM3: Double? = null,
    @SerialName("expected_reading_value") val expectedReadingValue: Double? = null,
)

@Serializable
data class SyncReading(
    @SerialName("client_id") val clientId: String,
    @SerialName("meter_id") val meterId: String,
    @SerialName("reading_value") val readingValue: Double,
    @SerialName("reading_date") val readingDate: String,
    val notes: String? = null,
)

@Serializable
data class SyncRequest(val readings: List<SyncReading>)

@Serializable
data class SyncResultItem(
    @SerialName("client_id") val clientId: String,
    @SerialName("server_id") val serverId: String? = null,
    val success: Boolean,
    val duplicate: Boolean = false,
    val error: String? = null,
)

@Serializable
data class SyncResponse(
    val readings: List<SyncResultItem> = emptyList(),
    @SerialName("synced_at") val syncedAt: String? = null,
)

interface FlowApi {
    @POST("auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @GET("auth/me")
    suspend fun me(): MeResponse

    @GET("meters/reading-context")
    suspend fun readingContext(): List<ReadingContext>

    @POST("sync/push")
    suspend fun push(@Body body: SyncRequest): SyncResponse

    @GET("health")
    suspend fun health(): Map<String, String>
}
