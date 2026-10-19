import { FormEvent, useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  MapPin,
  Home,
  Receipt,
  Wallet,
  Wrench,
  BarChart3,
  UserCog,
  Building2,
  Gauge,
  Calculator,
  LogOut,
  KeyRound,
  Droplets,
  Handshake,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import api from '../../services/api'
import { Field, Modal, inputClass, primaryButtonClass, secondaryButtonClass } from '../ui'

type NavItem = { to: string; icon: typeof LayoutDashboard; label: string; roles?: string[] }

const ALL = ['super_admin', 'partner_admin', 'community_admin', 'treasurer', 'reader']
const MONEY = ['super_admin', 'partner_admin', 'community_admin', 'treasurer']
const MANAGE = ['super_admin', 'partner_admin', 'community_admin']

// Each level of the hierarchy only sees its own branch:
// system admin starts at Partners, partner admin at Water committees,
// committee admin / treasurer at Communities, a viewer at whatever they were given.
const navGroups: { label: string; items: NavItem[] }[] = [
  { label: '', items: [{ to: '/', icon: LayoutDashboard, label: 'Dashboard', roles: ALL }] },
  {
    label: 'Structure',
    items: [
      { to: '/partners', icon: Handshake, label: 'Partners', roles: ['super_admin'] },
      { to: '/water-committees', icon: Building2, label: 'Water committees', roles: ['super_admin', 'partner_admin', 'reader'] },
      { to: '/communities', icon: MapPin, label: 'Communities', roles: ALL },
      { to: '/households', icon: Home, label: 'Households', roles: ALL },
    ],
  },
  {
    label: 'Operations',
    items: [
      { to: '/readings', icon: Gauge, label: 'Meter readings', roles: ALL },
      { to: '/billing', icon: Receipt, label: 'Billing', roles: ALL },
      { to: '/tariffs', icon: Calculator, label: 'Tariffs', roles: MONEY },
      { to: '/expenses', icon: Wallet, label: 'Expenses', roles: MONEY },
      { to: '/maintenance', icon: Wrench, label: 'Maintenance', roles: MONEY },
    ],
  },
  {
    label: 'Oversight',
    items: [
      { to: '/analytics', icon: BarChart3, label: 'Analytics', roles: MONEY },
      { to: '/team', icon: UserCog, label: 'Team', roles: [...MANAGE, 'treasurer'] },
    ],
  },
]

function visibleGroups(user: { role: string; partner_id?: string | null; water_committee_id?: string | null; community_id?: string | null; household_id?: string | null } | null) {
  if (!user) return []
  return navGroups
    .map((g) => ({
      ...g,
      items: g.items.filter((item) => {
        if (item.roles && !item.roles.includes(user.role)) return false
        if (user.role !== 'reader') return true
        // Viewers only see the levels at or below the one they are attached to.
        if (item.to === '/water-committees') return !user.water_committee_id && !user.community_id && !user.household_id
        if (item.to === '/communities') return !user.household_id
        return true
      }),
    }))
    .filter((g) => g.items.length > 0)
}

const roleLabels: Record<string, string> = {
  super_admin: 'System administrator',
  partner_admin: 'Partner administrator',
  community_admin: 'Water committee administrator',
  treasurer: 'Treasurer',
  operator: 'Operator',
  reader: 'Viewer (read-only)',
}

export default function Sidebar() {
  const { logout, user } = useAuth()
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [saving, setSaving] = useState(false)

  async function changePassword(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setPasswordError('')
    try {
      await api.post('/auth/me/password', {
        current_password: currentPassword,
        new_password: newPassword,
      })
      setShowPasswordForm(false)
      setCurrentPassword('')
      setNewPassword('')
    } catch (err: any) {
      setPasswordError(err?.response?.data?.detail ?? 'Could not change the password.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 bg-primary-900 text-white flex flex-col print:hidden">
      <div className="p-6 flex items-center gap-3 border-b border-primary-800">
        <Droplets className="h-8 w-8 text-primary-300" />
        <div>
          <h1 className="text-lg font-bold">Flow</h1>
          <p className="text-xs text-primary-300">Water Intelligence</p>
        </div>
      </div>

      <nav className="flex-1 py-3 overflow-y-auto">
        {visibleGroups(user).map((group) => (
          <div key={group.label || 'top'} className="mb-2">
            {group.label && (
              <p className="px-6 pt-3 pb-1 text-[11px] uppercase tracking-wider text-primary-400">{group.label}</p>
            )}
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-6 py-2.5 text-sm transition-colors ${
                    isActive
                      ? 'bg-primary-800 text-white border-r-2 border-primary-300'
                      : 'text-primary-200 hover:bg-primary-800/50 hover:text-white'
                  }`
                }
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="p-4 border-t border-primary-800">
        {user && (
          <div className="mb-3 px-2">
            <p className="text-sm text-white truncate">{user.full_name}</p>
            <p className="text-xs text-primary-400">{roleLabels[user.role] || user.role}</p>
          </div>
        )}
        <button
          onClick={() => {
            setPasswordError('')
            setShowPasswordForm(true)
          }}
          className="flex items-center gap-3 px-2 py-2 text-sm text-primary-300 hover:text-white transition-colors w-full"
        >
          <KeyRound className="h-5 w-5" />
          Change password
        </button>
        <button
          onClick={logout}
          className="flex items-center gap-3 px-2 py-2 text-sm text-primary-300 hover:text-white transition-colors w-full"
        >
          <LogOut className="h-5 w-5" />
          Sign Out
        </button>
      </div>

      {showPasswordForm && (
        <Modal title="Change password" onClose={() => setShowPasswordForm(false)}>
          <form onSubmit={changePassword} className="space-y-4">
            {passwordError && (
              <p className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-3 py-2 text-sm">
                {passwordError}
              </p>
            )}
            <Field label="Current password">
              <input
                type="password"
                className={inputClass}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
              />
            </Field>
            <Field label="New password" hint="At least 8 characters">
              <input
                type="password"
                minLength={8}
                className={inputClass}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
            </Field>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                className={secondaryButtonClass}
                onClick={() => setShowPasswordForm(false)}
              >
                Cancel
              </button>
              <button type="submit" className={primaryButtonClass} disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </aside>
  )
}
