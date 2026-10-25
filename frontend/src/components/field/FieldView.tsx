import { useState, useEffect } from 'react'
import { Droplets, LogOut } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { startAutoSync } from '../../services/syncService'
import FieldDashboard from './FieldDashboard'
import MeterReadingField from './MeterReadingField'
import MaintenanceField from './MaintenanceField'
import MeterReplaceField from './MeterReplaceField'
import HouseholdAddField from './HouseholdAddField'

type Page = 'home' | 'readings' | 'maintenance' | 'meter' | 'household'

export default function FieldView() {
  const { logout, user } = useAuth()
  const [page, setPage] = useState<Page>('home')

  useEffect(() => {
    const stop = startAutoSync()
    return stop
  }, [])

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Compact header */}
      <header className="bg-primary-700 text-white px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Droplets className="h-6 w-6 text-primary-200" />
          <span className="font-bold">Flow</span>
          <span className="text-primary-300 text-sm hidden sm:inline">Field Mode</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-primary-200">{user?.full_name}</span>
          <button onClick={logout} className="p-1.5 rounded hover:bg-primary-600 transition-colors">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="p-4">
        {page === 'home' && (
          <FieldDashboard onNavigate={(p) => setPage(p)} />
        )}
        {page === 'readings' && (
          <MeterReadingField onBack={() => setPage('home')} />
        )}
        {page === 'household' && (
          <HouseholdAddField onBack={() => setPage('home')} />
        )}
        {page === 'meter' && (
          <MeterReplaceField onBack={() => setPage('home')} />
        )}
        {page === 'maintenance' && (
          <MaintenanceField onBack={() => setPage('home')} />
        )}
      </div>
    </div>
  )
}
