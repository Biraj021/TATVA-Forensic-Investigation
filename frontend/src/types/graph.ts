// ─────────────────────────────────────────────────────────────────────────────
// Shared graph types — mirrors backend GraphRenderPayload schema exactly.
// Import from here in ALL files that need graph data shapes.
// Do NOT re-declare these in individual components.
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// Entity status — set by investigator, stored in PostgreSQL (not Neo4j)
// ─────────────────────────────────────────────────────────────────────────────

export type EntityStatus = 'ACTIVE' | 'CLEARED' | 'PERSON_OF_INTEREST' | 'PRIORITY_TARGET';

export interface AssessmentRecord {
  status: EntityStatus;
  reason?: string;
  updated_at?: string;
}

export type AssessmentsMap = Record<string, AssessmentRecord>;

// ─────────────────────────────────────────────────────────────────────────────
// Graph node / link shapes — mirror backend GraphRenderPayload exactly.
// ─────────────────────────────────────────────────────────────────────────────

export interface RenderNode {
  id: string;
  label: string;
  type: string;      // master_type: PERSON | PLACE | INFRASTRUCTURE | ENTITY
  sub_type: string;  // entity_types[0]: ACCOUNT | CELL_TOWER | VEHICLE | …
  risk_score: number;
  // Added by react-force-graph-3d at runtime (do not set manually)
  x?: number;
  y?: number;
  z?: number;
}

export interface RenderLink {
  source: string | RenderNode;
  target: string | RenderNode;
  type: string;
  confidence: number;
}

export interface GraphRenderPayload {
  nodes: RenderNode[];
  links: RenderLink[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Graph view / filter types
// ─────────────────────────────────────────────────────────────────────────────

export type GraphView = 'FULL' | 'PEOPLE' | 'ACCOUNTS' | 'LOCATIONS' | 'DEVICES';

// ─────────────────────────────────────────────────────────────────────────────
// GRAPH_FILTERS — single source of truth for all filter definitions.
//
// Each filter defines:
//   nodeTypes  — master_type values that form the CORE of this view (primary nodes).
//   nodeSubTypes — sub_type values that form the CORE of this view.
//   linkTypes  — link types that are "native" to this view (used to show
//                directly connected neighbours even when they fall outside
//                the core node types, implementing the entity-centric subgraph).
//
// Algorithm:
//   1. Start with "core" nodes that match nodeTypes OR nodeSubTypes.
//   2. Follow any link in linkTypes from a core node — include the OTHER end
//      of that link as a "connected neighbour", even if it doesn't match the
//      core node types.
//   3. Include only links where BOTH endpoints are in (core ∪ neighbours).
// ─────────────────────────────────────────────────────────────────────────────

export interface GraphFilterDef {
  /** Sidebar display label */
  label: string;
  /** Material Symbols icon name */
  icon: string;
  /** master_type values that are "core" entities for this view */
  nodeTypes: string[];
  /** sub_type values that are "core" entities for this view */
  nodeSubTypes: string[];
  /** Relation types that connect core entities to their direct neighbours */
  linkTypes: string[];
  /** Optional badge rendered next to the label */
  badge?: string;
}

export const GRAPH_FILTERS: Record<GraphView, GraphFilterDef> = {
  FULL: {
    label: 'Entity Graph',
    icon: 'hub',
    nodeTypes: [],        // empty → matches everything
    nodeSubTypes: [],
    linkTypes: [],
    badge: 'LIVE',
  },
  PEOPLE: {
    label: 'People',
    icon: 'groups',
    nodeTypes: ['PERSON'],
    nodeSubTypes: ['PERSON'],
    linkTypes: [
      'CALLED',
      'MESSAGED',
      'EMAILED',
      'ASSOCIATED_WITH',
      'TRANSFERRED_MONEY',
      'TRANSFERRED_TO',
    ],
  },
  ACCOUNTS: {
    label: 'Accounts',
    icon: 'account_balance',
    nodeTypes: ['ENTITY'],
    nodeSubTypes: ['ACCOUNT', 'BANK_ACCOUNT', 'UPI', 'WALLET'],
    linkTypes: [
      'TRANSFERRED_TO',
      'TRANSFERRED_MONEY',
      'RECEIVED_FROM',
      'TRANSACTION',
      'OWNS_ACCOUNT',
    ],
  },
  LOCATIONS: {
    label: 'Locations',
    icon: 'location_on',
    nodeTypes: ['PLACE', 'INFRASTRUCTURE'],
    nodeSubTypes: ['LOCATION', 'CELL_TOWER', 'ATM', 'WAREHOUSE', 'PLACE'],
    linkTypes: [
      'LOCATED_AT',
      'VISITED',
      'NEAR',
      'MOVED_TO',
      'CONNECTED_TO_TOWER',
    ],
  },
  DEVICES: {
    label: 'Devices',
    icon: 'devices',
    nodeTypes: ['INFRASTRUCTURE'],
    nodeSubTypes: [
      'PHONE_NUMBER',
      'DEVICE',
      'WEARABLE_DEVICE',
      'EMAIL_ADDRESS',
      'PLATFORM',
      'CAMERA',
      'TRACKER',
      'SOCIAL_HANDLE',
      'CHAT_ACCOUNT',
      'TELEGRAM',
      'WHATSAPP',
    ],
    linkTypes: [
      'CALLED',
      'MESSAGED',
      'EMAILED',
      'COMMUNICATED_WITH',
      'CONNECTED_TO_TOWER',
      'DETECTED',
    ],
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// filterGraphData — derives a subgraph from fullGraphData given a GraphView.
//
// "Entity-centric subgraph" strategy:
//   1. Identify core nodes (match nodeTypes or nodeSubTypes).
//   2. Walk every link in linkTypes — if one end is a core node, pull in the
//      other end as a "neighbour".
//   3. The visible node set = core ∪ neighbours.
//   4. Keep only links where BOTH source and target are in the visible set.
//
// Calling with GraphView='FULL' returns fullGraphData unchanged (no copy).
// ─────────────────────────────────────────────────────────────────────────────

function nodeId(endpoint: string | RenderNode): string {
  return typeof endpoint === 'string' ? endpoint : endpoint.id;
}

export function filterGraphData(
  full: GraphRenderPayload,
  view: GraphView,
): GraphRenderPayload {
  if (view === 'FULL') return full;

  const def = GRAPH_FILTERS[view];

  // ── Step 1: identify core nodes ──────────────────────────────────────────
  const coreIds = new Set<string>();
  for (const node of full.nodes) {
    const matchesType    = def.nodeTypes.includes(node.type);
    const matchesSubType = def.nodeSubTypes.includes(node.sub_type);
    if (matchesType || matchesSubType) {
      coreIds.add(node.id);
    }
  }

  // ── Step 2: pull in directly connected neighbours via native link types ──
  const neighbourIds = new Set<string>();
  const nativeLinkSet = new Set(def.linkTypes);

  for (const link of full.links) {
    const src = nodeId(link.source);
    const tgt = nodeId(link.target);
    if (!nativeLinkSet.has(link.type)) continue;

    if (coreIds.has(src) && !coreIds.has(tgt)) neighbourIds.add(tgt);
    if (coreIds.has(tgt) && !coreIds.has(src)) neighbourIds.add(src);
  }

  const visibleIds = new Set([...coreIds, ...neighbourIds]);

  // ── Step 3: filter nodes ─────────────────────────────────────────────────
  const filteredNodes = full.nodes.filter(n => visibleIds.has(n.id));

  // ── Step 4: filter links — both endpoints must be visible ────────────────
  const filteredLinks = full.links.filter(link => {
    const src = nodeId(link.source);
    const tgt = nodeId(link.target);
    return visibleIds.has(src) && visibleIds.has(tgt);
  });

  return { nodes: filteredNodes, links: filteredLinks };
}
