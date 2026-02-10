import React, { useState, useEffect, useRef } from 'react';
import { ChevronDown, ChevronUp, CheckCircle, AlertTriangle, ArrowRight, Code } from 'lucide-react';
import mermaid from 'mermaid';

function DiagramLog({ pipeline }) {
  const [expandedStages, setExpandedStages] = useState({});
  const [showCode, setShowCode] = useState({});
  const diagramRefs = useRef({});

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
      const initial = {};
      pipeline.forEach((_, i) => { initial[i] = true; });
      setExpandedStages(initial);

      const timer = setTimeout(() => {
        pipeline.forEach((stage, i) => {
          renderDiagram(stage.mermaid, `diagram-log-${i}`);
        });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [pipeline]);

  const renderDiagram = async (code, elementId) => {
    const el = document.getElementById(elementId);
    if (!el || !code) return;
    try {
      el.innerHTML = '';
      const { svg } = await mermaid.render(`${elementId}-svg`, code);
      el.innerHTML = svg;
    } catch (err) {
      el.innerHTML = `<pre class="text-red-500 text-xs p-2">Render error: ${err.message}</pre>`;
    }
  };

  const toggleStage = (index) => {
    setExpandedStages(prev => ({ ...prev, [index]: !prev[index] }));
    if (!expandedStages[index]) {
      setTimeout(() => {
        renderDiagram(pipeline[index].mermaid, `diagram-log-${index}`);
      }, 100);
    }
  };

  const toggleCode = (index) => {
    setShowCode(prev => ({ ...prev, [index]: !prev[index] }));
  };

  if (!pipeline || pipeline.length === 0) {
    return (
      <div className="text-center py-12 text-slate-500">
        <Code className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p className="text-lg font-medium">No diagram pipeline data</p>
        <p className="text-sm mt-1">Run an architecture query to see the diagram processing stages</p>
      </div>
    );
  }

  const stageColors = {
    'LLM Output': { bg: 'bg-blue-50', border: 'border-blue-200', icon: 'text-blue-600', badge: 'bg-blue-100 text-blue-700' },
    'Syntax Sanitizer': { bg: 'bg-amber-50', border: 'border-amber-200', icon: 'text-amber-600', badge: 'bg-amber-100 text-amber-700' },
    'Ontology Validator': { bg: 'bg-green-50', border: 'border-green-200', icon: 'text-green-600', badge: 'bg-green-100 text-green-700' },
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Diagram Processing Pipeline</h2>
          <p className="text-sm text-slate-500 mt-1">
            Each stage shows how the architecture diagram was refined from raw LLM output to the final validated result
          </p>
        </div>
        <div className="flex items-center space-x-1 text-xs text-slate-400">
          {pipeline.map((stage, i) => (
            <React.Fragment key={i}>
              <span className={`px-2 py-1 rounded font-medium ${(stageColors[stage.stage] || stageColors['LLM Output']).badge}`}>
                {stage.stage}
              </span>
              {i < pipeline.length - 1 && <ArrowRight className="h-3 w-3" />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {pipeline.map((stage, index) => {
        const colors = stageColors[stage.stage] || stageColors['LLM Output'];
        const hasChanges = stage.changes && stage.changes.length > 0 && stage.changes[0] !== 'No syntax issues found' && stage.changes[0] !== 'Passed all validation checks';
        const isClean = stage.changes && (stage.changes.includes('No syntax issues found') || stage.changes.includes('Passed all validation checks'));

        return (
          <div key={index} className={`rounded-lg border ${colors.border} overflow-hidden`}>
            <button
              onClick={() => toggleStage(index)}
              className={`w-full flex items-center justify-between p-4 ${colors.bg} hover:opacity-90 transition-opacity`}
            >
              <div className="flex items-center space-x-3">
                <div className={`flex items-center justify-center w-8 h-8 rounded-full bg-white shadow-sm`}>
                  <span className="text-sm font-bold text-slate-700">{index + 1}</span>
                </div>
                <div className="text-left">
                  <h3 className="font-semibold text-slate-900">{stage.stage}</h3>
                  <p className="text-xs text-slate-600">{stage.description}</p>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                {hasChanges && (
                  <span className="flex items-center space-x-1 text-xs font-medium text-amber-700 bg-amber-100 px-2 py-1 rounded">
                    <AlertTriangle className="h-3 w-3" />
                    <span>{stage.changes.length} change{stage.changes.length !== 1 ? 's' : ''}</span>
                  </span>
                )}
                {isClean && (
                  <span className="flex items-center space-x-1 text-xs font-medium text-green-700 bg-green-100 px-2 py-1 rounded">
                    <CheckCircle className="h-3 w-3" />
                    <span>Clean</span>
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
              <div className="p-4 bg-white space-y-4">
                {stage.changes && stage.changes.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Changes Applied</p>
                    <ul className="space-y-1">
                      {stage.changes.map((change, ci) => (
                        <li key={ci} className="flex items-start space-x-2 text-sm text-slate-700">
                          <span className={`mt-1 flex-shrink-0 h-1.5 w-1.5 rounded-full ${hasChanges ? 'bg-amber-400' : 'bg-green-400'}`}></span>
                          <span>{change}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="border border-slate-200 rounded-lg overflow-hidden">
                  <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-b border-slate-200">
                    <span className="text-xs font-medium text-slate-500">Diagram at this stage</span>
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleCode(index); }}
                      className="text-xs text-slate-500 hover:text-slate-700 flex items-center space-x-1"
                    >
                      <Code className="h-3 w-3" />
                      <span>{showCode[index] ? 'Show Diagram' : 'Show Code'}</span>
                    </button>
                  </div>
                  {showCode[index] ? (
                    <pre className="p-4 text-xs text-slate-700 bg-slate-50 overflow-x-auto max-h-96 font-mono leading-relaxed">
                      {stage.mermaid}
                    </pre>
                  ) : (
                    <div
                      id={`diagram-log-${index}`}
                      className="p-4 flex justify-center overflow-x-auto min-h-[200px]"
                    />
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default DiagramLog;
