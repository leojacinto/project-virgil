import React, { useState, useEffect } from 'react';
import { Download, ExternalLink, ChevronDown, ChevronUp, CheckCircle, AlertTriangle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import mermaid from 'mermaid';

function ResultsDisplay({ result }) {
  const [expandedSections, setExpandedSections] = useState({
    diagram: true,
    analysis: true,
    recommendations: true,
    metadata: false
  });

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

  const handleDownloadDiagram = () => {
    if (result.diagram_path) {
      window.open(`/api/diagrams/${result.diagram_path}`, '_blank');
    }
  };

  return (
    <div className="space-y-6">
      {result.mermaid_diagram && (
        <div className="bg-white border border-slate-200 rounded-lg">
          <button
            onClick={() => toggleSection('diagram')}
            className="w-full flex items-center justify-between p-6 hover:bg-slate-50 transition-colors"
          >
            <h3 className="text-lg font-semibold text-slate-900">
              Architecture Diagram
            </h3>
            {expandedSections.diagram ? (
              <ChevronUp className="h-5 w-5 text-slate-500" />
            ) : (
              <ChevronDown className="h-5 w-5 text-slate-500" />
            )}
          </button>
          {expandedSections.diagram && (
            <div className="px-6 pb-6 border-t border-slate-200">
              <div className="bg-slate-50 rounded-lg p-6 mt-4 overflow-x-auto">
                <div className="mermaid">
                  {result.mermaid_diagram}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-lg">
        <button
          onClick={() => toggleSection('analysis')}
          className="w-full flex items-center justify-between p-6 hover:bg-slate-50 transition-colors"
        >
          <h3 className="text-lg font-semibold text-slate-900">
            Architecture Analysis
          </h3>
          {expandedSections.analysis ? (
            <ChevronUp className="h-5 w-5 text-slate-500" />
          ) : (
            <ChevronDown className="h-5 w-5 text-slate-500" />
          )}
        </button>
        {expandedSections.analysis && (
          <div className="px-6 pb-6 border-t border-slate-200">
            <div className="prose prose-slate max-w-none mt-4">
              <ReactMarkdown>{result.analysis}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white border border-slate-200 rounded-lg">
        <button
          onClick={() => toggleSection('recommendations')}
          className="w-full flex items-center justify-between p-6 hover:bg-slate-50 transition-colors"
        >
          <h3 className="text-lg font-semibold text-slate-900">
            Recommendations ({result.recommendations?.length || 0})
          </h3>
          {expandedSections.recommendations ? (
            <ChevronUp className="h-5 w-5 text-slate-500" />
          ) : (
            <ChevronDown className="h-5 w-5 text-slate-500" />
          )}
        </button>
        {expandedSections.recommendations && (
          <div className="px-6 pb-6 border-t border-slate-200">
            <div className="space-y-4 mt-4">
              {result.recommendations && result.recommendations.length > 0 ? (
                result.recommendations.map((rec, index) => (
                  <div
                    key={index}
                    className="border border-slate-200 rounded-lg p-4 hover:shadow-sm transition-shadow"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h4 className="font-semibold text-slate-900 flex items-center space-x-2">
                        <CheckCircle className="h-5 w-5 text-green-600" />
                        <span>{rec.title}</span>
                      </h4>
                      {rec.priority && (
                        <span
                          className={`px-2 py-1 text-xs font-medium rounded border ${getPriorityColor(
                            rec.priority
                          )}`}
                          title={
                            rec.priority.toLowerCase() === 'high' 
                              ? 'Critical for core functionality - implement first'
                              : rec.priority.toLowerCase() === 'medium'
                              ? 'Important for complete solution - implement after high priority'
                              : 'Nice-to-have enhancement - implement if time/budget allows'
                          }
                        >
                          {rec.priority.toUpperCase()}
                        </span>
                      )}
                    </div>
                    <p className="text-slate-700 text-sm mb-3">{rec.description}</p>
                    {rec.servicenow_components && rec.servicenow_components.length > 0 && (
                      <div className="mt-3">
                        <p className="text-xs font-medium text-slate-600 mb-2">
                          ServiceNow Components:
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {rec.servicenow_components.map((component, idx) => (
                            <span
                              key={idx}
                              className="px-2 py-1 bg-primary-50 text-primary-700 text-xs rounded border border-primary-200"
                            >
                              {component}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-slate-600 text-sm">No recommendations available</p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="bg-white border border-slate-200 rounded-lg">
        <button
          onClick={() => toggleSection('metadata')}
          className="w-full flex items-center justify-between p-6 hover:bg-slate-50 transition-colors"
        >
          <h3 className="text-lg font-semibold text-slate-900">Analysis Metadata</h3>
          {expandedSections.metadata ? (
            <ChevronUp className="h-5 w-5 text-slate-500" />
          ) : (
            <ChevronDown className="h-5 w-5 text-slate-500" />
          )}
        </button>
        {expandedSections.metadata && result.metadata && (
          <div className="px-6 pb-6 border-t border-slate-200">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
              <div className="bg-slate-50 p-4 rounded-lg">
                <p className="text-xs text-slate-600 mb-1">ServiceNow Instance</p>
                <p className="text-sm font-semibold text-slate-900">
                  {result.metadata.servicenow_instance}
                </p>
              </div>
              <div className="bg-slate-50 p-4 rounded-lg">
                <p className="text-xs text-slate-600 mb-1">Tables Analyzed</p>
                <p className="text-sm font-semibold text-slate-900">
                  {result.metadata.tables_analyzed}
                </p>
              </div>
              <div className="bg-slate-50 p-4 rounded-lg">
                <p className="text-xs text-slate-600 mb-1">Apps Analyzed</p>
                <p className="text-sm font-semibold text-slate-900">
                  {result.metadata.apps_analyzed}
                </p>
              </div>
              <div className="bg-slate-50 p-4 rounded-lg">
                <p className="text-xs text-slate-600 mb-1">Documents Used</p>
                <p className="text-sm font-semibold text-slate-900">
                  {result.metadata.documents_used}
                </p>
              </div>
            </div>
            <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-xs text-blue-800">
                <strong>Query:</strong> {result.metadata.query}
              </p>
              <p className="text-xs text-blue-600 mt-2">
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
