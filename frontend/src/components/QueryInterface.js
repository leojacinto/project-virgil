import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Search, Globe, FileText, X } from 'lucide-react';
import axios from 'axios';

function QueryInterface({ onAnalysisComplete }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [options, setOptions] = useState({
    include_web_search: true,
    include_pricing: true
  });
  const [progress, setProgress] = useState(null);
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

  const handleExampleClick = (example) => {
    setQuery(example);
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-slate-900 mb-4">
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
            <label className="flex items-center space-x-3 p-4 border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-50 transition-colors">
              <input
                type="checkbox"
                checked={options.include_web_search}
                onChange={(e) => setOptions({ ...options, include_web_search: e.target.checked })}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-slate-300 rounded"
              />
              <div className="flex items-center space-x-2">
                <Globe className="h-4 w-4 text-slate-600" />
                <span className="text-sm font-medium text-slate-700">Web Search</span>
              </div>
            </label>

            <label className="flex items-center space-x-3 p-4 border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-50 transition-colors">
              <input
                type="checkbox"
                checked={options.include_pricing}
                onChange={(e) => setOptions({ ...options, include_pricing: e.target.checked })}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-slate-300 rounded"
              />
              <div className="flex items-center space-x-2">
                <FileText className="h-4 w-4 text-slate-600" />
                <span className="text-sm font-medium text-slate-700">Use Documents</span>
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
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-700">
                  Step {progress.step}/{progress.total} — {progress.label}
                </span>
                <span className="text-xs text-slate-500">
                  {Math.round((progress.step / progress.total) * 100)}%
                </span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-1.5">
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
        <h4 className="text-sm font-medium text-slate-700 mb-3 flex items-center space-x-2">
          <Search className="h-4 w-4" />
          <span>Example Queries</span>
        </h4>
        <div className="grid grid-cols-1 gap-2">
          {exampleQueries.map((example, index) => (
            <button
              key={index}
              onClick={() => handleExampleClick(example)}
              disabled={loading}
              className="text-left px-4 py-3 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-sm text-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default QueryInterface;
