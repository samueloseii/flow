package org.flow.reader.data.local

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Room
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import androidx.room.RoomDatabase
import androidx.room.TypeConverter
import androidx.room.TypeConverters
import kotlinx.coroutines.flow.Flow

@Dao
interface MeterDao {
    @Query("SELECT * FROM meters ORDER BY accountNumber")
    fun observeAll(): Flow<List<MeterEntity>>

    @Query("SELECT * FROM meters WHERE meterId = :meterId")
    suspend fun byId(meterId: String): MeterEntity?

    @Query("SELECT COUNT(*) FROM meters")
    suspend fun count(): Int

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(meters: List<MeterEntity>)

    @Query("DELETE FROM meters WHERE meterId NOT IN (:keep)")
    suspend fun deleteMissing(keep: List<String>)

    @Query("UPDATE meters SET lastReadingValue = :value, lastReadingDate = :date WHERE meterId = :meterId")
    suspend fun updateLastReading(meterId: String, value: Double, date: String)
}

@Dao
interface ReadingDao {
    @Query("SELECT * FROM pending_readings ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<ReadingEntity>>

    @Query("SELECT * FROM pending_readings WHERE status != 'SYNCED' ORDER BY createdAt")
    suspend fun unsynced(): List<ReadingEntity>

    @Query("SELECT COUNT(*) FROM pending_readings WHERE status != 'SYNCED'")
    fun observeUnsyncedCount(): Flow<Int>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(reading: ReadingEntity)

    @Query(
        "UPDATE pending_readings SET status = :status, serverId = :serverId, " +
            "uploadedAt = :uploadedAt, lastError = NULL, attempts = attempts + 1 " +
            "WHERE clientId = :clientId"
    )
    suspend fun markSynced(
        clientId: String,
        status: ReadingStatus = ReadingStatus.SYNCED,
        serverId: String?,
        uploadedAt: Long,
    )

    @Query(
        "UPDATE pending_readings SET status = 'FAILED', lastError = :error, " +
            "attempts = attempts + 1 WHERE clientId = :clientId"
    )
    suspend fun markFailed(clientId: String, error: String)

    @Query("DELETE FROM pending_readings WHERE status = 'SYNCED' AND uploadedAt < :before")
    suspend fun pruneSynced(before: Long)
}

class Converters {
    @TypeConverter
    fun toStatus(value: String): ReadingStatus = ReadingStatus.valueOf(value)

    @TypeConverter
    fun fromStatus(status: ReadingStatus): String = status.name
}

@Database(entities = [MeterEntity::class, ReadingEntity::class], version = 2, exportSchema = false)
@TypeConverters(Converters::class)
abstract class FlowDatabase : RoomDatabase() {
    abstract fun meters(): MeterDao
    abstract fun readings(): ReadingDao

    companion object {
        @Volatile
        private var instance: FlowDatabase? = null

        fun get(context: Context): FlowDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext,
                FlowDatabase::class.java,
                "flow-reader.db",
            )
                // Rollback journal commits are fsynced, so a saved reading survives a battery pull.
                .setJournalMode(RoomDatabase.JournalMode.TRUNCATE)
                .addMigrations(MIGRATION_1_2)
                .build().also { instance = it }
        }
    }
}

/** Keeps pending offline readings when the meter table gains the expected-consumption columns. */
val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("ALTER TABLE meters ADD COLUMN communityName TEXT")
        db.execSQL("ALTER TABLE meters ADD COLUMN daysSinceLastReading INTEGER")
        db.execSQL("ALTER TABLE meters ADD COLUMN expectedConsumptionM3 REAL")
        db.execSQL("ALTER TABLE meters ADD COLUMN expectedReadingValue REAL")
    }
}
