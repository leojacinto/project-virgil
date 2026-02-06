import React, { useState } from 'react';
import { ChevronRight, ChevronLeft, CheckCircle, Loader2, Database, Brain, Zap } from 'lucide-react';
import axios from 'axios';

function SetupWizard({ onComplete }) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const [llmConfig, setLlmConfig] = useState({
    provider: 'openai',
    api_key: '',
    model: ''
  });
  
  const [servicenowConfig, setServicenowConfig] = useState({
    instance: '',
    username: '',
    password: '',
    jdbc_path: ''
  });

  const llmProviders = [
    { 
      id: 'openai', 
      name: 'OpenAI', 
      models: ['gpt-4-turbo-preview', 'gpt-4', 'gpt-3.5-turbo'],
      defaultModel: 'gpt-4-turbo-preview'
    },
    { 
      id: 'anthropic', 
      name: 'Anthropic Claude', 
      models: ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229'],
      defaultModel: 'claude-3-5-sonnet-20241022'
    },
    { 
      id: 'google', 
      name: 'Google Gemini', 
      models: ['gemini-pro', 'gemini-1.5-pro'],
      defaultModel: 'gemini-pro'
    },
    { 
      id: 'azure', 
      name: 'Azure OpenAI', 
      models: ['gpt-4', 'gpt-35-turbo'],
      defaultModel: 'gpt-4'
    }
  ];

  const selectedProvider = llmProviders.find(p => p.id === llmConfig.provider);

  const handleLlmSubmit = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.post('/api/llm/configure', {
        provider: llmConfig.provider,
        api_key: llmConfig.api_key,
        model: llmConfig.model || selectedProvider.defaultModel
      });
      
      if (response.data.status === 'configured') {
        setStep(2);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to configure LLM');
    } finally {
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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        <div className="bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden">
          {/* Progress Bar */}
          <div className="bg-slate-50 px-8 py-6 border-b border-slate-200">
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
            
            <div className="w-full bg-slate-200 rounded-full h-2">
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
                  <h2 className="text-2xl font-bold text-slate-900 mb-2">
                    Configure AI Model
                  </h2>
                  <p className="text-slate-600">
                    Choose your LLM provider for architecture analysis
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-3">
                    Select Provider
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {llmProviders.map((provider) => (
                      <button
                        key={provider.id}
                        onClick={() => setLlmConfig({ ...llmConfig, provider: provider.id, model: '' })}
                        className={`p-4 border-2 rounded-lg text-left transition-all ${
                          llmConfig.provider === provider.id
                            ? 'border-primary-500 bg-primary-50'
                            : 'border-slate-200 hover:border-slate-300'
                        }`}
                      >
                        <div className="font-semibold text-slate-900">{provider.name}</div>
                        <div className="text-xs text-slate-600 mt-1">{provider.defaultModel}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label htmlFor="api_key" className="block text-sm font-medium text-slate-700 mb-2">
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

                <div>
                  <label htmlFor="model" className="block text-sm font-medium text-slate-700 mb-2">
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
                  <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
                    {error}
                  </div>
                )}

                <button
                  onClick={handleLlmSubmit}
                  disabled={loading || !llmConfig.api_key}
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
                  <h2 className="text-2xl font-bold text-slate-900 mb-2">
                    Connect to ServiceNow
                  </h2>
                  <p className="text-slate-600">
                    Enter your ServiceNow instance credentials
                  </p>
                </div>

                <div>
                  <label htmlFor="instance" className="block text-sm font-medium text-slate-700 mb-2">
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
                  <p className="mt-1 text-xs text-slate-500">
                    Without .service-now.com (e.g., "dev12345")
                  </p>
                </div>

                <div>
                  <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-2">
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
                  <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-2">
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

                <div>
                  <label htmlFor="jdbc_path" className="block text-sm font-medium text-slate-700 mb-2">
                    JDBC JAR Path (Optional)
                  </label>
                  <input
                    type="text"
                    id="jdbc_path"
                    value={servicenowConfig.jdbc_path}
                    onChange={(e) => setServicenowConfig({ ...servicenowConfig, jdbc_path: e.target.value })}
                    placeholder="./jdbc/servicenow-jdbc.jar"
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    Leave empty to use default path
                  </p>
                </div>

                {error && (
                  <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
                    {error}
                  </div>
                )}

                <div className="flex space-x-3">
                  <button
                    onClick={() => setStep(1)}
                    disabled={loading}
                    className="flex-1 bg-slate-100 text-slate-700 py-3 px-4 rounded-lg font-medium hover:bg-slate-200 transition-colors disabled:opacity-50 flex items-center justify-center space-x-2"
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
                <h2 className="text-2xl font-bold text-slate-900 mb-2">
                  All Set!
                </h2>
                <p className="text-slate-600 mb-6">
                  Your ServiceNow Architecture Generator is ready to use
                </p>
                <div className="flex items-center justify-center space-x-2">
                  <Loader2 className="h-5 w-5 text-primary-600 animate-spin" />
                  <span className="text-sm text-slate-600">Loading application...</span>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 text-center">
          <p className="text-sm text-slate-600">
            Need help? Check the <a href="#" className="text-primary-600 hover:underline">documentation</a>
          </p>
        </div>
      </div>
    </div>
  );
}

export default SetupWizard;
