import React, { useState, useEffect, useRef } from 'react';
import { Download, ExternalLink, ChevronDown, ChevronUp, CheckCircle, AlertTriangle, FileText, Loader2, ShieldCheck, Brain, Network } from 'lucide-react';
import { downloadMermaid, exportToPDF } from '../utils/exportUtils';
import ReactMarkdown from 'react-markdown';
import mermaid from 'mermaid';

function ResultsDisplay({ result }) {
  const [expandedSections, setExpandedSections] = useState({
    diagram: true,
    analysis: true,
    recommendations: true,
    metadata: false
  });
  const [exporting, setExporting] = useState(false);
  const resultsRef = useRef(null);

  useEffect(() => {
    mermaid.initialize({ 
      startOnLoad: true,
      theme: 'default',
      securityLevel: 'loose',
      flowchart: { useMaxWidth: true, htmlLabels: true }
    });
    mermaid.contentLoaded();
  }, [result]);

  const toggleSection = (section) => {
    setExpandedSections({
      ...expandedSections,
      [section]: !expandedSections[section]
    });
  };

  const getPriorityColor = (priority) => {
    switch (priority?.toLowerCase()) {
      case 'high':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'low':
        return 'bg-green-100 text-green-800 border-green-200';
      default:
        return 'bg-slate-100 text-slate-800 border-slate-200';
    }
  };

  const getConfidenceBadge = (confidence) => {
    switch (confidence) {
      case 'rule-backed':
        return {
          color: 'bg-emerald-100 text-emerald-800 border-emerald-200',
          icon: <ShieldCheck className="h-3 w-3" />,
          label: 'Rule-Backed'
        };
      case 'ontology-validated':
        return {
          color: 'bg-blue-100 text-blue-800 border-blue-200',
          icon: <Network className="h-3 w-3" />,
          label: 'Ontology-Validated'
        };
      case 'llm-generated':
        return {
          color: 'bg-amber-100 text-amber-800 border-amber-200',
          icon: <Brain className="h-3 w-3" />,
          label: 'LLM-Generated'
        };
      default:
        return null;
    }
  };

  const handleDownloadDiagram = () => {
    if (result.diagram_path) {
      window.open(`/api/diagrams/${result.diagram_path}`, '_blank');
    }
  };

  return (
    <div className="space-y-6" ref={resultsRef}>
      {/* PDF Export bar */}
      <div className="flex justify-end">
        <button
          onClick={async () => {
            setExporting(true);
            try {
              await exportToPDF(resultsRef.current, 'Architecture_Analysis');
            } finally {
              setExporting(false);
            }
          }}
          disabled={exporting}
          className="flex items-center space-x-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-600 transition-colors disabled:opacity-50"
          title="Export analysis to PDF"
        >
          {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
          <span>Export PDF</span>
        </button>
      </div>

      {result.mermaid_diagram && (
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg">
          <button
            onClick={() => toggleSection('diagram')}
            className="w-full flex items-center justify-between p-6 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
          >
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
              Architecture Diagram
            </h3>
            {expandedSections.diagram ? (
              <ChevronUp className="h-5 w-5 text-slate-500" />
            ) : (
              <ChevronDown className="h-5 w-5 text-slate-500" />
            )}
          </button>
          {expandedSections.diagram && (
            <div className="px-6 pb-6 border-t border-slate-200 dark:border-slate-700">
              <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-6 mt-4 overflow-x-auto relative group">
                <button
                  onClick={() => downloadMermaid(result.mermaid_diagram, 'architecture_diagram')}
                  className="absolute top-2 right-2 p-1.5 rounded-md bg-white/80 dark:bg-slate-700/80 border border-slate-200 dark:border-slate-600 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-white dark:hover:bg-slate-700 transition-all opacity-0 group-hover:opacity-100 z-10"
                  title="Download Mermaid syntax"
                >
                  <Download className="h-3.5 w-3.5" />
                </button>
                <div className="mermaid">
                  {result.mermaid_diagram}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg">
        <button
          onClick={() => toggleSection('analysis')}
          className="w-full flex items-center justify-between p-6 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
        >
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
            Architecture Analysis
          </h3>
          {expandedSections.analysis ? (
            <ChevronUp className="h-5 w-5 text-slate-500" />
          ) : (
            <ChevronDown className="h-5 w-5 text-slate-500" />
          )}
        </button>
        {expandedSections.analysis && (
          <div className="px-6 pb-6 border-t border-slate-200 dark:border-slate-700">
            <div className="prose prose-slate dark:prose-invert max-w-none mt-4">
              <ReactMarkdown>{result.analysis}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg">
        <button
          onClick={() => toggleSection('recommendations')}
          className="w-full flex items-center justify-between p-6 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
        >
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
            Recommendations ({result.recommendations?.length || 0})
          </h3>
          {expandedSections.recommendations ? (
            <ChevronUp className="h-5 w-5 text-slate-500" />
          ) : (
            <ChevronDown className="h-5 w-5 text-slate-500" />
          )}
        </button>
        {expandedSections.recommendations && (
          <div className="px-6 pb-6 border-t border-slate-200 dark:border-slate-700">
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mt-4 mb-4">
              <p className="text-sm font-medium text-blue-900 dark:text-blue-200 mb-2">Priority Levels:</p>
              <div className="flex flex-wrap gap-4 text-sm">
                <div className="flex items-center space-x-2">
                  <span className="px-2 py-1 text-xs font-medium rounded border bg-red-100 text-red-800 border-red-200">HIGH</span>
                  <span className="text-blue-800 dark:text-blue-300">Critical - implement first</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="px-2 py-1 text-xs font-medium rounded border bg-yellow-100 text-yellow-800 border-yellow-200">MEDIUM</span>
                  <span className="text-blue-800 dark:text-blue-300">Important - implement second</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="px-2 py-1 text-xs font-medium rounded border bg-green-100 text-green-800 border-green-200">LOW</span>
                  <span className="text-blue-800 dark:text-blue-300">Nice-to-have - if time allows</span>
                </div>
              </div>
            </div>
            {result.recommendations && result.recommendations.some(r => r.confidence) && (
              <div className="bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-700 rounded-lg p-4 mb-4">
                <p className="text-sm font-medium text-slate-900 dark:text-white mb-2">Confidence Source:</p>
                <div className="flex flex-wrap gap-4 text-sm">
                  <div className="flex items-center space-x-2">
                    <span className="px-2 py-1 text-xs font-medium rounded border bg-emerald-100 text-emerald-800 border-emerald-200 flex items-center space-x-1">
                      <ShieldCheck className="h-3 w-3" /><span>Rule-Backed</span>
                    </span>
                    <span className="text-slate-600 dark:text-slate-400">Verified by deterministic rule engine</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="px-2 py-1 text-xs font-medium rounded border bg-blue-100 text-blue-800 border-blue-200 flex items-center space-x-1">
                      <Network className="h-3 w-3" /><span>Ontology-Validated</span>
                    </span>
                    <span className="text-slate-600 dark:text-slate-400">Components exist in ontology graph</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="px-2 py-1 text-xs font-medium rounded border bg-amber-100 text-amber-800 border-amber-200 flex items-center space-x-1">
                      <Brain className="h-3 w-3" /><span>LLM-Generated</span>
                    </span>
                    <span className="text-slate-600 dark:text-slate-400">No deterministic backing</span>
                  </div>
                </div>
              </div>
            )}
            <div className="space-y-4">
              {result.recommendations && result.recommendations.length > 0 ? (
                result.recommendations.map((rec, index) => (
                  <div
                    key={index}
                    className="border border-slate-200 dark:border-slate-700 rounded-lg p-4 hover:shadow-sm transition-shadow"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h4 className="font-semibold text-slate-900 dark:text-white flex items-center space-x-2">
                        <CheckCircle className="h-5 w-5 text-green-600" />
                        <span>{rec.title}</span>
                      </h4>
                      <div className="flex items-center space-x-2 flex-shrink-0">
                        {rec.confidence && getConfidenceBadge(rec.confidence) && (
                          <span
                            className={`px-2 py-1 text-xs font-medium rounded border flex items-center space-x-1 ${getConfidenceBadge(rec.confidence).color}`}
                            title={rec.confidence_detail || ''}
                          >
                            {getConfidenceBadge(rec.confidence).icon}
                            <span>{getConfidenceBadge(rec.confidence).label}</span>
                          </span>
                        )}
                        {rec.priority && (
                          <span
                            className={`px-2 py-1 text-xs font-medium rounded border ${getPriorityColor(
                              rec.priority
                            )}`}
                          >
                            {rec.priority.toUpperCase()}
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="text-slate-700 dark:text-slate-300 text-sm mb-3">{rec.description}</p>
                    {rec.servicenow_components && rec.servicenow_components.length > 0 && (
                      <div className="mt-3">
                        <p className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">
                          ServiceNow Components:
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {rec.servicenow_components.map((component, idx) => {
                            const isUnvalidated = rec.unvalidated_components && rec.unvalidated_components.includes(component);
                            return (
                              <span
                                key={idx}
                                className={`px-2 py-1 text-xs rounded border ${
                                  isUnvalidated
                                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                                    : 'bg-primary-50 text-primary-700 border-primary-200'
                                }`}
                                title={isUnvalidated ? 'Not found in ServiceNow ontology — verify this component' : ''}
                              >
                                {component}{isUnvalidated && ' *'}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    )}
                    {rec.validation_notes && rec.validation_notes.length > 0 && (
                      <div className="mt-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
                        <p className="font-medium mb-1">Validation Notes:</p>
                        {rec.validation_notes.map((note, idx) => (
                          <p key={idx} className="ml-2">- {note}</p>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-slate-600 dark:text-slate-400 text-sm">No recommendations available</p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg">
        <button
          onClick={() => toggleSection('metadata')}
          className="w-full flex items-center justify-between p-6 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
        >
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Analysis Metadata</h3>
          {expandedSections.metadata ? (
            <ChevronUp className="h-5 w-5 text-slate-500" />
          ) : (
            <ChevronDown className="h-5 w-5 text-slate-500" />
          )}
        </button>
        {expandedSections.metadata && result.metadata && (
          <div className="px-6 pb-6 border-t border-slate-200 dark:border-slate-700">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
              <div className="bg-slate-50 dark:bg-slate-700/50 p-4 rounded-lg">
                <p className="text-xs text-slate-600 dark:text-slate-400 mb-1">ServiceNow Instance</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">
                  {result.metadata.servicenow_instance}
                </p>
              </div>
              <div className="bg-slate-50 dark:bg-slate-700/50 p-4 rounded-lg">
                <p className="text-xs text-slate-600 dark:text-slate-400 mb-1">Tables Analyzed</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">
                  {result.metadata.tables_analyzed}
                </p>
              </div>
              <div className="bg-slate-50 dark:bg-slate-700/50 p-4 rounded-lg">
                <p className="text-xs text-slate-600 dark:text-slate-400 mb-1">Apps Analyzed</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">
                  {result.metadata.apps_analyzed}
                </p>
              </div>
              <div className="bg-slate-50 dark:bg-slate-700/50 p-4 rounded-lg">
                <p className="text-xs text-slate-600 dark:text-slate-400 mb-1">Documents Used</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">
                  {result.metadata.documents_used}
                </p>
              </div>
            </div>
            <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
              <p className="text-xs text-blue-800 dark:text-blue-300">
                <strong>Query:</strong> {result.metadata.query}
              </p>
              <p className="text-xs text-blue-600 dark:text-blue-400 mt-2">
                Generated at: {new Date(result.metadata.timestamp).toLocaleString()}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ResultsDisplay;
