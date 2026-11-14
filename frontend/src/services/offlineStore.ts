const DB_NAME = 'flow-offline'
const DB_VERSION = 1
const READINGS_STORE = 'pending_readings'
const PAYMENTS_STORE = 'pending_payments'

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(READINGS_STORE)) {
        db.createObjectStore(READINGS_STORE, { keyPath: 'client_id' })
      }
      if (!db.objectStoreNames.contains(PAYMENTS_STORE)) {
        db.createObjectStore(PAYMENTS_STORE, { keyPath: 'client_id' })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export interface OfflineReading {
  client_id: string
  meter_id: string
  reading_value: number
  reading_date: string
  notes?: string
  recorded_by?: string
}

export interface OfflinePayment {
  client_id: string
  connection_id: string
  invoice_id?: string | null
  amount: number
  currency: string
  payment_method: string
  payment_date: string
  receipt_number?: string
  notes?: string
}

export async function saveOfflineReading(reading: OfflineReading): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(READINGS_STORE, 'readwrite')
    tx.objectStore(READINGS_STORE).put(reading)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export async function saveOfflinePayment(payment: OfflinePayment): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(PAYMENTS_STORE, 'readwrite')
    tx.objectStore(PAYMENTS_STORE).put(payment)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export async function getPendingReadings(): Promise<OfflineReading[]> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(READINGS_STORE, 'readonly')
    const request = tx.objectStore(READINGS_STORE).getAll()
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export async function getPendingPayments(): Promise<OfflinePayment[]> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(PAYMENTS_STORE, 'readonly')
    const request = tx.objectStore(PAYMENTS_STORE).getAll()
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export async function clearSyncedReadings(clientIds: string[]): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(READINGS_STORE, 'readwrite')
    const store = tx.objectStore(READINGS_STORE)
    for (const id of clientIds) {
      store.delete(id)
    }
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export async function clearSyncedPayments(clientIds: string[]): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(PAYMENTS_STORE, 'readwrite')
    const store = tx.objectStore(PAYMENTS_STORE)
    for (const id of clientIds) {
      store.delete(id)
    }
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}
