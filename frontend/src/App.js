import React, { useState, useEffect } from 'react';
import { Database, FileText, Search, Settings, Loader2 } from 'lucide-react';
import ConnectionPanel from './components/ConnectionPanel';
import DocumentUpload from './components/DocumentUpload';
import QueryInterface from './components/QueryInterface';
import ResultsDisplay from './components/ResultsDisplay';
import InstanceInfo from './components/InstanceInfo';
import axios from 'axios';

function App() {
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('query');
  const [connectionInfo, setConnectionInfo] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);

  useEffect(() => {
    checkConnectionStatus();
  }, []);

  const checkConnectionStatus = async () => {
    try {
      const response = await axios.get('/api/connection/status');
      setConnected(response.data.connected);
      if (response.data.connected) {
        setConnectionInfo({ instance: response.data.instance });
      }
    } catch (error) {
      console.error('Error checking connection:', error);
    }
  };

  const handleConnect = async (config) => {
    setLoading(true);
    try {
      const response = await axios.post('/api/connect', config);
      setConnected(true);
      setConnectionInfo({ instance: config.instance });
      return { success: true, message: response.data.message };
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Connection failed' 
      };
    } finally {
      setLoading(false);
    }
  };

  const handleAnalysis = (result) => {
    setAnalysisResult(result);
    setActiveTab('results');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <header className="bg-white shadow-sm border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="bg-primary-600 p-2 rounded-lg">
                <Database className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900">
                  ServiceNow Architecture Generator
                </h1>
                <p className="text-sm text-slate-600">
                  AI-Powered Solution Design & Diagram Generation
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {connected && connectionInfo && (
                <div className="flex items-center space-x-2 bg-green-50 px-3 py-2 rounded-lg">
                  <div className="h-2 w-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-sm font-medium text-green-700">
                    Connected to {connectionInfo.instance}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {!connected ? (
          <div className="max-w-2xl mx-auto">
            <ConnectionPanel onConnect={handleConnect} loading={loading} />
          </div>
        ) : (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow-sm border border-slate-200">
              <div className="border-b border-slate-200">
                <nav className="flex space-x-8 px-6" aria-label="Tabs">
                  <button
                    onClick={() => setActiveTab('query')}
                    className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                      activeTab === 'query'
                        ? 'border-primary-500 text-primary-600'
                        : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center space-x-2">
                      <Search className="h-4 w-4" />
                      <span>Architecture Query</span>
                    </div>
                  </button>
                  <button
                    onClick={() => setActiveTab('documents')}
                    className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                      activeTab === 'documents'
                        ? 'border-primary-500 text-primary-600'
                        : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center space-x-2">
                      <FileText className="h-4 w-4" />
                      <span>Documents</span>
                    </div>
                  </button>
                  <button
                    onClick={() => setActiveTab('instance')}
                    className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                      activeTab === 'instance'
                        ? 'border-primary-500 text-primary-600'
                        : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center space-x-2">
                      <Settings className="h-4 w-4" />
                      <span>Instance Info</span>
                    </div>
                  </button>
                  {analysisResult && (
                    <button
                      onClick={() => setActiveTab('results')}
                      className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                        activeTab === 'results'
                          ? 'border-primary-500 text-primary-600'
                          : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center space-x-2">
                        <Database className="h-4 w-4" />
                        <span>Results</span>
                      </div>
                    </button>
                  )}
                </nav>
              </div>

              <div className="p-6">
                {activeTab === 'query' && (
                  <QueryInterface onAnalysisComplete={handleAnalysis} />
                )}
                {activeTab === 'documents' && <DocumentUpload />}
                {activeTab === 'instance' && <InstanceInfo />}
                {activeTab === 'results' && analysisResult && (
                  <ResultsDisplay result={analysisResult} />
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="mt-12 border-t border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-sm text-slate-600">
            ServiceNow Architecture Generator - Powered by AI
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
