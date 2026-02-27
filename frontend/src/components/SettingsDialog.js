import React, { useState, useEffect } from 'react';
import { X, Loader2, Brain, Database, CheckCircle, Wifi, Server } from 'lucide-react';
import axios from 'axios';

const llmProviders = [
  { id: 'openai', name: 'OpenAI', models: ['gpt-4-turbo-preview', 'gpt-4', 'gpt-3.5-turbo'], defaultModel: 'gpt-4-turbo-preview' },
  { id: 'claude', name: 'Claude', models: ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'], defaultModel: 'claude-3-5-sonnet-20241022' },
  { id: 'google', name: 'Google Gemini', models: ['gemini-2.5-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'], defaultModel: 'gemini-2.5-flash' },
  { id: 'onellm', name: 'One LLM', models: ['claude-3-7-sonnet-20250219', 'claude-3-5-sonnet-20241022'], defaultModel: 'claude-3-7-sonnet-20250219' },
];

/**
 * SettingsDialog — focused setup for LLM and/or Instance connection.
 * Props:
 *   show: 'llm' | 'instance' | 'both' | null  (null = closed)
 *   onClose: () => void
 *   onStatusChange: ({ llmConfigured, instanceConnected, instanceName }) => void
 *   llmConfigured: boolean
 *   instanceConnected: boolean
 */
function SettingsDialog({ show, onClose, onStatusChange, llmConfigured, instanceConnected }) {
  const [tab, setTab] = useState('llm');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [llmConfig, setLlmConfig] = useState({
    provider: 'openai', api_key: '', model: '', api_url: ''
  });
  const [snConfig, setSnConfig] = useState({
    instance: '', username: '', password: '', jdbc_path: '', connection_mode: 'rest_only'
  });

  useEffect(() => {
    if (!show) return;
    setError(null);
    setSuccess(null);
    if (show === 'llm') setTab('llm');
    else if (show === 'instance') setTab('instance');
    else setTab('llm');

    axios.get('/api/env-defaults').then(res => {
      const { llm, servicenow } = res.data;
      if (llm?.api_key) {
        setLlmConfig(prev => ({
          ...prev,
          provider: llm.provider || prev.provider,
          api_key: llm.api_key,
          api_url: llm.api_url || prev.api_url,
        }));
      }
      if (servicenow?.instance) {
        setSnConfig(prev => ({
          ...prev,
          instance: servicenow.instance || prev.instance,
          username: servicenow.username || prev.username,
          password: servicenow.password || prev.password,
        }));
      }
    }).catch(() => {});
  }, [show]);

  if (!show) return null;

  const selectedProvider = llmProviders.find(p => p.id === llmConfig.provider);
  const showTabs = show === 'both';

  const handleLlmSubmit = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const payload = {
        provider: llmConfig.provider,
        api_key: llmConfig.api_key,
        model: llmConfig.model || selectedProvider.defaultModel,
      };
      if (llmConfig.api_url) payload.api_url = llmConfig.api_url;
      const res = await axios.post('/api/llm/configure', payload);
      if (res.data?.status === 'configured') {
        setSuccess('LLM configured successfully');
        onStatusChange({ llmConfigured: true });
        if (!showTabs) setTimeout(onClose, 800);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to configure LLM');
    } finally {
      setLoading(false);
    }
  };

  const handleSnSubmit = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await axios.post('/api/connect', snConfig);
      if (res.data?.status === 'connected') {
        setSuccess('Connected to ServiceNow');
        onStatusChange({ instanceConnected: true, instanceName: snConfig.instance });
        if (!showTabs) setTimeout(onClose, 800);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to connect to ServiceNow');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700 w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900">
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">
            {show === 'llm' ? 'Configure AI Model' : show === 'instance' ? 'Connect ServiceNow' : 'Settings'}
          </h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400 transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tabs (only in 'both' mode) */}
        {showTabs && (
          <div className="flex border-b border-slate-200 dark:border-slate-700">
            <button
              onClick={() => { setTab('llm'); setError(null); setSuccess(null); }}
              className={`flex-1 py-3 text-sm font-medium flex items-center justify-center space-x-2 transition-colors ${
                tab === 'llm'
                  ? 'border-b-2 border-indigo-500 text-indigo-600'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <Brain className="h-4 w-4" />
              <span>LLM</span>
              {llmConfigured && <CheckCircle className="h-3.5 w-3.5 text-green-500" />}
            </button>
            <button
              onClick={() => { setTab('instance'); setError(null); setSuccess(null); }}
              className={`flex-1 py-3 text-sm font-medium flex items-center justify-center space-x-2 transition-colors ${
                tab === 'instance'
                  ? 'border-b-2 border-emerald-500 text-emerald-600'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <Database className="h-4 w-4" />
              <span>Instance</span>
              {instanceConnected && <CheckCircle className="h-3.5 w-3.5 text-green-500" />}
            </button>
          </div>
        )}

        <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
          {/* ===== LLM TAB ===== */}
          {(tab === 'llm' && (show === 'llm' || show === 'both')) && (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Provider</label>
                <div className="grid grid-cols-2 gap-2">
                  {llmProviders.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => setLlmConfig({ ...llmConfig, provider: p.id, model: '', api_url: '' })}
                      className={`p-3 border-2 rounded-lg text-left transition-all text-sm ${
                        llmConfig.provider === p.id
                          ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30'
                          : 'border-slate-200 dark:border-slate-600 hover:border-slate-300'
                      }`}
                    >
                      <div className="font-semibold text-slate-900 dark:text-white">{p.name}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">{p.defaultModel}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">API Key</label>
                <input
                  type="password"
                  value={llmConfig.api_key}
                  onChange={(e) => setLlmConfig({ ...llmConfig, api_key: e.target.value })}
                  placeholder={`Enter your ${selectedProvider?.name || ''} API key`}
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none text-sm bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                />
              </div>

              {(llmConfig.provider === 'claude' || llmConfig.provider === 'onellm') && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                    API URL {llmConfig.provider === 'onellm' ? <span className="text-red-500">(Required)</span> : <span className="text-slate-400">(Optional)</span>}
                  </label>
                  <input
                    type="text"
                    value={llmConfig.api_url}
                    onChange={(e) => setLlmConfig({ ...llmConfig, api_url: e.target.value })}
                    placeholder={llmConfig.provider === 'onellm' ? 'https://apicid-dev.servicenow.com/v4/onellm/models/anthropic' : 'https://api.anthropic.com (default)'}
                    className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none text-sm bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                  />
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Model</label>
                <select
                  value={llmConfig.model}
                  onChange={(e) => setLlmConfig({ ...llmConfig, model: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none text-sm bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                >
                  <option value="">Default ({selectedProvider?.defaultModel})</option>
                  {selectedProvider?.models.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>

              <button
                onClick={handleLlmSubmit}
                disabled={loading || !llmConfig.api_key || (llmConfig.provider === 'onellm' && !llmConfig.api_url)}
                className="w-full bg-indigo-600 text-white py-2.5 rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 text-sm"
              >
                {loading ? <><Loader2 className="h-4 w-4 animate-spin" /><span>Configuring...</span></> : <span>Configure LLM</span>}
              </button>
            </>
          )}

          {/* ===== INSTANCE TAB ===== */}
          {(tab === 'instance' && (show === 'instance' || show === 'both')) && (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Connection Mode</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setSnConfig({ ...snConfig, connection_mode: 'rest_only' })}
                    className={`p-3 border-2 rounded-lg text-left transition-all ${
                      snConfig.connection_mode === 'rest_only'
                        ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/30'
                        : 'border-slate-200 dark:border-slate-600 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center space-x-1.5 mb-0.5">
                      <Wifi className="h-3.5 w-3.5 text-emerald-600" />
                      <span className="font-semibold text-sm text-slate-900 dark:text-white">REST Only</span>
                    </div>
                    <p className="text-[10px] text-slate-500">No JDBC / Java required</p>
                  </button>
                  <button
                    onClick={() => setSnConfig({ ...snConfig, connection_mode: 'rest_and_jdbc' })}
                    className={`p-3 border-2 rounded-lg text-left transition-all ${
                      snConfig.connection_mode === 'rest_and_jdbc'
                        ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/30'
                        : 'border-slate-200 dark:border-slate-600 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center space-x-1.5 mb-0.5">
                      <Server className="h-3.5 w-3.5 text-emerald-600" />
                      <span className="font-semibold text-sm text-slate-900 dark:text-white">REST + JDBC</span>
                    </div>
                    <p className="text-[10px] text-slate-500">Full access with RaptorDB</p>
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Instance Name</label>
                <input
                  type="text"
                  value={snConfig.instance}
                  onChange={(e) => setSnConfig({ ...snConfig, instance: e.target.value })}
                  placeholder="your-instance"
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none text-sm bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                />
                <p className="mt-0.5 text-[10px] text-slate-400">Without .service-now.com (e.g. "dev12345")</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Username</label>
                <input
                  type="text"
                  value={snConfig.username}
                  onChange={(e) => setSnConfig({ ...snConfig, username: e.target.value })}
                  placeholder="admin"
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none text-sm bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Password</label>
                <input
                  type="password"
                  value={snConfig.password}
                  onChange={(e) => setSnConfig({ ...snConfig, password: e.target.value })}
                  placeholder="••••••••"
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none text-sm bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                />
              </div>

              {snConfig.connection_mode === 'rest_and_jdbc' && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">JDBC JAR Path</label>
                  <input
                    type="text"
                    value={snConfig.jdbc_path}
                    onChange={(e) => setSnConfig({ ...snConfig, jdbc_path: e.target.value })}
                    placeholder="Leave empty for default"
                    className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none text-sm bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                  />
                </div>
              )}

              <button
                onClick={handleSnSubmit}
                disabled={loading || !snConfig.instance || !snConfig.username || !snConfig.password}
                className="w-full bg-emerald-600 text-white py-2.5 rounded-lg font-medium hover:bg-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 text-sm"
              >
                {loading ? <><Loader2 className="h-4 w-4 animate-spin" /><span>Connecting...</span></> : <span>Connect Instance</span>}
              </button>
            </>
          )}

          {/* Status messages */}
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
              {error}
            </div>
          )}
          {success && (
            <div className="p-3 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-300 flex items-center space-x-2">
              <CheckCircle className="h-4 w-4" />
              <span>{success}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default SettingsDialog;
