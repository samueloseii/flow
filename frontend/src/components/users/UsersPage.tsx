import { FormEvent, useEffect, useState } from 'react'
import { KeyRound, Pencil, Plus, Trash2, Users } from 'lucide-react'
import api from '../../services/api'
import { useAuth } from '../../contexts/AuthContext'
import {
  Card,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  Spinner,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from '../ui'

interface TeamMember {
  id: string
  email: string
  full_name: string
  role: string
  phone: string | null
  is_active: boolean
  parent_level: string | null
  parent_id: string | null
  parent_name: string | null
  access_all_children: boolean
  community_ids: string[]
  connection_ids: string[]
  water_committee_id: string | null
  partner_id: string | null
  organization_id: string | null
}

interface Named {
  id: string
  name: string
}

interface ConnectionOption {
  id: string
  account_number: string
  contact_name: string
  water_committee_id: string
  community_id: string | null
}

interface Community {
  id: string
  name: string
  water_committee_id: string
}

export const roleOptions = [
  { value: 'operator', label: 'Operator — reads meters and replaces them; water committee level only' },
  { value: 'editor', label: 'Editor (treasurer) — edits everything at their level and below, cannot add or delete' },
  { value: 'admin', label: 'Administrator — adds, edits and deletes at their level and below' },
  { value: 'viewer', label: 'Viewer — read-only; the only role for a single connection' },
  { value: 'super_admin', label: 'System administrator — everything' },
]

export const roleLabels: Record<string, string> = {
  super_admin: 'System administrator',
  admin: 'Administrator',
  editor: 'Editor',
  operator: 'Operator',
  viewer: 'Viewer',
}

const levelLabels: Record<string, string> = {
  organization: 'Organization',
  partner: 'Partner',
  water_committee: 'Water committee',
  connection: 'Connection',
}

function levelsForRole(role: string): string[] {
  if (role === 'super_admin') return []
  if (role === 'operator') return ['water_committee']
  if (role === 'viewer') return ['organization', 'partner', 'water_committee', 'connection']
  return ['organization', 'partner', 'water_committee']
}

interface ScopeForm {
  role: string
  parent_level: string
  parent_id: string
  restrict: boolean
  community_ids: string[]
  connection_ids: string[]
}

const emptyScope: ScopeForm = {
  role: 'operator',
  parent_level: 'water_committee',
  parent_id: '',
  restrict: false,
  community_ids: [],
  connection_ids: [],
}

export default function UsersPage() {
  const { user: me } = useAuth()
  const [members, setMembers] = useState<TeamMember[]>([])
  const [organizations, setOrganizations] = useState<Named[]>([])
  const [partners, setPartners] = useState<Named[]>([])
  const [committees, setCommittees] = useState<Named[]>([])
  const [communities, setCommunities] = useState<Community[]>([])
  const [connections, setConnections] = useState<ConnectionOption[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ full_name: '', email: '', password: '', phone: '', ...emptyScope })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<TeamMember | null>(null)
  const [editForm, setEditForm] = useState({ full_name: '', phone: '', ...emptyScope })

  const canAdd = !!me && (me.role === 'super_admin' || me.role === 'admin')

  function load() {
    setLoading(true)
    api.get('/organizations/').then((r) => setOrganizations(r.data)).catch(() => setOrganizations([]))
    api.get('/partners/').then((r) => setPartners(r.data)).catch(() => setPartners([]))
    api.get('/water-committees/').then((r) => setCommittees(r.data)).catch(() => setCommittees([]))
    api.get('/communities/').then((r) => setCommunities(r.data)).catch(() => setCommunities([]))
    api.get('/connections/').then((r) => setConnections(r.data)).catch(() => setConnections([]))
    api
      .get('/auth/users')
      .then((r) => setMembers(r.data))
      .catch(() => setMembers([]))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  function parentOptions(level: string): { id: string; label: string }[] {
    if (level === 'organization') return organizations.map((o) => ({ id: o.id, label: o.name }))
    if (level === 'partner') return partners.map((p) => ({ id: p.id, label: p.name }))
    if (level === 'water_committee') return committees.map((c) => ({ id: c.id, label: c.name }))
    if (level === 'connection') return connections.map((c) => ({ id: c.id, label: `${c.account_number} — ${c.contact_name}` }))
    return []
  }

  function scopePayload(s: ScopeForm) {
    const restricted = s.role !== 'super_admin' && s.parent_level === 'water_committee' && s.restrict
    return {
      role: s.role,
      parent_level: s.role === 'super_admin' ? null : s.parent_level || null,
      parent_id: s.role === 'super_admin' ? null : s.parent_id || null,
      community_ids: restricted ? s.community_ids : [],
      connection_ids: restricted ? s.connection_ids : [],
    }
  }

  function scopeLabel(m: TeamMember): string {
    if (m.role === 'super_admin') return 'Everything'
    if (!m.parent_level) return 'Not assigned yet'
    const base = `${levelLabels[m.parent_level] ?? m.parent_level}: ${m.parent_name ?? '—'}`
    if (m.access_all_children) return base
    const parts: string[] = []
    if (m.community_ids?.length) {
      parts.push(m.community_ids.map((id) => communities.find((c) => c.id === id)?.name ?? '?').join(', '))
    }
    if (m.connection_ids?.length) parts.push(`${m.connection_ids.length} connection${m.connection_ids.length === 1 ? '' : 's'}`)
    return parts.length ? `${base} — only ${parts.join('; ')}` : base
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.post('/auth/users', {
        full_name: form.full_name,
        email: form.email,
        password: form.password,
        phone: form.phone || null,
        ...scopePayload(form),
      })
      setShowForm(false)
      setForm({ full_name: '', email: '', password: '', phone: '', ...emptyScope })
      load()
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not create the account.')
    } finally {
      setSaving(false)
    }
  }

  async function handleEditSubmit(e: FormEvent) {
    e.preventDefault()
    if (!editing) return
    setSaving(true)
    setError('')
    try {
      await api.patch(`/auth/users/${editing.id}`, {
        full_name: editForm.full_name,
        phone: editForm.phone || null,
        ...scopePayload(editForm),
      })
      setEditing(null)
      load()
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not save the changes.')
    } finally {
      setSaving(false)
    }
  }

  const active = members.filter((m) => m.is_active)

  async function resetPassword(member: TeamMember) {
    const next = window.prompt(`New password for ${member.full_name} (at least 8 characters)`)
    if (!next) return
    try {
      await api.post(`/auth/users/${member.id}/password`, { new_password: next })
      window.alert(`Password updated. Give it to ${member.full_name}.`)
    } catch (err: any) {
      window.alert(err?.response?.data?.detail ?? 'Could not change the password.')
    }
  }

  async function remove(member: TeamMember) {
    if (!window.confirm(`Remove ${member.full_name}'s account?`)) return
    try {
      await api.delete(`/auth/users/${member.id}`)
      load()
    } catch (err: any) {
      window.alert(err?.response?.data?.detail ?? 'Could not remove this account.')
    }
  }

  function ScopeFields<T extends ScopeForm>({ value, onChange }: { value: T; onChange: (v: T) => void }) {
    const levels = levelsForRole(value.role)
    const options = parentOptions(value.parent_level)
    const committeeCommunities = communities.filter((c) => c.water_committee_id === value.parent_id)
    const committeeConnections = connections.filter((c) => c.water_committee_id === value.parent_id)
    return (
      <>
        <Field label="Role" className="sm:col-span-2">
          <select
            className={inputClass}
            value={value.role}
            onChange={(e) => {
              const role = e.target.value
              const allowed = levelsForRole(role)
              const parent_level = allowed.includes(value.parent_level) ? value.parent_level : allowed[allowed.length - 1] ?? ''
              onChange({ ...value, role, parent_level, parent_id: parent_level === value.parent_level ? value.parent_id : '' })
            }}
          >
            {roleOptions
              .filter((r) => me?.role === 'super_admin' || r.value !== 'super_admin')
              .map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
          </select>
        </Field>
        {levels.length > 0 && (
          <>
            <Field label="Works at the level of">
              <select
                className={inputClass}
                value={value.parent_level}
                onChange={(e) => onChange({ ...value, parent_level: e.target.value, parent_id: '', restrict: false, community_ids: [], connection_ids: [] })}
              >
                {levels.map((l) => (
                  <option key={l} value={l}>
                    {levelLabels[l]}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={levelLabels[value.parent_level] ?? 'Entity'}>
              <select
                className={inputClass}
                value={value.parent_id}
                onChange={(e) => onChange({ ...value, parent_id: e.target.value, community_ids: [], connection_ids: [] })}
                required
              >
                <option value="">Choose…</option>
                {options.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </select>
            </Field>
          </>
        )}
        {value.parent_level === 'water_committee' && value.parent_id && (
          <Field label="Access within the committee" className="sm:col-span-2">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="radio"
                checked={!value.restrict}
                onChange={() => onChange({ ...value, restrict: false, community_ids: [], connection_ids: [] })}
              />
              Every connection in the committee
            </label>
            <label className="mt-1 flex items-center gap-2 text-sm text-gray-700">
              <input type="radio" checked={value.restrict} onChange={() => onChange({ ...value, restrict: true })} />
              Only certain communities / circuits or connections
            </label>
            {value.restrict && (
              <div className="mt-2 space-y-2">
                {committeeCommunities.length > 0 && (
                  <div className="grid grid-cols-2 gap-1 max-h-40 overflow-y-auto rounded-lg border border-gray-200 p-2">
                    {committeeCommunities.map((c) => (
                      <label key={c.id} className="flex items-center gap-2 text-sm text-gray-700">
                        <input
                          type="checkbox"
                          checked={value.community_ids.includes(c.id)}
                          onChange={(e) =>
                            onChange({
                              ...value,
                              community_ids: e.target.checked
                                ? [...value.community_ids, c.id]
                                : value.community_ids.filter((id) => id !== c.id),
                            })
                          }
                        />
                        {c.name}
                      </label>
                    ))}
                  </div>
                )}
                <select
                  multiple
                  className={`${inputClass} h-32`}
                  value={value.connection_ids}
                  onChange={(e) => onChange({ ...value, connection_ids: Array.from(e.target.selectedOptions).map((o) => o.value) })}
                >
                  {committeeConnections.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.account_number} — {c.contact_name}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500">Tick communities and/or select connections (hold Ctrl/Cmd for several).</p>
              </div>
            )}
          </Field>
        )}
      </>
    )
  }

  return (
    <div>
      <PageHeader
        title="Team"
        subtitle="Who can sign in, and what they are allowed to do"
        actions={
          canAdd ? (
            <button
              onClick={() => {
                const level = me?.parent_level && me.parent_level !== 'connection' ? me.parent_level : 'water_committee'
                setForm({ full_name: '', email: '', password: '', phone: '', ...emptyScope, parent_level: level, parent_id: me?.parent_id ?? '' })
                setError('')
                setShowForm(true)
              }}
              className={primaryButtonClass}
            >
              <Plus className="h-4 w-4" />
              Add person
            </button>
          ) : null
        }
      />

      {loading ? (
        <Spinner />
      ) : active.length === 0 ? (
        <Card>
          <EmptyState icon={Users} title="No accounts yet" hint="Add your operators and treasurer." />
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-5 py-3 font-medium">Name</th>
                <th className="px-5 py-3 font-medium">Email</th>
                <th className="px-5 py-3 font-medium">Role</th>
                <th className="px-5 py-3 font-medium">Scope</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {active.map((m) => (
                <tr key={m.id}>
                  <td className="px-5 py-3 font-medium text-gray-900">{m.full_name}</td>
                  <td className="px-5 py-3 text-gray-600">{m.email}</td>
                  <td className="px-5 py-3 text-gray-600">{roleLabels[m.role] ?? m.role}</td>
                  <td className="px-5 py-3 text-gray-600">{scopeLabel(m)}</td>
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-3">
                      {canAdd && (
                        <button
                          className="text-gray-400 hover:text-primary-600"
                          aria-label={`Edit ${m.full_name}`}
                          onClick={() => {
                            setEditForm({
                              full_name: m.full_name,
                              phone: m.phone ?? '',
                              role: m.role,
                              parent_level: m.parent_level ?? '',
                              parent_id: m.parent_id ?? '',
                              restrict: !m.access_all_children,
                              community_ids: m.community_ids ?? [],
                              connection_ids: m.connection_ids ?? [],
                            })
                            setError('')
                            setEditing(m)
                          }}
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                      )}
                      <button
                        className="text-gray-400 hover:text-primary-600"
                        aria-label={`Change ${m.full_name}'s password`}
                        onClick={() => resetPassword(m)}
                      >
                        <KeyRound className="h-4 w-4" />
                      </button>
                      {canAdd && (
                        <button
                          className="text-gray-400 hover:text-red-600"
                          aria-label={`Remove ${m.full_name}`}
                          onClick={() => remove(m)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {editing && (
        <Modal
          title={`Edit ${editing.full_name}`}
          description="Change what this person is allowed to do, or where they work."
          onClose={() => setEditing(null)}
        >
          <form onSubmit={handleEditSubmit} className="space-y-4">
            {error && <p className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-3 py-2 text-sm">{error}</p>}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Full name">
                <input className={inputClass} value={editForm.full_name} onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })} required />
              </Field>
              <Field label="Phone">
                <input className={inputClass} value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} />
              </Field>
              <ScopeFields value={editForm} onChange={setEditForm} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setEditing(null)} className={secondaryButtonClass}>
                Cancel
              </button>
              <button type="submit" disabled={saving} className={primaryButtonClass}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {showForm && (
        <Modal
          title="Add a person"
          description="Accounts are created at your level or below. Tell them their password in person."
          onClose={() => setShowForm(false)}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <p className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-3 py-2 text-sm">{error}</p>}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Full name">
                <input className={inputClass} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
              </Field>
              <Field label="Phone">
                <input className={inputClass} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </Field>
              <Field label="Email">
                <input type="email" className={inputClass} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
              </Field>
              <Field label="Password" hint="At least 8 characters">
                <input type="password" className={inputClass} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={8} />
              </Field>
              <ScopeFields value={form} onChange={setForm} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowForm(false)} className={secondaryButtonClass}>
                Cancel
              </button>
              <button type="submit" disabled={saving} className={primaryButtonClass}>
                {saving ? 'Creating…' : 'Create account'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
