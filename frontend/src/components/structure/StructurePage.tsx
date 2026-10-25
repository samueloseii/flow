import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, ChevronDown, ChevronRight, Gauge, Globe, Handshake, Home, MapPin, Network } from 'lucide-react'
import api from '../../services/api'
import { useAuth } from '../../contexts/AuthContext'
import { Card, EmptyState, PageHeader, Spinner, secondaryButtonClass } from '../ui'

type Level = 'organization' | 'partner' | 'committee' | 'community' | 'household' | 'meter'
interface TreeNode { level: Level; id: string; name: string; meta: string | null; status: string | null; children: TreeNode[] }
interface Tree { root_level: Level; nodes: TreeNode[] }

const LEVELS: Level[] = ['organization', 'partner', 'committee', 'community', 'household', 'meter']
const ICONS: Record<Level, React.ComponentType<{ className?: string }>> = {
  organization: Globe, partner: Handshake, committee: Building2, community: MapPin, household: Home, meter: Gauge,
}
const CHILD_LABEL: Record<Level, [string, string] | null> = {
  organization: ['partner', 'partners'],
  partner: ['water committee', 'water committees'],
  committee: ['community', 'communities'],
  community: ['household', 'households'],
  household: ['meter', 'meters'],
  meter: null,
}
const TITLES: Record<Level, string> = {
  organization: 'All organizations',
  partner: 'Your partner',
  committee: 'Your water committee',
  community: 'Your community',
  household: 'Your household',
  meter: 'Meter',
}
const MANAGE = ['super_admin', 'partner_admin', 'community_admin']

// Organization → Partner → Water committee → Community → Household → Meter, as one outline.
// The server returns only the branch this login may see, starting at its own level.
export default function StructurePage() {
  const { user } = useAuth()
  const [tree, setTree] = useState<Tree | null>(null)
  const [loading, setLoading] = useState(true)
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})

  useEffect(() => {
    api.get('/structure/tree').then((r) => setTree(r.data)).catch(() => setTree({ root_level: 'organization', nodes: [] })).finally(() => setLoading(false))
  }, [])

  if (!user) return null
  if (loading || !tree) return <div className="flex justify-center py-20"><Spinner /></div>

  const canManage = MANAGE.includes(user.role)
  const toggle = (id: string) => setCollapsed((s) => ({ ...s, [id]: !s[id] }))
  const rootIndex = LEVELS.indexOf(tree.root_level)
  const path = LEVELS.slice(rootIndex).map((l) => (l === 'committee' ? 'Water committee' : l[0].toUpperCase() + l.slice(1))).join(' → ')
  const title = tree.nodes.length === 1 && tree.root_level !== 'organization' ? tree.nodes[0].name : TITLES[tree.root_level]

  const render = (n: TreeNode, depth: number) => {
    const label = CHILD_LABEL[n.level]
    const count = label ? `${n.children.length} ${n.children.length === 1 ? label[0] : label[1]}` : undefined
    const muted = !!n.status && n.status !== 'active'
    const Icon = ICONS[n.level]
    const open = !collapsed[n.id]
    const to = n.level === 'household' ? `/households/${n.id}` : undefined
    return (
      <li key={n.id}>
        <div className={`flex items-center gap-2 py-2 pr-5 hover:bg-gray-50 ${muted ? 'text-gray-400' : 'text-gray-900'}`} style={{ paddingLeft: 16 + depth * 28 }}>
          <button type="button" onClick={() => toggle(n.id)} disabled={!n.children.length} className="h-5 w-5 flex items-center justify-center text-gray-400 disabled:opacity-0">
            {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
          <Icon className={`h-4 w-4 shrink-0 ${muted ? 'text-gray-300' : 'text-primary-500'}`} />
          {to ? <Link to={to} className="font-medium hover:underline truncate">{n.name}</Link> : <span className="font-medium truncate">{n.name}</span>}
          {n.meta && <span className="text-sm text-gray-500 truncate">· {n.meta}</span>}
          {count && <span className="ml-auto text-xs text-gray-400">{count}</span>}
        </div>
        {open && n.children.length > 0 && <ul>{n.children.map((c) => render(c, depth + 1))}</ul>}
      </li>
    )
  }

  return (
    <div>
      <PageHeader title={title} subtitle={path}
        actions={canManage && (
          <>
            {user.role === 'super_admin' && <Link to="/partners" className={secondaryButtonClass}>Organizations &amp; partners</Link>}
            {['super_admin', 'partner_admin'].includes(user.role) && <Link to="/water-committees" className={secondaryButtonClass}>Water committees</Link>}
            <Link to="/communities" className={secondaryButtonClass}>Communities</Link>
            <Link to="/households" className={secondaryButtonClass}>Households &amp; import</Link>
          </>
        )} />
      <Card>
        {tree.nodes.length === 0 ? (
          <EmptyState icon={Network} title="Nothing in this branch yet" hint={canManage ? 'Use the buttons above to add the first level.' : undefined} />
        ) : (
          <ul className="py-2">{tree.nodes.map((n) => render(n, 0))}</ul>
        )}
      </Card>
    </div>
  )
}
