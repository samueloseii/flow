# Flow Reader (Android)

Native Android app for field operators who collect meter readings where there is no
usable internet. It is a companion to the Flow web app, not a replacement: everything
administrators and treasurers do (billing, payments, expenses, analytics) stays on the
web. The phone only does one job, and does it without a network: capture readings and
upload them later.

The app talks to the same Flow backend as the web app and adds no new business logic.

## Why a native app

The web app already caches in the browser, but a browser is not a safe place for a day's
work: closing the tab, clearing site data, an OS reclaiming storage or a reboot can all
cost readings. Room on the device keeps readings until the server confirms them.

## Requirements

- JDK 17
- Android SDK with platform 35 and build-tools 35 (Android Studio installs both)
- A device or emulator on Android 7.0 (API 24) or newer

## Build and run

```bash
cd android
./gradlew assembleDebug           # APK at app/build/outputs/apk/debug/app-debug.apk
./gradlew testDebugUnitTest       # unit tests (Robolectric + MockWebServer)
```

Point the app at a different backend at build time:

```bash
./gradlew assembleDebug -PflowApiBaseUrl=http://10.0.2.2:8000/api/v1/
```

The default is `https://flow-nstl.onrender.com/api/v1/`. `10.0.2.2` is how an emulator
reaches a server running on the host machine.

### Emulator

```bash
sdkmanager "system-images;android-34;google_apis;x86_64" emulator
avdmanager create avd -n flow -k "system-images;android-34;google_apis;x86_64"
emulator -avd flow &
./gradlew installDebug
```

Toggle offline mode with the emulator's Cellular/Wi-Fi settings, or:

```bash
adb shell svc data disable && adb shell svc wifi disable   # go offline
adb shell svc data enable  && adb shell svc wifi enable    # come back online
```

### Physical device

Enable Developer options → USB debugging, connect by USB, then `./gradlew installDebug`.
To hand the APK to someone else, send `app-debug.apk` and let them install it with
"Install unknown apps" allowed for their file manager. Debug builds are signed with the
local debug key — for wider distribution build a release APK signed with your own
keystore.

## How an operator uses it

1. Sign in once while online with the Flow account an administrator created.
2. The app downloads every connection and meter the account covers and stores them locally.
3. Go offline. Pick a connection (search by name or account number), type the cumulative
   meter reading, save. The app shows the previous reading and the resulting consumption,
   and warns when a reading is lower than the previous one, identical to it, or more than
   25% above the connection's average.
4. Keep recording. Readings survive closing the app and rebooting the phone.
5. Back in coverage, press Sync (or let the background job run). Confirmed readings turn
   into receipts; anything the server rejected stays on the phone, marked, ready to retry.

## Architecture

```
ui/            Compose screens + FlowViewModel (all UI state in one immutable UiState)
data/
  AuthStore          token + operator identity in EncryptedSharedPreferences
  ReadingRepository  the only place that talks to both Room and the API
  local/             Room entities, DAOs, FlowDatabase
  remote/            Retrofit interface, kotlinx.serialization models, OkHttp client
sync/          SyncWorker — WorkManager job, periodic (15 min) + on demand
```

There is no DI framework: `AppContainer` in `FlowApp.kt` builds the four objects the app
needs and hands them out via `context.container`.

### Local database

`meters` is a cache — replaced wholesale on every download, so a connection removed on the
server disappears from the phone.

`readings` is the source of truth until the server confirms otherwise. Each row carries
`clientId` (a UUID generated on the phone), the meter and connection it belongs to, the
value, previous value, reading date, notes, `status`, `serverId`, created/uploaded
timestamps, the last error and an attempt count. Rows are never deleted before the server
acknowledges them; synced rows are pruned after seven days so the operator keeps a recent
receipt.

### Sync

`PENDING → SYNCED` on an explicit per-item success, `PENDING → FAILED` on a rejection or a
network error, `FAILED → SYNCED` on a successful retry. Nothing else moves rows.

Retries are safe because every reading carries a `clientId` and the backend stores it in a
unique column: uploading the same reading twice returns the original `server_id` with
`duplicate: true` instead of writing a second reading. This matters — a duplicated reading
would otherwise corrupt the connection's consumption and its bill.

A dropped response is therefore never data loss: the reading stays local, the next sync
re-sends it, and the server recognises it.

### API used

| Endpoint | Purpose |
| --- | --- |
| `POST /auth/login` | sign in, returns a JWT (30 days for field roles) |
| `GET /auth/me` | operator name, id, community |
| `GET /meters/reading-context` | every connection + meter with its last reading and average |
| `POST /sync/push` | batch upload of readings, idempotent on `client_id` |
| `GET /health` | connectivity check |

### Authentication

The JWT lives in `EncryptedSharedPreferences` (AES-256-GCM, key in the Android keystore),
so it survives restarts and reboots without the operator retyping a password in the field.
Signing out clears the token but never the unsynced readings.

## Known limitations

- Readings only. Fault reports, payments and photos of the dial are web-only for now
  (the backend has a `photo_url` column but no upload endpoint).
- If the token expires while the phone is offline, readings keep saving locally but sync
  waits until the operator signs in again on a network.
- Meters are downloaded in one request; very large communities will want pagination.
- The app reads all meters the account can see, not a per-route subset.

## Possible next steps

- Photo capture once an upload endpoint exists.
- Offline fault reports reusing the same `client_id` idempotency.
- Per-route assignment so an operator only downloads their own list.
- Release signing + Play Store internal distribution.
