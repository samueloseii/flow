import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { Building2, ChevronRight, Handshake, Home, MapPin } from 'lucide-react'
import api from '../../services/api'
import { useAuth } from '../../contexts/AuthContext'
import { Card, EmptyState, PageHeader, Spinner, secondaryButtonClass } from '../ui'

type Level = 'root' | 'partner' | 'committee' | 'community'

interface Partner { id: string; name: string; country: string; communities_count: number }
interface Committee { id: string; name: string; partner_id: string; partner_name: string | null; region: string | null; community_count: number; household_count: number }
interface Community { id: string; name: string; region: string | null; partner_id: string; water_committee_id: string | null; water_committee_name: string | null; total_connections: number }
interface Household { id: string; account_number: string; head_of_household: string; address: string | null; has_meter: boolean; status: string; outstanding_balance: number; community_id: string }

const MANAGE = ['super_admin', 'partner_admin', 'community_admin']

// One page that walks the tree: Partner → Water committee → Community → Household.
// The account's level decides where the walk starts; everything above it is hidden.
export default function StructurePage({ level }: { level: Level }) {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [partners, setPartners] = useState<Partner[]>([])
  const [committees, setCommittees] = useState<Committee[]>([])
  const [communities, setCommunities] = useState<Community[]>([])
  const [households, setHouseholds] = useState<Household[]>([])
  const [loading, setLoading] = useState(true)

  const canManage = !!user && MANAGE.includes(user.role)

  // Where this account's branch starts.
  const start = useMemo(() => {
    if (!user) return null
    if (user.household_id) return { level: 'household' as const, id: user.household_id }
    if (user.community_id && user.role === 'reader') return { level: 'community' as const, id: user.community_id }
    if (user.water_committee_id) return { level: 'committee' as const, id: user.water_committee_id }
    if (user.partner_id) return { level: 'partner' as const, id: user.partner_id }
    return { level: 'root' as const, id: null }
  }, [user])

  useEffect(() => {
    if (!user) return
    setLoading(true)
    const wantsPartners = user.role === 'super_admin'
    Promise.all([
      wantsPartners ? api.get('/partners/').catch(() => ({ data: [] })) : Promise.resolve({ data: [] }),
      api.get('/water-committees/').catch(() => ({ data: [] })),
      api.get('/communities/').catch(() => ({ data: [] })),
      level === 'community' || level === 'committee' ? api.get('/households/', level === 'community' ? { params: { community_id: id } } : undefined).catch(() => ({ data: [] })) : Promise.resolve({ data: [] }),
    ])
      .then(([p, wc, c, h]) => { setPartners(p.data); setCommittees(wc.data); setCommunities(c.data); setHouseholds(h.data) })
      .finally(() => setLoading(false))
  }, [user, level, id])

  if (!user || !start) return null
  // Jump straight to the account's own level when the root is requested.
  if (level === 'root' && start.level !== 'root') {
    if (start.level === 'household') return <Navigate to={`/households/${start.id}`} replace />
    return <Navigate to={`/structure/${start.level}/${start.id}`} replace />
  }
  if (loading) return <div className="flex justify-center py-20"><Spinner /></div>

  const partner = level === 'partner' ? partners.find((p) => p.id === id) : undefined
  const committee = level === 'committee' ? committees.find((c) => c.id === id) : undefined
  const community = level === 'community' ? communities.find((c) => c.id === id) : undefined
  const parentCommittee = community ? committees.find((c) => c.id === community.water_committee_id) : level === 'committee' ? committee : undefined
  const parentPartner = parentCommittee ? partners.find((p) => p.id === parentCommittee.partner_id) : partner

  // Breadcrumb trimmed to what this account is allowed to see.
  const crumbs: { label: string; to?: string }[] = []
  if (start.level === 'root') {
    crumbs.push({ label: 'Partners', to: '/structure' })
    if (parentPartner) crumbs.push({ label: parentPartner.name, to: level === 'partner' ? undefined : `/structure/partner/${parentPartner.id}` })
  }
  if (parentCommittee && level !== 'partner' && start.level !== 'community') {
    crumbs.push({ label: parentCommittee.name, to: level === 'committee' ? undefined : `/structure/committee/${parentCommittee.id}` })
  }
  if (community) crumbs.push({ label: community.name })

  const title = level === 'root' ? 'Partners' : level === 'partner' ? partner?.name ?? 'Partner' : level === 'committee' ? committee?.name ?? 'Water committee' : community?.name ?? 'Community'
  const subtitle = level === 'root' ? 'Each partner supports one or more water committees.'
    : level === 'partner' ? 'Water committees supported by this partner.'
    : level === 'committee' ? 'Communities administered by this water committee.'
    : 'Households served in this community; open one for its meters and readings.'

  const manageLink = level === 'root' ? { to: '/partners', label: 'Manage partners' }
    : level === 'partner' ? { to: '/water-committees', label: 'Manage water committees' }
    : level === 'committee' ? { to: '/communities', label: 'Manage communities' }
    : { to: '/households', label: 'Manage households' }

  return (
    <div>
      {crumbs.length > 1 && (
        <nav className="flex items-center gap-1 text-sm text-gray-500 mb-4">
          {crumbs.map((c, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-gray-300" />}
              {c.to ? <Link to={c.to} className="hover:text-gray-900">{c.label}</Link> : <span className="text-gray-900 font-medium">{c.label}</span>}
            </span>
          ))}
        </nav>
      )}
      <PageHeader
        title={title}
        subtitle={subtitle}
        actions={canManage && <Link to={manageLink.to} className={secondaryButtonClass}>{manageLink.label}</Link>}
      />

      {level === 'root' && (
        <Rows
          empty={{ icon: Handshake, title: 'No partners yet', hint: canManage ? 'Add the first partner organisation under Manage partners.' : undefined }}
          rows={partners.map((p) => ({
            key: p.id, icon: Handshake, title: p.name, meta: p.country,
            counts: `${committees.filter((c) => c.partner_id === p.id).length} water committees · ${p.communities_count} communities`,
            onClick: () => navigate(`/structure/partner/${p.id}`),
          }))}
        />
      )}
      {level === 'partner' && (
        <Rows
          empty={{ icon: Building2, title: 'No water committees under this partner' }}
          rows={committees.filter((c) => c.partner_id === id).map((c) => ({
            key: c.id, icon: Building2, title: c.name, meta: c.region ?? '',
            counts: `${c.community_count} communities · ${c.household_count} households`,
            onClick: () => navigate(`/structure/committee/${c.id}`),
          }))}
        />
      )}
      {level === 'committee' && (
        <Rows
          empty={{ icon: MapPin, title: 'No communities under this water committee', hint: canManage ? 'Add one under Manage communities.' : undefined }}
          rows={communities.filter((c) => c.water_committee_id === id).map((c) => ({
            key: c.id, icon: MapPin, title: c.name, meta: c.region ?? '',
            counts: `${households.filter((h) => h.community_id === c.id).length} households`,
            onClick: () => navigate(`/structure/community/${c.id}`),
          }))}
        />
      )}
      {level === 'community' && (
        <Rows
          empty={{ icon: Home, title: 'No households in this community', hint: canManage ? 'Register households one by one or import a CSV under Manage households.' : undefined }}
          rows={households.map((h) => ({
            key: h.id, icon: Home, title: h.head_of_household, meta: `${h.account_number}${h.address ? ` · ${h.address}` : ''}`,
            counts: h.has_meter ? 'Meter fitted' : 'No meter',
            onClick: () => navigate(`/households/${h.id}`),
          }))}
        />
      )}
    </div>
  )
}

function Rows({ rows, empty }: {
  rows: { key: string; icon: React.ComponentType<{ className?: string }>; title: string; meta: string; counts: string; onClick: () => void }[]
  empty: { icon: React.ComponentType<{ className?: string }>; title: string; hint?: string }
}) {
  if (rows.length === 0) return <Card><EmptyState {...empty} /></Card>
  return (
    <Card>
      <ul className="divide-y divide-gray-100">
        {rows.map((r) => (
          <li key={r.key}>
            <button type="button" onClick={r.onClick} className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-gray-50">
              <r.icon className="h-5 w-5 text-primary-500 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 truncate">{r.title}</p>
                {r.meta && <p className="text-sm text-gray-500 truncate">{r.meta}</p>}
              </div>
              <span className="text-sm text-gray-500 hidden sm:block">{r.counts}</span>
              <ChevronRight className="h-4 w-4 text-gray-300" />
            </button>
          </li>
        ))}
      </ul>
    </Card>
  )
}
