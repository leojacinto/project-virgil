import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Search, Globe, FileText, X, AlertTriangle, ShieldAlert } from 'lucide-react';
import axios from 'axios';

function QueryInterface({ onAnalysisComplete, query, setQuery, options, setOptions }) {
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(null);
  const [showDocWarning, setShowDocWarning] = useState(false);
  const [attachedDocs, setAttachedDocs] = useState([]);
  const abortControllerRef = useRef(null);
  const taskIdRef = useRef(null);

  useEffect(() => {
    if (!loading) { setProgress(null); return; }
    const poll = setInterval(async () => {
      try {
        const res = await axios.get('/api/analyze/progress');
        if (res.data.active) setProgress(res.data);
        else setProgress(null);
      } catch (_) {}
    }, 1500);
    return () => clearInterval(poll);
  }, [loading]);

  const exampleQueries = [
    "How do I address a customer service workflow requirement?",
    "Architect a master data management solution that writes to SAP",
    "Design an ITSM solution with incident and change management",
    "Create an integration architecture for Salesforce and ServiceNow",
    "Build a knowledge management system with AI-powered search"
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    // Check for attached documents before proceeding
    if (options.include_pricing) {
      try {
        const [snRes, custRes] = await Promise.all([
          axios.get('/api/documents?store=servicenow_assets'),
          axios.get('/api/documents?store=customer_documents')
        ]);
        const allDocs = [
          ...(snRes.data?.documents || []).map(d => ({ ...d, store: 'ServiceNow Assets' })),
          ...(custRes.data?.documents || []).map(d => ({ ...d, store: 'Customer Documents' }))
        ];
        if (allDocs.length > 0) {
          setAttachedDocs(allDocs);
          setShowDocWarning(true);
          return;
        }
      } catch (_) {
        // Could not verify documents — warn the user rather than silently proceeding
        setAttachedDocs([]);
        setShowDocWarning(true);
        return;
      }
    }

    runAnalysis();
  };

  const runAnalysis = async () => {
    // Create new AbortController for this request
    abortControllerRef.current = new AbortController();
    
    setLoading(true);
    try {
      const response = await axios.post('/api/analyze', {
        query: query.trim(),
        include_web_search: options.include_web_search,
        include_pricing: options.include_pricing
      }, {
        signal: abortControllerRef.current.signal
      });

      // Store task_id if available
      if (response.data.metadata?.task_id) {
        taskIdRef.current = response.data.metadata.task_id;
      }

      onAnalysisComplete(response.data);
    } catch (error) {
      if (axios.isCancel(error)) {
        console.log('Analysis cancelled by user');
        alert('Analysis cancelled');
      } else {
        console.error('Analysis error:', error);
        alert(error.response?.data?.detail || 'Analysis failed. Please try again.');
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleCancel = async () => {
    // Cancel the HTTP request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    // Cancel the backend task if we have a task_id
    if (taskIdRef.current) {
      try {
        await axios.post(`/api/cancel/${taskIdRef.current}`);
      } catch (error) {
        console.error('Error cancelling backend task:', error);
      }
      taskIdRef.current = null;
    }
    
    setLoading(false);
  };

  const confirmAndRun = () => {
    setShowDocWarning(false);
    setAttachedDocs([]);
    runAnalysis();
  };

  const handleExampleClick = (example) => {
    setQuery(example);
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
          Describe Your Architecture Requirements
        </h3>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="E.g., 'How do I address a customer service workflow requirement?' or 'Architect a master data management solution that writes to SAP for me.'"
              rows={6}
              className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all resize-none"
              disabled={loading}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="flex items-center space-x-3 p-4 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
              <input
                type="checkbox"
                checked={options.include_web_search}
                onChange={(e) => setOptions({ ...options, include_web_search: e.target.checked })}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-slate-300 rounded"
              />
              <div className="flex items-center space-x-2">
                <Globe className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Web Search</span>
              </div>
            </label>

            <label className="flex items-center space-x-3 p-4 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
              <input
                type="checkbox"
                checked={options.include_pricing}
                onChange={(e) => setOptions({ ...options, include_pricing: e.target.checked })}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-slate-300 rounded"
              />
              <div className="flex items-center space-x-2">
                <FileText className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Use Documents</span>
              </div>
            </label>
          </div>

          <div className="flex space-x-3">
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="flex-1 bg-primary-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
            >
              {loading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <span>Analyzing Architecture...</span>
                </>
              ) : (
                <>
                  <Send className="h-5 w-5" />
                  <span>Generate Architecture</span>
                </>
              )}
            </button>
            
            {loading && (
              <button
                type="button"
                onClick={handleCancel}
                className="px-6 bg-red-600 text-white py-3 rounded-lg font-medium hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors flex items-center justify-center space-x-2"
              >
                <X className="h-5 w-5" />
                <span>Cancel</span>
              </button>
            )}
          </div>

          {loading && progress && (
            <div className="bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-700 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Step {progress.step}/{progress.total} — {progress.label}
                </span>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {Math.round((progress.step / progress.total) * 100)}%
                </span>
              </div>
              <div className="w-full bg-slate-200 dark:bg-slate-600 rounded-full h-1.5">
                <div
                  className="bg-primary-600 h-1.5 rounded-full transition-all duration-500"
                  style={{ width: `${(progress.step / progress.total) * 100}%` }}
                />
              </div>
            </div>
          )}
        </form>
      </div>

      <div>
        <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3 flex items-center space-x-2">
          <Search className="h-4 w-4" />
          <span>Example Queries</span>
        </h4>
        <div className="grid grid-cols-1 gap-2">
          {exampleQueries.map((example, index) => (
            <button
              key={index}
              onClick={() => handleExampleClick(example)}
              disabled={loading}
              className="text-left px-4 py-3 bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-700 dark:text-slate-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {example}
            </button>
          ))}
        </div>
      </div>
      {/* Document warning modal */}
      {showDocWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-700 max-w-lg w-full mx-4 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-amber-50 dark:bg-amber-900/20">
              <div className="flex items-center space-x-3">
                <ShieldAlert className="h-5 w-5 text-amber-600" />
                <h3 className="font-semibold text-slate-900 dark:text-white">Documents Will Be Sent to LLM</h3>
              </div>
            </div>
            <div className="px-6 py-4 space-y-3">
              {attachedDocs.length > 0 ? (
                <>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    The following <strong>{attachedDocs.length}</strong> document{attachedDocs.length !== 1 ? 's' : ''} will be included as context in this analysis request:
                  </p>
                  <div className="max-h-48 overflow-y-auto space-y-1">
                    {attachedDocs.map((doc, i) => (
                      <div key={i} className="flex items-center justify-between px-3 py-2 bg-slate-50 dark:bg-slate-700/50 rounded border border-slate-200 dark:border-slate-700">
                        <div className="flex items-center space-x-2 min-w-0">
                          <FileText className="h-3.5 w-3.5 text-slate-400 flex-shrink-0" />
                          <span className="text-sm text-slate-700 dark:text-slate-300 truncate">{doc.filename}</span>
                        </div>
                        <span className="text-[10px] text-slate-500 dark:text-slate-400 flex-shrink-0 ml-2">{doc.store}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-700 dark:text-slate-300">
                  Could not retrieve the document list, but <strong>"Use Documents"</strong> is enabled. Previously uploaded documents may still be sent as context to the LLM.
                </p>
              )}
              <div className="flex items-start space-x-2 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-800 dark:text-amber-300">
                  Verify that you are connected to the intended LLM provider before proceeding, especially if these documents contain sensitive information.
                </p>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-700 flex space-x-3">
              <button
                onClick={() => { setShowDocWarning(false); setAttachedDocs([]); }}
                className="flex-1 px-4 py-2.5 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg font-medium hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmAndRun}
                className="flex-1 px-4 py-2.5 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors flex items-center justify-center space-x-2"
              >
                <Send className="h-4 w-4" />
                <span>Proceed with Analysis</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default QueryInterface;
