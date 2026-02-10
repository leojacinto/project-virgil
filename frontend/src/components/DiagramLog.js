import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, CheckCircle, AlertTriangle, ArrowRight, Code, Shield, Zap } from 'lucide-react';
import mermaid from 'mermaid';

function DiagramLog({ pipeline }) {
  const [expandedStages, setExpandedStages] = useState({});
  const [viewMode, setViewMode] = useState({});

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
        // Ontology Constraints and LLM Output never render as diagram
        const isConstraints = stage.stage === 'Ontology Constraints';
        const isRawLLM = stage.stage === 'LLM Output';
        modes[i] = (isConstraints || isRawLLM) ? 'code' : 'diagram';
      });
      setExpandedStages(expanded);
      setViewMode(modes);

      // Only render stages that have valid mermaid and are not raw/constraints
      const timer = setTimeout(() => {
        pipeline.forEach((stage, i) => {
          if (stage.mermaid && stage.stage !== 'Ontology Constraints' && stage.stage !== 'LLM Output') {
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
      const id = `dpipe-svg-${index}-${Date.now()}`;
      const { svg } = await mermaid.render(id, code);
      el.innerHTML = svg;
    } catch (err) {
      // On failure, show code instead — no error dump
      el.innerHTML = '';
      setViewMode(prev => ({ ...prev, [index]: 'code' }));
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
    if (stage.stage === 'Ontology Constraints') return; // no toggle for constraints
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
    'Ontology Constraints': { bg: 'bg-purple-50', border: 'border-purple-200', badge: 'bg-purple-100 text-purple-700', Icon: Shield },
    'LLM Output': { bg: 'bg-blue-50', border: 'border-blue-200', badge: 'bg-blue-100 text-blue-700', Icon: Zap },
    'Syntax Sanitizer': { bg: 'bg-amber-50', border: 'border-amber-200', badge: 'bg-amber-100 text-amber-700', Icon: Code },
    'Ontology Validator': { bg: 'bg-green-50', border: 'border-green-200', badge: 'bg-green-100 text-green-700', Icon: CheckCircle },
  };

  const renderConstraints = (constraints) => {
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
                <span key={i} className="px-2 py-1 bg-green-50 border border-green-200 rounded text-xs font-medium text-green-700">
                  {label}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Blocked Labels */}
        {constraints.blocked_labels && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Blocked Labels (auto-replaced or removed)</p>
            <div className="flex flex-wrap gap-1.5">
              {constraints.blocked_labels.map((label, i) => (
                <span key={i} className="px-2 py-1 bg-red-50 border border-red-200 rounded text-xs font-medium text-red-600 line-through">
                  {label}
                </span>
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
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Required Layer Order (top to bottom)</p>
            <div className="flex items-center space-x-1">
              {constraints.layer_order.map((layer, i) => (
                <React.Fragment key={i}>
                  <span className="px-2 py-1 bg-slate-100 border border-slate-200 rounded text-xs font-medium text-slate-700">
                    {layer}
                  </span>
                  {i < constraints.layer_order.length - 1 && (
                    <span className="text-slate-300 text-xs">→</span>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
        )}

        {/* Ontology Stats */}
        {constraints.ontology_stats && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Ontology Graph</p>
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
          How the architecture diagram was shaped from ontology constraints through LLM generation to the final validated result
        </p>
        <div className="flex flex-wrap items-center gap-2 mt-3">
          {pipeline.map((stage, i) => {
            const cfg = stageConfig[stage.stage] || stageConfig['LLM Output'];
            return (
              <React.Fragment key={i}>
                <span className={`px-2 py-1 rounded text-xs font-medium ${cfg.badge}`}>
                  {stage.stage}
                </span>
                {i < pipeline.length - 1 && <ArrowRight className="h-3 w-3 text-slate-300" />}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {pipeline.map((stage, index) => {
        const cfg = stageConfig[stage.stage] || stageConfig['LLM Output'];
        const isConstraints = stage.stage === 'Ontology Constraints';
        const isRawLLM = stage.stage === 'LLM Output';
        const hasMermaid = !!stage.mermaid;
        const hasChanges = stage.changes && stage.changes.length > 0 &&
          !stage.changes.includes('No syntax issues found') &&
          !stage.changes.includes('Passed all validation checks') &&
          !stage.changes.includes('Ontology rules already satisfied');
        const isClean = stage.changes && (
          stage.changes.includes('No syntax issues found') ||
          stage.changes.includes('Passed all validation checks') ||
          stage.changes.includes('Ontology rules already satisfied')
        );
        const isCode = viewMode[index] === 'code';
        const canToggle = hasMermaid && !isConstraints;

        return (
          <div key={index} className={`rounded-lg border ${cfg.border} overflow-hidden`}>
            <button
              onClick={() => toggleStage(index)}
              className={`w-full flex items-center justify-between p-4 ${cfg.bg} hover:opacity-90 transition-opacity`}
            >
              <div className="flex items-center space-x-3">
                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-white shadow-sm">
                  <span className="text-sm font-bold text-slate-700">{index + 1}</span>
                </div>
                <div className="text-left">
                  <h3 className="font-semibold text-slate-900">{stage.stage}</h3>
                  <p className="text-xs text-slate-600 max-w-lg">{stage.description}</p>
                </div>
              </div>
              <div className="flex items-center space-x-2 flex-shrink-0">
                {isConstraints && (
                  <span className="flex items-center space-x-1 text-xs font-medium text-purple-700 bg-purple-100 px-2 py-1 rounded">
                    <Shield className="h-3 w-3" />
                    <span>Pre-generation</span>
                  </span>
                )}
                {hasChanges && !isConstraints && (
                  <span className="flex items-center space-x-1 text-xs font-medium text-amber-700 bg-amber-100 px-2 py-1 rounded">
                    <AlertTriangle className="h-3 w-3" />
                    <span>{stage.changes.length} change{stage.changes.length !== 1 ? 's' : ''}</span>
                  </span>
                )}
                {isClean && !isConstraints && (
                  <span className="flex items-center space-x-1 text-xs font-medium text-green-700 bg-green-100 px-2 py-1 rounded">
                    <CheckCircle className="h-3 w-3" />
                    <span>Ontology rules satisfied</span>
                  </span>
                )}
                {expandedStages[index] ? (
                  <ChevronUp className="h-5 w-5 text-slate-400" />
                ) : (
                  <ChevronDown className="h-5 w-5 text-slate-400" />
                )}
              </div>
            </button>

            {expandedStages[index] && (
              <div className="p-4 bg-white space-y-3">
                {/* Ontology Constraints: show structured data */}
                {isConstraints && stage.constraints && renderConstraints(stage.constraints)}

                {/* Non-constraint stages: show changes + diagram/code */}
                {!isConstraints && stage.changes && stage.changes.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                      {isRawLLM ? 'Notes' : 'Changes Applied'}
                    </p>
                    <ul className="space-y-1">
                      {stage.changes.map((change, ci) => (
                        <li key={ci} className="flex items-start space-x-2 text-sm text-slate-700">
                          <span className={`mt-1.5 flex-shrink-0 h-1.5 w-1.5 rounded-full ${hasChanges ? 'bg-amber-400' : 'bg-green-400'}`} />
                          <span>{change}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {hasMermaid && !isConstraints && (
                  <div className="border border-slate-200 rounded-lg overflow-hidden">
                    <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-b border-slate-200">
                      <span className="text-xs font-medium text-slate-500">
                        {isCode ? 'Mermaid Source' : 'Rendered Diagram'}
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
                      <pre className="p-4 text-xs text-slate-700 bg-slate-50 overflow-auto max-h-80 font-mono leading-relaxed whitespace-pre-wrap break-words">
                        {stage.mermaid}
                      </pre>
                    ) : (
                      <div
                        id={`dpipe-${index}`}
                        className="p-4 flex justify-center overflow-auto max-h-[500px]"
                      />
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
