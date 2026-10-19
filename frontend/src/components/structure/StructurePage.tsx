import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, ChevronDown, ChevronRight, Gauge, Handshake, Home, MapPin, Network } from 'lucide-react'
import api from '../../services/api'
import { useAuth } from '../../contexts/AuthContext'
import { Card, EmptyState, PageHeader, Spinner, secondaryButtonClass } from '../ui'

interface Partner { id: string; name: string; country: string }
interface Committee { id: string; name: string; partner_id: string; region: string | null }
interface Community { id: string; name: string; partner_id: string; water_committee_id: string | null }
interface Household { id: string; account_number: string; head_of_household: string; community_id: string; status: string }
interface Meter { id: string; serial_number: string; status: string; household_id: string; last_reading_value: number }

const MANAGE = ['super_admin', 'partner_admin', 'community_admin']

// The whole hierarchy as one expandable outline, the way the committee drew it:
// Partner → Water committee → Community → Household → Meter (removed meters stay listed).
// Each account only receives its own branch from the API, so the outline starts at its level.
export default function StructurePage() {
  const { user } = useAuth()
  const [partners, setPartners] = useState<Partner[]>([])
  const [committees, setCommittees] = useState<Committee[]>([])
  const [communities, setCommunities] = useState<Community[]>([])
  const [households, setHouseholds] = useState<Household[]>([])
  const [meters, setMeters] = useState<Meter[]>([])
  const [loading, setLoading] = useState(true)
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (!user) return
    setLoading(true)
    const get = (url: string, params?: object) => api.get(url, { params }).then((r) => r.data).catch(() => [])
    Promise.all([
      user.role === 'super_admin' ? get('/partners/') : Promise.resolve([]),
      get('/water-committees/'),
      get('/communities/'),
      get('/households/', { limit: 1000 }),
      get('/meters/', { limit: 1000 }),
    ]).then(([p, wc, c, h, m]) => {
      setPartners(p); setCommittees(wc); setCommunities(c); setHouseholds(h); setMeters(m)
    }).finally(() => setLoading(false))
  }, [user])

  const canManage = !!user && MANAGE.includes(user.role)
  const toggle = (id: string) => setCollapsed((s) => ({ ...s, [id]: !s[id] }))

  // Group children under their parents once.
  const byParent = useMemo(() => ({
    committees: group(committees, (c) => c.partner_id),
    communities: group(communities, (c) => c.water_committee_id ?? `partner:${c.partner_id}`),
    households: group(households, (h) => h.community_id),
    meters: group(meters, (m) => m.household_id),
  }), [committees, communities, households, meters])

  if (!user) return null
  if (loading) return <div className="flex justify-center py-20"><Spinner /></div>

  const meterRow = (m: Meter) => (
    <Row key={m.id} depth={4} icon={Gauge} title={m.serial_number}
      meta={m.status === 'active' ? `last reading ${m.last_reading_value} m³` : m.status}
      muted={m.status !== 'active'} />
  )
  const householdRow = (h: Household) => {
    const ms = byParent.meters[h.id] ?? []
    return (
      <Row key={h.id} depth={3} icon={Home} title={h.head_of_household} meta={h.account_number} to={`/households/${h.id}`}
        count={`${ms.length} meter${ms.length === 1 ? '' : 's'}`} muted={h.status !== 'active'}
        open={!collapsed[h.id]} onToggle={ms.length ? () => toggle(h.id) : undefined}>
        {ms.map(meterRow)}
      </Row>
    )
  }
  const communityRow = (c: Community) => {
    const hs = byParent.households[c.id] ?? []
    return (
      <Row key={c.id} depth={2} icon={MapPin} title={c.name} count={`${hs.length} household${hs.length === 1 ? '' : 's'}`}
        open={!collapsed[c.id]} onToggle={hs.length ? () => toggle(c.id) : undefined}>
        {hs.map(householdRow)}
      </Row>
    )
  }
  const committeeRow = (w: Committee) => {
    const cs = byParent.communities[w.id] ?? []
    return (
      <Row key={w.id} depth={1} icon={Building2} title={w.name} meta={w.region ?? ''} count={`${cs.length} communit${cs.length === 1 ? 'y' : 'ies'}`}
        open={!collapsed[w.id]} onToggle={cs.length ? () => toggle(w.id) : undefined}>
        {cs.map(communityRow)}
      </Row>
    )
  }
  const partnerRow = (p: Partner) => {
    const ws = byParent.committees[p.id] ?? []
    const loose = byParent.communities[`partner:${p.id}`] ?? []
    return (
      <Row key={p.id} depth={0} icon={Handshake} title={p.name} meta={p.country} count={`${ws.length} water committee${ws.length === 1 ? '' : 's'}`}
        open={!collapsed[p.id]} onToggle={ws.length + loose.length ? () => toggle(p.id) : undefined}>
        {ws.map(committeeRow)}
        {loose.map(communityRow)}
      </Row>
    )
  }

  // What the top of this account's branch is.
  let top: React.ReactNode
  let title = 'Structure'
  let subtitle = 'Partner → Water committee → Community → Household → Meter'
  if (user.role === 'super_admin') {
    title = 'All partners'
    top = partners.length ? partners.map(partnerRow) : null
  } else if (user.household_id) {
    title = 'Your household'
    top = households.map(householdRow)
  } else if (user.role === 'reader' && user.community_id) {
    title = communities[0]?.name ?? 'Your community'
    top = communities.map(communityRow)
  } else if (user.water_committee_id) {
    const w = committees.find((x) => x.id === user.water_committee_id)
    title = w?.name ?? 'Your water committee'
    subtitle = 'Communities, households and meters under this water committee.'
    top = (byParent.communities[user.water_committee_id] ?? []).map(communityRow)
  } else {
    title = 'Water committees you support'
    top = committees.map(committeeRow)
  }
  const empty = !top || (Array.isArray(top) && top.length === 0)

  return (
    <div>
      <PageHeader title={title} subtitle={subtitle}
        actions={canManage && (
          <>
            {user.role === 'super_admin' && <Link to="/partners" className={secondaryButtonClass}>Partners</Link>}
            {['super_admin', 'partner_admin'].includes(user.role) && <Link to="/water-committees" className={secondaryButtonClass}>Water committees</Link>}
            <Link to="/communities" className={secondaryButtonClass}>Communities</Link>
            <Link to="/households" className={secondaryButtonClass}>Households &amp; import</Link>
          </>
        )} />
      <Card>
        {empty ? (
          <EmptyState icon={Network} title="Nothing in this branch yet" hint={canManage ? 'Use the buttons above to add the first level.' : undefined} />
        ) : (
          <ul className="py-2">{top}</ul>
        )}
      </Card>
    </div>
  )
}

function group<T>(items: T[], key: (t: T) => string): Record<string, T[]> {
  const out: Record<string, T[]> = {}
  for (const it of items) (out[key(it)] ??= []).push(it)
  return out
}

function Row({ depth, icon: Icon, title, meta, count, to, muted, open, onToggle, children }: {
  depth: number
  icon: React.ComponentType<{ className?: string }>
  title: string
  meta?: string
  count?: string
  to?: string
  muted?: boolean
  open?: boolean
  onToggle?: () => void
  children?: React.ReactNode
}) {
  const hasChildren = !!onToggle
  return (
    <li>
      <div className={`flex items-center gap-2 py-2 pr-5 hover:bg-gray-50 ${muted ? 'text-gray-400' : 'text-gray-900'}`} style={{ paddingLeft: 16 + depth * 28 }}>
        <button type="button" onClick={onToggle} disabled={!hasChildren} className="h-5 w-5 flex items-center justify-center text-gray-400 disabled:opacity-0">
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
        <Icon className={`h-4 w-4 shrink-0 ${muted ? 'text-gray-300' : 'text-primary-500'}`} />
        {to ? <Link to={to} className="font-medium hover:underline truncate">{title}</Link> : <span className="font-medium truncate">{title}</span>}
        {meta && <span className="text-sm text-gray-500 truncate">· {meta}</span>}
        {count && <span className="ml-auto text-xs text-gray-400">{count}</span>}
      </div>
      {open && children && <ul>{children}</ul>}
    </li>
  )
}
