import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, CheckCircle, AlertTriangle, ArrowRight, Code, Shield, Zap, AlertOctagon, Network } from 'lucide-react';
import mermaid from 'mermaid';

function DiagramLog({ pipeline }) {
  const [expandedStages, setExpandedStages] = useState({});
  const [viewMode, setViewMode] = useState({});
  const [refDiagramMode, setRefDiagramMode] = useState('diagram');

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'default',
      securityLevel: 'loose',
      flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' }
    });
  }, []);

  useEffect(() => {
    if (pipeline && pipeline.length > 0) {
      const expanded = {};
      const modes = {};
      pipeline.forEach((stage, i) => {
        expanded[i] = true;
        const noRender = ['Ontology Constraints', 'LLM Output', 'Baseline'];
        modes[i] = noRender.includes(stage.stage) ? 'code' : 'diagram';
      });
      setExpandedStages(expanded);
      setViewMode(modes);

      const noAutoRender = new Set(['Ontology Constraints', 'LLM Output', 'Baseline']);
      const timer = setTimeout(() => {
        pipeline.forEach((stage, i) => {
          if (stage.mermaid && !noAutoRender.has(stage.stage)) {
            renderDiagram(i);
          }
        });
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [pipeline]);

  const renderDiagram = async (index) => {
    if (!pipeline || !pipeline[index]) return;
    const code = pipeline[index].mermaid;
    const el = document.getElementById(`dpipe-${index}`);
    if (!el || !code) return;
    try {
      el.innerHTML = '';
      const { svg } = await mermaid.render(`dpipe-svg-${index}-${Date.now()}`, code);
      el.innerHTML = svg;
    } catch {
      el.innerHTML = '';
      setViewMode(prev => ({ ...prev, [index]: 'code' }));
    }
  };

  const renderRefDiagram = async (code) => {
    const el = document.getElementById('ref-diagram');
    if (!el || !code) return;
    try {
      el.innerHTML = '';
      const { svg } = await mermaid.render(`ref-svg-${Date.now()}`, code);
      el.innerHTML = svg;
    } catch {
      el.innerHTML = '';
      setRefDiagramMode('code');
    }
  };

  const toggleStage = (index) => {
    const willExpand = !expandedStages[index];
    setExpandedStages(prev => ({ ...prev, [index]: willExpand }));
    if (willExpand && viewMode[index] === 'diagram' && pipeline[index].mermaid) {
      setTimeout(() => renderDiagram(index), 150);
    }
  };

  const toggleView = (index) => {
    const stage = pipeline[index];
    if (stage.stage === 'Ontology Constraints' || stage.stage === 'Baseline') return;
    const next = viewMode[index] === 'code' ? 'diagram' : 'code';
    setViewMode(prev => ({ ...prev, [index]: next }));
    if (next === 'diagram' && stage.mermaid) {
      setTimeout(() => renderDiagram(index), 100);
    }
  };

  if (!pipeline || pipeline.length === 0) {
    return (
      <div className="text-center py-12 text-slate-500">
        <Code className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p className="text-lg font-medium">No pipeline data</p>
        <p className="text-sm mt-1">Run an architecture query to see the diagram processing stages</p>
      </div>
    );
  }

  const stageConfig = {
    'Baseline':        { bg: 'bg-red-50',    border: 'border-red-300',    badge: 'bg-red-100 text-red-700' },
    'Ontology Constraints': { bg: 'bg-purple-50', border: 'border-purple-200', badge: 'bg-purple-100 text-purple-700' },
    'LLM Output':          { bg: 'bg-blue-50',   border: 'border-blue-200',   badge: 'bg-blue-100 text-blue-700' },
    'Syntax Sanitizer':    { bg: 'bg-amber-50',  border: 'border-amber-200',  badge: 'bg-amber-100 text-amber-700' },
    'Ontology Validator':  { bg: 'bg-green-50',  border: 'border-green-200',  badge: 'bg-green-100 text-green-700' },
  };

  const renderConstraints = (constraints, mermaidCode) => {
    if (!constraints) return null;
    return (
      <div className="space-y-4">
        {/* Hard Limits */}
        {constraints.hard_limits && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Hard Limits Enforced</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.entries(constraints.hard_limits).map(([key, val]) => (
                <div key={key} className="bg-purple-50 border border-purple-100 rounded-lg p-3 text-center">
                  <p className="text-lg font-bold text-purple-700">{val}</p>
                  <p className="text-xs text-purple-600">{key.replace(/_/g, ' ')}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Allowed Labels */}
        {constraints.allowed_labels && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Allowed Relationship Labels</p>
            <div className="flex flex-wrap gap-1.5">
              {constraints.allowed_labels.map((label, i) => (
                <span key={i} className="px-2 py-1 bg-green-50 border border-green-200 rounded text-xs font-medium text-green-700">{label}</span>
              ))}
            </div>
          </div>
        )}

        {/* Label Replacement Mapping */}
        {constraints.label_replacements && Object.keys(constraints.label_replacements).length > 0 && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
              Blocked Labels → Auto-Replacement ({Object.keys(constraints.label_replacements).length} rules)
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5">
              {Object.entries(constraints.label_replacements).map(([vague, standard], i) => (
                <div key={i} className="flex items-center space-x-2 px-2 py-1.5 bg-slate-50 border border-slate-200 rounded text-xs">
                  <span className="text-red-500 line-through font-medium">{vague}</span>
                  <ArrowRight className="h-3 w-3 text-slate-400 flex-shrink-0" />
                  <span className="text-green-700 font-medium">{standard}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Architectural Rules */}
        {constraints.architectural_rules && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Architectural Rules</p>
            <ul className="space-y-1">
              {constraints.architectural_rules.map((rule, i) => (
                <li key={i} className="flex items-start space-x-2 text-sm text-slate-700">
                  <Shield className="h-3.5 w-3.5 mt-0.5 flex-shrink-0 text-purple-500" />
                  <span>{rule}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Layer Order */}
        {constraints.layer_order && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Required Layer Order (top → bottom)</p>
            <div className="flex flex-wrap items-center gap-1">
              {constraints.layer_order.map((layer, i) => (
                <React.Fragment key={i}>
                  <span className="px-2 py-1 bg-slate-100 border border-slate-200 rounded text-xs font-medium text-slate-700">{layer}</span>
                  {i < constraints.layer_order.length - 1 && <span className="text-slate-300 text-xs">→</span>}
                </React.Fragment>
              ))}
            </div>
          </div>
        )}

        {/* Query-Relevant Subgraph */}
        {constraints.query_relevant_subgraph && constraints.query_relevant_subgraph.total_nodes > 0 && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
              <Network className="h-3.5 w-3.5 inline mr-1" />
              Query-Relevant Subgraph ({constraints.query_relevant_subgraph.total_nodes} nodes, {constraints.query_relevant_subgraph.total_edges} edges)
            </p>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {constraints.query_relevant_subgraph.nodes?.map((node, i) => (
                <span key={i} className={`px-2 py-1 rounded text-xs font-medium ${
                  node.layer === 'data' ? 'bg-emerald-50 border border-emerald-200 text-emerald-700' :
                  node.layer === 'product' ? 'bg-blue-50 border border-blue-200 text-blue-700' :
                  node.layer === 'ui' ? 'bg-indigo-50 border border-indigo-200 text-indigo-700' :
                  node.layer === 'platform' ? 'bg-orange-50 border border-orange-200 text-orange-700' :
                  'bg-slate-50 border border-slate-200 text-slate-700'
                }`}>
                  {node.label}
                </span>
              ))}
            </div>
            {constraints.query_relevant_subgraph.segregation_rules?.length > 0 && (
              <div className="mt-2">
                <p className="text-xs font-semibold text-red-500 mb-1">Segregation Rules</p>
                {constraints.query_relevant_subgraph.segregation_rules.map((rule, i) => (
                  <p key={i} className="text-xs text-red-600 flex items-center space-x-1">
                    <AlertOctagon className="h-3 w-3 flex-shrink-0" />
                    <span>{rule}</span>
                  </p>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Reference Example Diagram */}
        {mermaidCode && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Reference Diagram (from ontology subgraph)</p>
            <div className="border border-purple-200 rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 bg-purple-50 border-b border-purple-200">
                <span className="text-xs font-medium text-purple-600">
                  {refDiagramMode === 'code' ? 'Reference Source' : 'Reference Diagram'}
                </span>
                <button
                  onClick={() => {
                    const next = refDiagramMode === 'code' ? 'diagram' : 'code';
                    setRefDiagramMode(next);
                    if (next === 'diagram') setTimeout(() => renderRefDiagram(mermaidCode), 100);
                  }}
                  className="text-xs text-purple-600 hover:text-purple-800 font-medium flex items-center space-x-1"
                >
                  <Code className="h-3 w-3" />
                  <span>{refDiagramMode === 'code' ? 'Show Diagram' : 'Show Code'}</span>
                </button>
              </div>
              {refDiagramMode === 'code' ? (
                <pre className="p-4 text-xs text-slate-700 bg-purple-50/30 overflow-auto max-h-64 font-mono leading-relaxed whitespace-pre-wrap break-words">
                  {mermaidCode}
                </pre>
              ) : (
                <div id="ref-diagram" className="p-4 flex justify-center overflow-auto max-h-[400px] bg-white" />
              )}
            </div>
          </div>
        )}

        {/* Ontology Stats */}
        {constraints.ontology_stats && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Full Ontology Graph</p>
            <div className="flex items-center space-x-4 text-sm text-slate-600">
              <span><strong>{constraints.ontology_stats.nodes}</strong> nodes</span>
              <span><strong>{constraints.ontology_stats.edges}</strong> edges</span>
              <span><strong>{constraints.ontology_stats.relationship_types?.length || 0}</strong> relationship types</span>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="mb-2">
        <h2 className="text-xl font-bold text-slate-900">Diagram Pipeline</h2>
        <p className="text-sm text-slate-500 mt-1">
          From unconstrained baseline through ontology-guided generation to validated output
        </p>
        <div className="flex flex-wrap items-center gap-2 mt-3">
          {pipeline.map((stage, i) => {
            const cfg = stageConfig[stage.stage] || stageConfig['LLM Output'];
            return (
              <React.Fragment key={i}>
                <span className={`px-2 py-1 rounded text-xs font-medium ${cfg.badge}`}>{stage.stage}</span>
                {i < pipeline.length - 1 && <ArrowRight className="h-3 w-3 text-slate-300" />}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {pipeline.map((stage, index) => {
        const cfg = stageConfig[stage.stage] || stageConfig['LLM Output'];
        const isConstraints = stage.stage === 'Ontology Constraints';
        const isBaseline = stage.stage === 'Baseline';
        const isRawLLM = stage.stage === 'LLM Output';
        const hasMermaid = !!stage.mermaid;
        const cleanMessages = ['No syntax issues found', 'Passed all validation checks',
          'Ontology rules already satisfied', 'Ontology rules already satisfied — prompt constraints prevented issues pre-generation'];
        const hasChanges = stage.changes && stage.changes.length > 0 &&
          !stage.changes.some(c => cleanMessages.includes(c));
        const isClean = stage.changes && stage.changes.some(c => cleanMessages.includes(c));
        const isCode = viewMode[index] === 'code';
        const canToggle = hasMermaid && !isConstraints && !isBaseline;

        return (
          <div key={index} className={`rounded-lg border ${cfg.border} overflow-hidden`}>
            <button
              onClick={() => toggleStage(index)}
              className={`w-full flex items-center justify-between p-4 ${cfg.bg} hover:opacity-90 transition-opacity`}
            >
              <div className="flex items-center space-x-3">
                <div className={`flex items-center justify-center w-8 h-8 rounded-full shadow-sm ${
                  isBaseline ? 'bg-red-100' : 'bg-white'
                }`}>
                  <span className={`text-sm font-bold ${isBaseline ? 'text-red-700' : 'text-slate-700'}`}>
                    {isBaseline ? '0' : index + 1 - (pipeline.some(s => s.stage === 'Baseline') ? 1 : 0)}
                  </span>
                </div>
                <div className="text-left">
                  <h3 className={`font-semibold ${isBaseline ? 'text-red-900' : 'text-slate-900'}`}>{stage.stage}</h3>
                  <p className={`text-xs max-w-lg ${isBaseline ? 'text-red-600' : 'text-slate-600'}`}>{stage.description}</p>
                </div>
              </div>
              <div className="flex items-center space-x-2 flex-shrink-0">
                {isBaseline && (
                  <span className="flex items-center space-x-1 text-xs font-medium text-red-700 bg-red-100 px-2 py-1 rounded">
                    <AlertOctagon className="h-3 w-3" />
                    <span>No guardrails</span>
                  </span>
                )}
                {isConstraints && (
                  <span className="flex items-center space-x-1 text-xs font-medium text-purple-700 bg-purple-100 px-2 py-1 rounded">
                    <Shield className="h-3 w-3" />
                    <span>Pre-generation</span>
                  </span>
                )}
                {hasChanges && !isConstraints && !isBaseline && (
                  <span className="flex items-center space-x-1 text-xs font-medium text-amber-700 bg-amber-100 px-2 py-1 rounded">
                    <AlertTriangle className="h-3 w-3" />
                    <span>{stage.changes.length} change{stage.changes.length !== 1 ? 's' : ''}</span>
                  </span>
                )}
                {isClean && !isConstraints && !isBaseline && (
                  <span className="flex items-center space-x-1 text-xs font-medium text-green-700 bg-green-100 px-2 py-1 rounded">
                    <CheckCircle className="h-3 w-3" />
                    <span>Ontology rules satisfied</span>
                  </span>
                )}
                {expandedStages[index] ? <ChevronUp className="h-5 w-5 text-slate-400" /> : <ChevronDown className="h-5 w-5 text-slate-400" />}
              </div>
            </button>

            {expandedStages[index] && (
              <div className={`p-4 space-y-3 ${isBaseline ? 'bg-red-50/30' : 'bg-white'}`}>
                {isConstraints && stage.constraints && renderConstraints(stage.constraints, stage.mermaid)}

                {!isConstraints && stage.changes && stage.changes.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                      {isBaseline ? 'Why this is the baseline' : isRawLLM ? 'Notes' : 'Changes Applied'}
                    </p>
                    <ul className="space-y-1">
                      {stage.changes.map((change, ci) => (
                        <li key={ci} className="flex items-start space-x-2 text-sm text-slate-700">
                          <span className={`mt-1.5 flex-shrink-0 h-1.5 w-1.5 rounded-full ${
                            isBaseline ? 'bg-red-400' : hasChanges ? 'bg-amber-400' : 'bg-green-400'
                          }`} />
                          <span>{change}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {hasMermaid && !isConstraints && (
                  <div className={`border rounded-lg overflow-hidden ${isBaseline ? 'border-red-200' : 'border-slate-200'}`}>
                    <div className={`flex items-center justify-between px-3 py-2 border-b ${
                      isBaseline ? 'bg-red-50 border-red-200' : 'bg-slate-50 border-slate-200'
                    }`}>
                      <span className={`text-xs font-medium ${isBaseline ? 'text-red-600' : 'text-slate-500'}`}>
                        {isCode ? 'Mermaid Source' : 'Rendered Diagram'}
                        {isBaseline && ' (unconstrained)'}
                        {isRawLLM && isCode && ' (before processing)'}
                      </span>
                      {canToggle && (
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleView(index); }}
                          className="text-xs text-primary-600 hover:text-primary-800 font-medium flex items-center space-x-1"
                        >
                          <Code className="h-3 w-3" />
                          <span>{isCode ? 'Try Render' : 'Show Code'}</span>
                        </button>
                      )}
                    </div>
                    {isCode ? (
                      <pre className={`p-4 text-xs overflow-auto max-h-80 font-mono leading-relaxed whitespace-pre-wrap break-words ${
                        isBaseline ? 'text-red-800 bg-red-50/50' : 'text-slate-700 bg-slate-50'
                      }`}>
                        {stage.mermaid}
                      </pre>
                    ) : (
                      <div id={`dpipe-${index}`} className="p-4 flex justify-center overflow-auto max-h-[500px]" />
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default DiagramLog;
