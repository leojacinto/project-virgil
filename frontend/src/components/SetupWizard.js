import React, { useState, useEffect } from 'react';
import { ChevronRight, ChevronLeft, CheckCircle, Loader2, Database, Brain, Zap, Wifi, Server } from 'lucide-react';
import axios from 'axios';

function SetupWizard({ onComplete }) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const [llmConfig, setLlmConfig] = useState({
    provider: 'openai',
    api_key: '',
    model: '',
    api_url: ''
  });
  
  const [servicenowConfig, setServicenowConfig] = useState({
    instance: '',
    username: '',
    password: '',
    jdbc_path: '',
    connection_mode: 'rest_only'
  });

  useEffect(() => {
    axios.get('/api/env-defaults').then(res => {
      const { llm, servicenow } = res.data;
      if (llm.api_key) {
        setLlmConfig(prev => ({
          ...prev,
          provider: llm.provider || prev.provider,
          api_key: llm.api_key,
          api_url: llm.api_url || prev.api_url,
        }));
      }
      if (servicenow.instance) {
        setServicenowConfig(prev => ({
          ...prev,
          instance: servicenow.instance || prev.instance,
          username: servicenow.username || prev.username,
          password: servicenow.password || prev.password,
        }));
      }
    }).catch(() => {});
  }, []);

  const llmProviders = [
    { 
      id: 'openai', 
      name: 'OpenAI', 
      models: ['gpt-4-turbo-preview', 'gpt-4', 'gpt-3.5-turbo'],
      defaultModel: 'gpt-4-turbo-preview'
    },
    { 
      id: 'claude', 
      name: 'Claude', 
      models: ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
      defaultModel: 'claude-3-5-sonnet-20241022'
    },
    { 
      id: 'google', 
      name: 'Google Gemini', 
      models: ['gemini-2.5-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'],
      defaultModel: 'gemini-2.5-flash'
    },
    { 
      id: 'onellm', 
      name: 'One LLM', 
      models: ['claude-3-7-sonnet-20250219', 'claude-3-5-sonnet-20241022'],
      defaultModel: 'claude-3-7-sonnet-20250219'
    }
  ];

  const selectedProvider = llmProviders.find(p => p.id === llmConfig.provider);

  const handleLlmSubmit = async () => {
    if (loading) return; // Prevent multiple clicks
    
    setLoading(true);
    setError(null);
    
    try {
      const payload = {
        provider: llmConfig.provider,
        api_key: llmConfig.api_key,
        model: llmConfig.model || selectedProvider.defaultModel
      };
      if (llmConfig.api_url) {
        payload.api_url = llmConfig.api_url;
      }
      const response = await axios.post('/api/llm/configure', payload);
      
      if (response.data && response.data.status === 'configured') {
        // Use setTimeout to ensure state update happens
        setTimeout(() => {
          setLoading(false);
          setStep(2);
        }, 100);
      } else {
        setError('Unexpected response from server');
        setLoading(false);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to configure LLM');
      setLoading(false);
    }
  };

  const handleServiceNowSubmit = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.post('/api/connect', servicenowConfig);
      
      if (response.data.status === 'connected') {
        setStep(3);
        setTimeout(() => {
          onComplete({
            llm: llmConfig,
            servicenow: servicenowConfig
          });
        }, 1500);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to connect to ServiceNow');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
          {/* Progress Bar */}
          <div className="bg-slate-50 dark:bg-slate-900 px-8 py-6 border-b border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between mb-4">
              <div className={`flex items-center space-x-2 ${step >= 1 ? 'text-primary-600' : 'text-slate-400'}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${step >= 1 ? 'bg-primary-600 text-white' : 'bg-slate-200'}`}>
                  {step > 1 ? <CheckCircle className="h-5 w-5" /> : '1'}
                </div>
                <span className="font-medium">LLM Setup</span>
              </div>
              
              <ChevronRight className="h-5 w-5 text-slate-400" />
              
              <div className={`flex items-center space-x-2 ${step >= 2 ? 'text-primary-600' : 'text-slate-400'}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${step >= 2 ? 'bg-primary-600 text-white' : 'bg-slate-200'}`}>
                  {step > 2 ? <CheckCircle className="h-5 w-5" /> : '2'}
                </div>
                <span className="font-medium">ServiceNow</span>
              </div>
              
              <ChevronRight className="h-5 w-5 text-slate-400" />
              
              <div className={`flex items-center space-x-2 ${step >= 3 ? 'text-primary-600' : 'text-slate-400'}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${step >= 3 ? 'bg-primary-600 text-white' : 'bg-slate-200'}`}>
                  {step >= 3 ? <CheckCircle className="h-5 w-5" /> : '3'}
                </div>
                <span className="font-medium">Complete</span>
              </div>
            </div>
            
            <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
              <div 
                className="bg-primary-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${(step / 3) * 100}%` }}
              />
            </div>
          </div>

          <div className="p-8">
            {/* Step 1: LLM Configuration */}
            {step === 1 && (
              <div className="space-y-6">
                <div className="text-center mb-6">
                  <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-100 rounded-full mb-4">
                    <Brain className="h-8 w-8 text-primary-600" />
                  </div>
                  <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
                    Configure AI Model
                  </h2>
                  <p className="text-slate-600 dark:text-slate-400">
                    Choose your LLM provider for architecture analysis
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
                    Select Provider
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {llmProviders.map((provider) => (
                      <button
                        key={provider.id}
                        onClick={() => setLlmConfig({ ...llmConfig, provider: provider.id, model: '', api_url: '' })}
                        className={`p-4 border-2 rounded-lg text-left transition-all ${
                          llmConfig.provider === provider.id
                            ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30'
                            : 'border-slate-200 dark:border-slate-600 hover:border-slate-300 dark:hover:border-slate-500'
                        }`}
                      >
                        <div className="font-semibold text-slate-900 dark:text-white">{provider.name}</div>
                        <div className="text-xs text-slate-600 dark:text-slate-400 mt-1">{provider.defaultModel}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label htmlFor="api_key" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    API Key
                  </label>
                  <input
                    type="password"
                    id="api_key"
                    value={llmConfig.api_key}
                    onChange={(e) => setLlmConfig({ ...llmConfig, api_key: e.target.value })}
                    placeholder={`Enter your ${selectedProvider.name} API key`}
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                  />
                </div>

                {(llmConfig.provider === 'claude' || llmConfig.provider === 'onellm') && (
                  <div>
                    <label htmlFor="api_url" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      API URL {llmConfig.provider === 'onellm' 
                        ? <span className="text-red-500 font-normal">(Required)</span>
                        : <span className="text-slate-400 font-normal">(Optional)</span>}
                    </label>
                    <input
                      type="text"
                      id="api_url"
                      value={llmConfig.api_url}
                      onChange={(e) => setLlmConfig({ ...llmConfig, api_url: e.target.value })}
                      placeholder={llmConfig.provider === 'onellm' 
                        ? 'https://apicid-dev.servicenow.com/v4/onellm/models/anthropic'
                        : 'https://api.anthropic.com (default)'}
                      className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                    />
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      {llmConfig.provider === 'onellm'
                        ? 'Your OneLLM gateway endpoint'
                        : 'Only set this if your organization uses a dedicated Claude endpoint'}
                    </p>
                  </div>
                )}

                <div>
                  <label htmlFor="model" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Model (Optional)
                  </label>
                  <select
                    id="model"
                    value={llmConfig.model}
                    onChange={(e) => setLlmConfig({ ...llmConfig, model: e.target.value })}
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                  >
                    <option value="">Default ({selectedProvider.defaultModel})</option>
                    {selectedProvider.models.map((model) => (
                      <option key={model} value={model}>{model}</option>
                    ))}
                  </select>
                </div>

                {error && (
                  <div className="p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-800 dark:text-red-300">
                    {error}
                  </div>
                )}

                <button
                  onClick={handleLlmSubmit}
                  disabled={loading || !llmConfig.api_key || (llmConfig.provider === 'onellm' && !llmConfig.api_url)}
                  className="w-full bg-primary-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      <span>Configuring...</span>
                    </>
                  ) : (
                    <>
                      <span>Continue</span>
                      <ChevronRight className="h-5 w-5" />
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Step 2: ServiceNow Configuration */}
            {step === 2 && (
              <div className="space-y-6">
                <div className="text-center mb-6">
                  <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
                    <Database className="h-8 w-8 text-blue-600" />
                  </div>
                  <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
                    Connect to ServiceNow
                  </h2>
                  <p className="text-slate-600 dark:text-slate-400">
                    Choose your connection method and enter credentials
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
                    Connection Mode
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setServicenowConfig({ ...servicenowConfig, connection_mode: 'rest_only' })}
                      className={`p-4 border-2 rounded-lg text-left transition-all ${
                        servicenowConfig.connection_mode === 'rest_only'
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                          : 'border-slate-200 dark:border-slate-600 hover:border-slate-300 dark:hover:border-slate-500'
                      }`}
                    >
                      <div className="flex items-center space-x-2 mb-1">
                        <Wifi className="h-4 w-4 text-blue-600" />
                        <span className="font-semibold text-slate-900 dark:text-white">REST API Only</span>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400">No JDBC driver or Java required. Works with any ServiceNow instance.</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => setServicenowConfig({ ...servicenowConfig, connection_mode: 'rest_and_jdbc' })}
                      className={`p-4 border-2 rounded-lg text-left transition-all ${
                        servicenowConfig.connection_mode === 'rest_and_jdbc'
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                          : 'border-slate-200 dark:border-slate-600 hover:border-slate-300 dark:hover:border-slate-500'
                      }`}
                    >
                      <div className="flex items-center space-x-2 mb-1">
                        <Server className="h-4 w-4 text-blue-600" />
                        <span className="font-semibold text-slate-900 dark:text-white">REST API + JDBC</span>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400">Full access with RaptorDB. Requires JDBC driver and Java.</p>
                    </button>
                  </div>
                </div>

                <div>
                  <label htmlFor="instance" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Instance Name
                  </label>
                  <input
                    type="text"
                    id="instance"
                    value={servicenowConfig.instance}
                    onChange={(e) => setServicenowConfig({ ...servicenowConfig, instance: e.target.value })}
                    placeholder="your-instance"
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                  />
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    Without .service-now.com (e.g., "dev12345")
                  </p>
                </div>

                <div>
                  <label htmlFor="username" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Username
                  </label>
                  <input
                    type="text"
                    id="username"
                    value={servicenowConfig.username}
                    onChange={(e) => setServicenowConfig({ ...servicenowConfig, username: e.target.value })}
                    placeholder="admin"
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                  />
                </div>

                <div>
                  <label htmlFor="password" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Password
                  </label>
                  <input
                    type="password"
                    id="password"
                    value={servicenowConfig.password}
                    onChange={(e) => setServicenowConfig({ ...servicenowConfig, password: e.target.value })}
                    placeholder="••••••••"
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                  />
                </div>

                {servicenowConfig.connection_mode === 'rest_and_jdbc' && (
                  <div>
                    <label htmlFor="jdbc_path" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      JDBC JAR Path (Optional)
                    </label>
                    <input
                      type="text"
                      id="jdbc_path"
                      value={servicenowConfig.jdbc_path}
                      onChange={(e) => setServicenowConfig({ ...servicenowConfig, jdbc_path: e.target.value })}
                      placeholder="Leave empty to use built-in driver"
                      className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                    />
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      Leave empty to use default path
                    </p>
                  </div>
                )}

                {error && (
                  <div className="p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-800 dark:text-red-300">
                    {error}
                  </div>
                )}

                <div className="flex space-x-3">
                  <button
                    onClick={() => setStep(1)}
                    disabled={loading}
                    className="flex-1 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 py-3 px-4 rounded-lg font-medium hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors disabled:opacity-50 flex items-center justify-center space-x-2"
                  >
                    <ChevronLeft className="h-5 w-5" />
                    <span>Back</span>
                  </button>
                  
                  <button
                    onClick={handleServiceNowSubmit}
                    disabled={loading || !servicenowConfig.instance || !servicenowConfig.username || !servicenowConfig.password}
                    className="flex-1 bg-primary-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="h-5 w-5 animate-spin" />
                        <span>Connecting...</span>
                      </>
                    ) : (
                      <>
                        <span>Connect</span>
                        <ChevronRight className="h-5 w-5" />
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Step 3: Complete */}
            {step === 3 && (
              <div className="text-center py-8">
                <div className="inline-flex items-center justify-center w-20 h-20 bg-green-100 rounded-full mb-6">
                  <Zap className="h-10 w-10 text-green-600" />
                </div>
                <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
                  All Set!
                </h2>
                <p className="text-slate-600 dark:text-slate-400 mb-6">
                  Your ServiceNow Architecture Generator is ready to use
                </p>
                <div className="flex items-center justify-center space-x-2">
                  <Loader2 className="h-5 w-5 text-primary-600 animate-spin" />
                  <span className="text-sm text-slate-600 dark:text-slate-400">Loading application...</span>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 text-center">
          <p className="text-sm text-slate-600 dark:text-slate-400">
            Need help? Check the <a href="#" className="text-primary-600 hover:underline">documentation</a>
          </p>
        </div>
      </div>
    </div>
  );
}

export default SetupWizard;
