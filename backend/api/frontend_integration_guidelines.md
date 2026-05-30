# TATVA — Frontend Integration & Developer Guidelines

This guide describes how to connect the newly exposed, rich **Risk Intelligence Engine APIs** to the frontend user interface. 

Follow these exact steps and copy the provided code blocks to integrate the **Interactive Suspect Proflier** and **Bidirectional Relation Details Overlay** inside your React components, completely replacing the static `Anomaly Detect` panel.

---

## 1. API Endpoints Expose Checklist
Verify that your local backend dev-server is running and exposes the following:
- `GET http://localhost:8000/api/insights/risk-profiles` (returns detailed actor risk profiles, explainability, evidence, and custom timelines).
- `GET http://localhost:8000/api/insights/relation-details?source=...&target=...` (returns bidirectional relationship metadata, communication/transaction counters, and narrative summaries).

---

## 2. Step-by-Step Frontend Changes

### Step A: Update `ForceGraphKnowledgeGraph.tsx`
We need to let the knowledge graph component capture clicking events on relationship links and bubble them up to the page.

1. Open [ForceGraphKnowledgeGraph.tsx](file:///c:/Users/Subarno%20Chakraborty/Coding/Hackathons/synchronicity/TATVA-Forensic-Investigation/frontend/src/components/ForceGraphKnowledgeGraph.tsx)
2. Update the `ForceGraphKnowledgeGraphProps` interface around line 13 to include `onLinkClick`:
```typescript
interface ForceGraphKnowledgeGraphProps {
  graphData: GraphRenderPayload | null;
  loading?: boolean;
  error?: string | null;
  onNodeClick?: (node: { id: string; name: string; type: string; val: string }) => void;
  onLinkClick?: (link: any) => void; // <-- ADD THIS LINE
  assessments?: AssessmentsMap;
  showCleared?: boolean;
  onToggleCleared?: (show: boolean) => void;
}
```
3. Destructure `onLinkClick` in the component arguments at line 133:
```typescript
export default function ForceGraphKnowledgeGraph({
  graphData,
  loading = false,
  error = null,
  onNodeClick,
  onLinkClick, // <-- ADD THIS LINE
  assessments = {},
  showCleared = true,
  onToggleCleared,
}: ForceGraphKnowledgeGraphProps) {
```
4. Attach `onLinkClick` to the `ForceGraph3D` component configuration around line 310:
```typescript
          // Links
          linkColor={(link) => linkColor(link as RenderLink)}
          linkWidth={(link) => ((link as RenderLink).confidence ?? 1) * 1.5}
          linkOpacity={0.5}
          linkDirectionalParticles={2}
          linkDirectionalParticleWidth={(link) => {
            const l = link as RenderLink;
            return l.type === 'TRANSFERRED_TO' || l.type === 'TRANSFERRED_MONEY' ? 2.5 : 1.5;
          }}
          linkDirectionalParticleColor={(link) => linkColor(link as RenderLink)}
          linkDirectionalParticleSpeed={getLinkParticleSpeed}
          onLinkClick={onLinkClick} // <-- ADD THIS LINE
```

---

### Step B: Update `InvestigationPage.tsx`
We will capture the link clicks, call the backend `/api/insights/relation-details` endpoint, and show the details in place of the static `Anomaly Detect` section on the top right.

1. Open [InvestigationPage.tsx](file:///c:/Users/Subarno%20Chakraborty/Coding/Hackathons/synchronicity/TATVA-Forensic-Investigation/frontend/src/pages/InvestigationPage.tsx)
2. Add new react states to track the selected relation, fetching state, and details near line 42:
```typescript
  // ── Relation Details state ──────────────────────────────────────────────
  const [selectedRelation, setSelectedRelation] = useState<any | null>(null)
  const [relationDetails, setRelationDetails] = useState<any | null>(null)
  const [relationLoading, setRelationLoading] = useState(false)
```
3. Add a fetching mechanism for premium risk profiles to unlock the full evidence hierarchy, narrative explanations, and notable/suspicious timelines:
```typescript
  const [riskProfiles, setRiskProfiles] = useState<any[]>([])

  useEffect(() => {
    fetch('http://localhost:8000/api/insights/risk-profiles')
      .then(res => res.json())
      .then(data => setRiskProfiles(data))
      .catch(err => console.error('Failed to load risk profiles:', err))
  }, [])

  // Derive the selected entity's risk profile
  const selectedProfile = useMemo(() => {
    if (!selectedEntity) return null
    return riskProfiles.find(p => p.person_id === selectedEntity.id)
  }, [selectedEntity, riskProfiles])
```
4. Add the `onLinkClick` handler function:
```typescript
  const handleLinkClick = async (link: any) => {
    const srcId = typeof link.source === 'object' ? link.source.id : link.source
    const tgtId = typeof link.target === 'object' ? link.target.id : link.target
    
    // Clear node selection to avoid sidebar clutter
    setSelectedEntity(null)
    
    setSelectedRelation(link)
    setRelationLoading(true)
    setRelationDetails(null)
    
    try {
      const res = await fetch(`http://localhost:8000/api/insights/relation-details?source=${srcId}&target=${tgtId}`)
      if (res.ok) {
        const data = await res.json()
        setRelationDetails(data)
      }
    } catch (err) {
      console.error('Failed to fetch relation details:', err)
    } finally {
      setRelationLoading(false)
    }
  }
```
5. Pass `handleLinkClick` to the `<ForceGraphKnowledgeGraph />` component inside the return layout (around line 240):
```tsx
            <ForceGraphKnowledgeGraph
              graphData={filteredGraphData}
              loading={graphLoading}
              error={graphError}
              onNodeClick={(node) => {
                setSelectedEntity(node)
                setSelectedRelation(null) // Clear selected relation on node click
              }}
              onLinkClick={handleLinkClick} // <-- ADD THIS LINE
              assessments={assessments}
              showCleared={showCleared}
              onToggleCleared={setShowCleared}
            />
```

---

### Step C: Replace static Anomaly HUD with Relation Intelligence Panel
Let's remove the static `"Anomaly Detect"` HTML overlay and replace it with a gorgeous, interactive, glassmorphic Relationship intelligence overlay.

1. Locate the `"Anomaly Detect"` block in `InvestigationPage.tsx` (around lines 275-281):
```tsx
          {/* REMOVE THIS OLD HUD ELEMENT */}
          <div className="absolute top-8 right-8 glass-panel p-3 rounded flex flex-col gap-1 z-10" style={{ border: '1px solid rgba(255,180,171,0.1)' }}>
            <div className="flex justify-between items-center gap-10">
              <span className="uppercase" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px', color: '#ffb4ab' }}>Anomaly Detect</span>
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: '#ffb4ab' }}>ALRT-02</span>
            </div>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '12px', color: 'rgba(255,180,171,0.7)' }}>CROSS-NODE TRAFFIC SPIKE</div>
          </div>
```

2. Replace it with this dynamic relation component:
```tsx
          {/* ── NEW DYNAMIC RELATION INTELLIGENCE HUD PANEL ── */}
          {selectedRelation && (
            <div className="absolute top-8 right-8 glass-panel p-5 rounded-lg flex flex-col gap-3 z-30 transition-all duration-300 animate-fade-in" 
                 style={{ border: '1px solid rgba(254,183,0,0.3)', width: '380px', backdropFilter: 'blur(16px)', background: 'rgba(19, 19, 20, 0.9)' }}>
              <div className="flex justify-between items-center border-b border-[#3f4852]/30 pb-2">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-[#feb700]" style={{ fontSize: '16px' }}>share_reviews</span>
                  <span className="uppercase font-bold" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px', color: '#feb700' }}>
                    Relation Intelligence
                  </span>
                </div>
                <button onClick={() => { setSelectedRelation(null); setRelationDetails(null); }} className="text-[#bec7d4] hover:text-[#feb700] transition-colors material-symbols-outlined text-sm">
                  close
                </button>
              </div>
              
              {relationLoading ? (
                <div className="flex flex-col items-center py-8 gap-2">
                  <div className="w-6 h-6 rounded-full border-2 border-[#feb700]/30 border-t-[#feb700] animate-spin" />
                  <span style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: '#bec7d4' }} className="uppercase tracking-widest">Reconstructing Connection...</span>
                </div>
              ) : relationDetails ? (
                <div className="space-y-4">
                  {/* Entity Breadcrumb Header */}
                  <div>
                    <div className="flex items-center gap-2 justify-center text-center py-2 px-3 bg-[#353436]/40 rounded mb-2 border border-[#3f4852]/20">
                      <span className="font-bold text-xs" style={{ color: '#ffdb9d' }}>{relationDetails.source_name}</span>
                      <span className="material-symbols-outlined text-[#feb700] animate-pulse" style={{ fontSize: '14px' }}>swap_horiz</span>
                      <span className="font-bold text-xs" style={{ color: '#ffdb9d' }}>{relationDetails.target_name}</span>
                    </div>
                    <div style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: '#bec7d4' }} className="text-center">
                      Direct Interactions: <strong className="text-[#feb700]">{relationDetails.interactions_count}</strong>
                    </div>
                  </div>

                  {/* Narrative summary */}
                  <div className="bg-[#feb700]/5 border border-[#feb700]/15 rounded p-3 text-xs leading-relaxed" style={{ color: '#bec7d4', fontFamily: 'Geist' }}>
                    <div className="font-bold text-[10px] text-[#feb700] uppercase tracking-wider mb-1" style={{ fontFamily: 'JetBrains Mono' }}>Narrative Summary</div>
                    {relationDetails.summary}
                  </div>

                  {/* Chronological events */}
                  <div className="space-y-2">
                    <div className="font-bold text-[10px] text-[#bec7d4] uppercase tracking-wider mb-1" style={{ fontFamily: 'JetBrains Mono' }}>Detailed Interacting Signals</div>
                    <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar pr-1">
                      {relationDetails.relations.map((rel: any, idx: number) => (
                        <div key={idx} className="border-l-2 border-[#feb700]/30 pl-3 py-1 space-y-1 hover:bg-[#353436]/20 rounded transition-all">
                          <div className="flex justify-between items-center text-[10px]" style={{ fontFamily: 'JetBrains Mono' }}>
                            <span className="px-1.5 py-0.5 rounded text-[8px] font-bold" style={{ background: '#feb700', color: '#412d00' }}>
                              {rel.type}
                            </span>
                            <span className="text-[#bec7d4]/60">
                              {rel.timestamp ? new Date(rel.timestamp).toLocaleString() : 'N/A'}
                            </span>
                          </div>
                          <p className="text-xs text-[#bec7d4]" style={{ fontFamily: 'Geist' }}>{rel.description}</p>
                          {rel.confidence && (
                            <div style={{ fontSize: '9px', color: '#feb700' }} className="font-mono">
                              Confidence: {(rel.confidence * 100).toFixed(0)}%
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-[#bec7d4] py-4 text-center">No connection data available.</div>
              )}
            </div>
          )}
```

---

### Step D: Update the Right Sidebar (EXPLAINABILITY tab)
Let's upgrade the EXPLAINABILITY side-panel to pull from the rich `selectedProfile` variables. This populates a full list of suspects scored by risk, showing explanations, exact contributing risk points, and notable timelines.

Modify the `EXPLAINABILITY` section in `InvestigationPage.tsx` starting near line 313:
```tsx
            {activeTab === 'EXPLAINABILITY' && (
              <>
                {/* Selected Node Details or Generic Intelligence Summary */}
                {selectedEntity ? (
                  <div className="glass-panel p-4 rounded-lg relative overflow-hidden mb-6" style={{ border: '1px solid rgba(254,183,0,0.2)' }}>
                    <div className="flex items-center gap-2 mb-3 border-b border-[#3f4852]/20 pb-2">
                      <span className="material-symbols-outlined text-sm" style={{ color: '#feb700' }}>info</span>
                      <span className="uppercase font-bold" style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: '#feb700' }}>Entity Details</span>
                      <span className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-bold" style={{ background: '#feb700', color: '#412d00' }}>
                        {selectedEntity.type}
                      </span>
                    </div>
                    <h4 style={{ fontFamily: 'Geist', fontSize: '18px', fontWeight: 'bold', color: '#e5e2e3', marginBottom: '8px' }}>
                      {selectedEntity.name}
                    </h4>
                    <p style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: '#bec7d4', marginBottom: '12px', wordBreak: 'break-all' }}>
                      ID: {selectedEntity.id} <br />
                      Sub-Type: <span className="text-[#feb700]">{selectedEntity.val}</span>
                    </p>

                    {/* Premium Profile Section */}
                    {selectedProfile ? (
                      <div className="mt-4 border-t border-[#3f4852]/30 pt-3 space-y-4">
                        {/* Risk Metric Badge */}
                        <div className="flex justify-between items-center bg-[#ef4444]/10 border border-[#ef4444]/20 p-2.5 rounded">
                          <div>
                            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: '#bec7d4' }}>FORENSIC RISK LEVEL</div>
                            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '16px', fontWeight: 'bold', color: '#ef4444' }}>
                              {selectedProfile.risk_level}
                            </div>
                          </div>
                          <div className="text-right">
                            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: '#bec7d4' }}>RISK SCORE</div>
                            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '20px', fontWeight: '900', color: '#ef4444' }}>
                              {selectedProfile.risk_score.toFixed(0)}%
                            </div>
                          </div>
                        </div>

                        {/* Narrative Explanation */}
                        <div className="space-y-1">
                          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: '#feb700' }} className="uppercase font-bold tracking-wider">Forensic Summary</div>
                          <p style={{ fontFamily: 'Geist', fontSize: '12px', color: '#bec7d4', lineHeight: '18px' }}>
                            {selectedProfile.explanation}
                          </p>
                        </div>

                        {/* Contributing Risk Factors */}
                        <div className="space-y-2">
                          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: '#feb700' }} className="uppercase font-bold tracking-wider">Contributing Factors ({selectedProfile.evidence.length})</div>
                          <div className="space-y-1.5 max-h-40 overflow-y-auto custom-scrollbar pr-1">
                            {selectedProfile.evidence.map((ev: any, idx: number) => (
                              <div key={idx} className="bg-[#1c1b1c] border border-[#3f4852]/30 rounded p-2 text-xs space-y-1">
                                <div className="flex justify-between items-center text-[#ffb4ab] font-bold">
                                  <span>{ev.rule_name}</span>
                                  <span>+{ev.weighted_contribution.toFixed(1)}</span>
                                </div>
                                {ev.evidence?.text_snippet && (
                                  <p className="italic text-[#bec7d4]/60">"{ev.evidence.text_snippet}"</p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Suspicious/Notable Actions Timeline */}
                        <div className="space-y-2">
                          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: '#feb700' }} className="uppercase font-bold tracking-wider">Notable Suspicious Actions</div>
                          <div className="space-y-2 max-h-40 overflow-y-auto custom-scrollbar pr-1">
                            {selectedProfile.timeline.map((act: any, idx: number) => (
                              <div key={idx} className="border-l border-[#feb700]/30 pl-2.5 py-0.5 space-y-0.5">
                                <div style={{ fontSize: '9px', color: '#bec7d4/60' }} className="font-mono">
                                  {new Date(act.timestamp).toLocaleString()}
                                </div>
                                <div className="text-xs font-bold text-[#ffdb9d]">{act.action}</div>
                                <p className="text-xs text-[#bec7d4]/80">{act.description}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : suspects.find(s => s.master_id === selectedEntity.id) ? (
                      /* Legacy suspects fallback if not resolved in premium */
                      <div className="mt-4 border-t border-[#3f4852]/30 pt-3">
                        <div style={{ fontFamily: 'JetBrains Mono', fontSize: '12px', color: '#ffb4ab', fontWeight: 'bold', marginBottom: '4px' }}>
                          Risk Score: {suspects.find(s => s.master_id === selectedEntity.id).risk_score}%
                        </div>
                        <ul className="list-disc pl-4 space-y-1 mt-2 text-xs text-[#bec7d4] font-sans">
                          {suspects.find(s => s.master_id === selectedEntity.id).reasons.map((reason: string, ri: number) => (
                            <li key={ri}>{reason}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    {/* ── Investigator Assessment Section (kept intact) ── */}
                    <div className="mt-4 border-t border-[#3f4852]/30 pt-3 space-y-2">
                      <div style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: '#bec7d4', letterSpacing: '0.05em', marginBottom: '6px' }}>INVESTIGATOR ASSESSMENT</div>
                      <select
                        value={detailStatus}
                        onChange={e => setDetailStatus(e.target.value as EntityStatus)}
                        className="w-full rounded px-2 py-1.5 text-xs outline-none border border-[#3f4852]/50 focus:border-[#feb700] transition-colors"
                        style={{ background: '#1c1b1c', color: STATUS_COLORS[detailStatus], fontFamily: 'JetBrains Mono', fontWeight: 'bold' }}
                      >
                        {STATUS_OPTIONS.map(s => (
                          <option key={s} value={s} style={{ color: STATUS_COLORS[s] }}>{s.replace(/_/g, ' ')}</option>
                        ))}
                      </select>
                      <textarea
                        value={detailReason}
                        onChange={e => setDetailReason(e.target.value)}
                        placeholder="Reason (optional)..."
                        rows={2}
                        className="w-full rounded px-2 py-1.5 text-xs outline-none border border-[#3f4852]/50 focus:border-[#feb700] transition-colors resize-none"
                        style={{ background: '#1c1b1c', color: '#e5e2e3', fontFamily: 'Geist', fontSize: '12px' }}
                      />
                      <button
                        onClick={() => saveAssessment(selectedEntity.id, detailStatus, detailReason)}
                        disabled={savingAssessment}
                        className="w-full py-2 rounded flex items-center justify-center gap-2 font-bold uppercase tracking-wider hover:brightness-110 active:scale-[0.98] transition-all disabled:opacity-50"
                        style={{ background: '#feb700', color: '#412d00', fontFamily: 'JetBrains Mono', fontSize: '11px' }}
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>save</span>
                        {savingAssessment ? 'Saving...' : 'Save Assessment'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="glass-panel p-4 rounded-lg relative overflow-hidden" style={{ border: '1px solid rgba(152,203,255,0.2)' }}>
                    <div className="flex items-center gap-2 mb-3">
                      <span className="material-symbols-outlined text-sm" style={{ color: '#98cbff' }}>psychology</span>
                      <span className="uppercase" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px', color: '#98cbff' }}>Intelligence Summary</span>
                      <span className="ml-auto" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: '#bec7d4' }}>MDL-84</span>
                    </div>
                    <p style={{ fontFamily: 'Geist', fontSize: '14px', color: '#bec7d4', lineHeight: '20px' }}>
                      Select any node in the knowledge graph to query real-time spatial properties, transaction history, centralities, and custom intelligence details. Click on any connection link to reveal real-time Relation Intelligence.
                    </p>
                    <div className="mt-4 flex gap-2">
                      <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(152,203,255,0.1)', border: '1px solid rgba(152,203,255,0.2)', color: '#98cbff' }}>INTERACTIVE</span>
                      <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(254,183,0,0.1)', border: '1px solid rgba(254,183,0,0.2)', color: '#ffdb9d' }}>REAL-TIME GRAPH</span>
                    </div>
                  </div>
                )}
```
