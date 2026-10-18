import { FormEvent, useEffect, useState } from 'react'
import { KeyRound, Pencil, Plus, Trash2, Users } from 'lucide-react'
import api from '../../services/api'
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
  community_id: string | null
  water_committee_id: string | null
  assigned_community_ids: string[]
}

interface Committee {
  id: string
  name: string
}

interface Community {
  id: string
  name: string
  water_committee_id: string | null
}

const roleOptions = [
  { value: 'operator', label: 'Operator — reads meters in assigned communities' },
  { value: 'treasurer', label: 'Treasurer — billing, payments and expenses for the committee' },
  { value: 'community_admin', label: 'Water committee administrator — runs the committee' },
  { value: 'partner_admin', label: 'Partner administrator — all committees the partner supports' },
  { value: 'super_admin', label: 'System administrator — everything' },
  { value: 'reader', label: 'Viewer — read-only' },
]

const roleLabels: Record<string, string> = {
  super_admin: 'Super administrator',
  partner_admin: 'Organization administrator',
  community_admin: 'Water committee admin',
  treasurer: 'Treasurer',
  operator: 'Operator',
  reader: 'Viewer',
}

const emptyForm = {
  full_name: '',
  email: '',
  password: '',
  phone: '',
  role: 'operator',
  community_id: '',
  water_committee_id: '',
  assigned_community_ids: [] as string[],
}

export default function UsersPage() {
  const [members, setMembers] = useState<TeamMember[]>([])
  const [communities, setCommunities] = useState<Community[]>([])
  const [committees, setCommittees] = useState<Committee[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<TeamMember | null>(null)
  const [editForm, setEditForm] = useState({ full_name: '', phone: '', role: '', community_id: '', water_committee_id: '', assigned_community_ids: [] as string[] })

  function load() {
    setLoading(true)
    api.get('/water-committees/').then((r) => setCommittees(r.data)).catch(() => setCommittees([]))
    Promise.all([api.get('/auth/users'), api.get('/communities/')])
      .then(([usersRes, communitiesRes]) => {
        setMembers(usersRes.data)
        setCommunities(communitiesRes.data)
      })
      .catch(() => setMembers([]))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

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
        role: form.role,
        community_id: form.community_id || null,
        water_committee_id: form.water_committee_id || null,
        assigned_community_ids: form.role === 'operator' || form.role === 'reader' ? form.assigned_community_ids : [],
      })
      setShowForm(false)
      setForm(emptyForm)
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
        role: editForm.role,
        community_id: editForm.community_id || null,
        clear_community: !editForm.community_id,
        water_committee_id: editForm.water_committee_id || null,
        clear_water_committee: !editForm.water_committee_id,
        assigned_community_ids: editForm.assigned_community_ids,
      })
      setEditing(null)
      load()
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not save the changes.')
    } finally {
      setSaving(false)
    }
  }

  const communityName = (id: string | null) =>
    communities.find((c) => c.id === id)?.name ?? '—'

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

  async function remove(member: TeamMember, question: string) {
    if (!window.confirm(question)) return
    try {
      await api.delete(`/auth/users/${member.id}`)
      load()
    } catch (err: any) {
      window.alert(err?.response?.data?.detail ?? 'Could not remove this account.')
    }
  }

  return (
    <div>
      <PageHeader
        title="Team"
        subtitle="Who can sign in, and what they are allowed to do"
        actions={
          <button
            onClick={() => {
              setForm({ ...emptyForm, community_id: communities[0]?.id ?? '' })
              setError('')
              setShowForm(true)
            }}
            className={primaryButtonClass}
          >
            <Plus className="h-4 w-4" />
            Add person
          </button>
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
                <th className="px-5 py-3 font-medium">Community</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {active.map((m) => (
                <tr key={m.id}>
                  <td className="px-5 py-3 font-medium text-gray-900">{m.full_name}</td>
                  <td className="px-5 py-3 text-gray-600">{m.email}</td>
                  <td className="px-5 py-3 text-gray-600">{roleLabels[m.role] ?? m.role}</td>
                  <td className="px-5 py-3 text-gray-600">{communityName(m.community_id)}</td>
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-3">
                      <button
                        className="text-gray-400 hover:text-primary-600"
                        aria-label={`Edit ${m.full_name}`}
                        onClick={() => {
                          setEditForm({
                            full_name: m.full_name,
                            phone: m.phone ?? '',
                            role: m.role,
                            community_id: m.community_id ?? '',
                            water_committee_id: m.water_committee_id ?? '',
                            assigned_community_ids: m.assigned_community_ids ?? [],
                          })
                          setError('')
                          setEditing(m)
                        }}
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        className="text-gray-400 hover:text-primary-600"
                        aria-label={`Change ${m.full_name}'s password`}
                        onClick={() => resetPassword(m)}
                      >
                        <KeyRound className="h-4 w-4" />
                      </button>
                      <button
                        className="text-gray-400 hover:text-red-600"
                        aria-label={`Remove ${m.full_name}`}
                        onClick={() => remove(m, `Remove ${m.full_name}'s account?`)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
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
          description="Change what this person is allowed to do, or which community they work in."
          onClose={() => setEditing(null)}
        >
          <form onSubmit={handleEditSubmit} className="space-y-4">
            {error && (
              <p className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-3 py-2 text-sm">
                {error}
              </p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Full name">
                <input
                  className={inputClass}
                  value={editForm.full_name}
                  onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                  required
                />
              </Field>
              <Field label="Phone">
                <input
                  className={inputClass}
                  value={editForm.phone}
                  onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                />
              </Field>
              <Field label="Role" className="sm:col-span-2">
                <select
                  className={inputClass}
                  value={editForm.role}
                  onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                >
                  {roleOptions.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Water committee" className="sm:col-span-2">
                <select
                  className={inputClass}
                  value={editForm.water_committee_id}
                  onChange={(e) => setEditForm({ ...editForm, water_committee_id: e.target.value, community_id: '', assigned_community_ids: [] })}
                >
                  <option value="">{committees.length ? 'All committees' : 'None'}</option>
                  {committees.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              {(editForm.role === 'operator' || editForm.role === 'reader') ? (
                <Field label="Communities to read" className="sm:col-span-2" hint="Tick every community this person covers">
                  <div className="grid grid-cols-2 gap-1 max-h-40 overflow-y-auto rounded-lg border border-gray-200 p-2">
                    {communities.filter((c) => !editForm.water_committee_id || c.water_committee_id === editForm.water_committee_id).map((c) => (
                      <label key={c.id} className="flex items-center gap-2 text-sm text-gray-700">
                        <input
                          type="checkbox"
                          checked={editForm.assigned_community_ids.includes(c.id)}
                          onChange={(e) => {
                            const ids = e.target.checked
                              ? [...editForm.assigned_community_ids, c.id]
                              : editForm.assigned_community_ids.filter((id) => id !== c.id)
                            setEditForm({ ...editForm, assigned_community_ids: ids, community_id: ids[0] ?? '' })
                          }}
                        />
                        {c.name}
                      </label>
                    ))}
                    {communities.length === 0 && <span className="text-xs text-gray-500">No communities yet</span>}
                  </div>
                </Field>
              ) : (
              <Field label="Community" className="sm:col-span-2">
                <select
                  className={inputClass}
                  value={editForm.community_id}
                  onChange={(e) => setEditForm({ ...editForm, community_id: e.target.value })}
                >
                  <option value="">All communities</option>
                  {communities.filter((c) => !editForm.water_committee_id || c.water_committee_id === editForm.water_committee_id).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className={secondaryButtonClass} onClick={() => setEditing(null)}>
                Cancel
              </button>
              <button type="submit" className={primaryButtonClass} disabled={saving}>
                {saving ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {showForm && (
        <Modal
          title="Add person"
          description="They sign in with this email and password."
          onClose={() => setShowForm(false)}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <p className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-3 py-2 text-sm">
                {error}
              </p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Full name">
                <input
                  className={inputClass}
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  required
                />
              </Field>
              <Field label="Email">
                <input
                  type="email"
                  className={inputClass}
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  required
                />
              </Field>
              <Field label="Phone">
                <input
                  className={inputClass}
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
              </Field>
              <Field label="Temporary password" hint="At least 8 characters">
                <input
                  type="text"
                  minLength={8}
                  className={inputClass}
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  required
                />
              </Field>
              <Field label="Role" className="sm:col-span-2">
                <select
                  className={inputClass}
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value })}
                >
                  {roleOptions.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Water committee" className="sm:col-span-2">
                <select
                  className={inputClass}
                  value={form.water_committee_id}
                  onChange={(e) => setForm({ ...form, water_committee_id: e.target.value, community_id: '', assigned_community_ids: [] })}
                >
                  <option value="">{committees.length ? 'All committees' : 'None'}</option>
                  {committees.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              {(form.role === 'operator' || form.role === 'reader') ? (
                <Field label="Communities to read" className="sm:col-span-2" hint="Tick every community this person covers">
                  <div className="grid grid-cols-2 gap-1 max-h-40 overflow-y-auto rounded-lg border border-gray-200 p-2">
                    {communities.filter((c) => !form.water_committee_id || c.water_committee_id === form.water_committee_id).map((c) => (
                      <label key={c.id} className="flex items-center gap-2 text-sm text-gray-700">
                        <input
                          type="checkbox"
                          checked={form.assigned_community_ids.includes(c.id)}
                          onChange={(e) => {
                            const ids = e.target.checked
                              ? [...form.assigned_community_ids, c.id]
                              : form.assigned_community_ids.filter((id) => id !== c.id)
                            setForm({ ...form, assigned_community_ids: ids, community_id: ids[0] ?? '' })
                          }}
                        />
                        {c.name}
                      </label>
                    ))}
                    {communities.length === 0 && <span className="text-xs text-gray-500">No communities yet</span>}
                  </div>
                </Field>
              ) : (
              <Field label="Community" className="sm:col-span-2">
                <select
                  className={inputClass}
                  value={form.community_id}
                  onChange={(e) => setForm({ ...form, community_id: e.target.value })}
                >
                  <option value="">All communities</option>
                  {communities.filter((c) => !form.water_committee_id || c.water_committee_id === form.water_committee_id).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className={secondaryButtonClass} onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button type="submit" className={primaryButtonClass} disabled={saving}>
                {saving ? 'Creating…' : 'Create account'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
