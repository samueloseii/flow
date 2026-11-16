package org.flow.reader

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.flow.reader.data.AuthStore
import org.flow.reader.data.ReadingRepository
import org.flow.reader.data.local.FlowDatabase
import org.flow.reader.data.local.MeterEntity
import org.flow.reader.data.local.ReadingStatus
import org.flow.reader.data.remote.ApiClient
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.shadows.ShadowNetworkCapabilities

@RunWith(RobolectricTestRunner::class)
class ReadingRepositoryTest {
    private lateinit var server: MockWebServer
    private lateinit var db: FlowDatabase
    private lateinit var repo: ReadingRepository
    private lateinit var context: Context

    private val meter = MeterEntity(
        meterId = "11111111-1111-1111-1111-111111111111",
        connectionId = "22222222-2222-2222-2222-222222222222",
        accountNumber = "A-001",
        contactName = "Mary Mensah",
        address = "1 Station Road",
        communityId = "33333333-3333-3333-3333-333333333333",
        serialNumber = "SN-1",
        lastReadingValue = 100.0,
        lastReadingDate = "2026-01-01T00:00:00Z",
        avgConsumptionM3 = 8.0,
        syncedAt = 0L,
    )

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        server = MockWebServer().also { it.start() }
        db = Room.inMemoryDatabaseBuilder(context, FlowDatabase::class.java)
            .allowMainThreadQueries().build()
        goOnline()
        val auth = AuthStore(context).also { it.token = "test-token" }
        val api = ApiClient.create(server.url("/api/v1/").toString(), auth)
        repo = ReadingRepository(context, db, api, auth)
    }

    /** Robolectric starts with an active network that has no capabilities declared. */
    private fun goOnline() {
        val cm = context.getSystemService(ConnectivityManager::class.java)
        val caps = ShadowNetworkCapabilities.newInstance()
        shadowOf(caps).addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
        shadowOf(cm).setNetworkCapabilities(cm.activeNetwork, caps)
    }

    @After
    fun tearDown() {
        server.shutdown()
        db.close()
    }

    @Test
    fun `reading saved offline survives with pending status and correct consumption`() = runTest {
        db.meters().upsertAll(listOf(meter))

        repo.saveReading(meter, 112.0, "dial dirty")

        val stored = db.readings().unsynced().single()
        assertEquals(ReadingStatus.PENDING, stored.status)
        assertEquals(12.0, stored.consumption, 0.001)
        assertNull(stored.serverId)
        // The cached meter advances so the next reading compares against this one.
        assertEquals(112.0, db.meters().byId(meter.meterId)!!.lastReadingValue, 0.001)
    }

    @Test
    fun `sync marks readings synced and leaves nothing pending`() = runTest {
        db.meters().upsertAll(listOf(meter))
        repo.saveReading(meter, 112.0, null)
        val clientId = db.readings().unsynced().single().clientId

        server.enqueue(
            MockResponse().setBody(
                """{"readings":[{"client_id":"$clientId","server_id":"srv-1","success":true,
                   "duplicate":false}],"payments":[],"synced_at":"2026-01-02T00:00:00Z"}"""
            ).setHeader("Content-Type", "application/json")
        )

        val outcome = repo.sync()

        assertTrue(outcome.ok)
        assertEquals(1, outcome.uploaded)
        assertTrue(db.readings().unsynced().isEmpty())
        val row = db.readings().observeAll().first().single()
        assertEquals("srv-1", row.serverId)
        assertEquals(ReadingStatus.SYNCED, row.status)
    }

    @Test
    fun `failed upload keeps the reading for a later retry`() = runTest {
        db.meters().upsertAll(listOf(meter))
        repo.saveReading(meter, 112.0, null)

        server.enqueue(MockResponse().setResponseCode(500))
        val failure = repo.sync()

        assertEquals(1, failure.failed)
        val kept = db.readings().unsynced().single()
        assertEquals(ReadingStatus.FAILED, kept.status)

        server.enqueue(
            MockResponse().setBody(
                """{"readings":[{"client_id":"${kept.clientId}","server_id":"srv-9","success":true,
                   "duplicate":false}],"payments":[],"synced_at":"2026-01-02T00:00:00Z"}"""
            ).setHeader("Content-Type", "application/json")
        )
        val retry = repo.sync()

        assertTrue(retry.ok)
        assertTrue(db.readings().unsynced().isEmpty())
    }

    @Test
    fun `a duplicate answer from the server still clears the reading locally`() = runTest {
        db.meters().upsertAll(listOf(meter))
        repo.saveReading(meter, 112.0, null)
        val clientId = db.readings().unsynced().single().clientId

        server.enqueue(
            MockResponse().setBody(
                """{"readings":[{"client_id":"$clientId","server_id":"srv-1","success":true,
                   "duplicate":true}],"payments":[],"synced_at":"2026-01-02T00:00:00Z"}"""
            ).setHeader("Content-Type", "application/json")
        )

        val outcome = repo.sync()

        assertEquals(1, outcome.duplicates)
        assertEquals(0, outcome.uploaded)
        assertTrue(db.readings().unsynced().isEmpty())
    }

    @Test
    fun `downloading meters replaces the cached list`() = runTest {
        db.meters().upsertAll(listOf(meter))
        server.enqueue(
            MockResponse().setBody(
                """[{"connection_id":"44444444-4444-4444-4444-444444444444","account_number":"A-002",
                    "contact_name":"John Adjei","address":null,
                    "community_id":"33333333-3333-3333-3333-333333333333",
                    "meter_id":"55555555-5555-5555-5555-555555555555","serial_number":"SN-2",
                    "last_reading_value":5.0,"last_reading_date":null,"avg_consumption_m3":0.0}]"""
            ).setHeader("Content-Type", "application/json")
        )

        assertEquals(1, repo.downloadMeters())
        assertEquals(1, db.meters().count())
        assertNull(db.meters().byId(meter.meterId))
    }
}
