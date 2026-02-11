import React, { useState, useEffect } from 'react';
import { Database, FileText, Search, Settings, Loader2, GitBranch } from 'lucide-react';
import SetupWizard from './components/SetupWizard';
import DocumentUpload from './components/DocumentUpload';
import QueryInterface from './components/QueryInterface';
import ResultsDisplay from './components/ResultsDisplay';
import InstanceInfo from './components/InstanceInfo';
import DiagramLog from './components/DiagramLog';
import axios from 'axios';

function App() {
  const [setupComplete, setSetupComplete] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('query');
  const [connectionInfo, setConnectionInfo] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      // First check if backend is healthy
      const healthCheck = await axios.get('/api/health');
      
      if (healthCheck.data.status === 'healthy') {
        const [llmStatus, connectionStatus] = await Promise.all([
          axios.get('/api/llm/status'),
          axios.get('/api/connection/status')
        ]);
        
        const isSetup = llmStatus.data.configured && connectionStatus.data.connected;
        setSetupComplete(isSetup);
        
        if (connectionStatus.data.connected) {
          setConnectionInfo({ instance: connectionStatus.data.instance });
        }
      }
    } catch (error) {
      console.error('Backend not ready yet:', error);
      // Retry after a delay if backend isn't ready
      setTimeout(checkStatus, 2000);
      return;
    } finally {
      setLoading(false);
    }
  };

  const handleSetupComplete = (config) => {
    setSetupComplete(true);
    setConnectionInfo({ instance: config.servicenow.instance });
  };

  const handleAnalysis = (result) => {
    setAnalysisResult(result);
    setActiveTab('results');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-12 w-12 text-primary-600 animate-spin mx-auto mb-4" />
          <p className="text-slate-600 font-medium">Waiting for backend server...</p>
          <p className="text-slate-500 text-sm mt-2">Installing dependencies if needed</p>
        </div>
      </div>
    );
  }

  if (!setupComplete) {
    return <SetupWizard onComplete={handleSetupComplete} />;
  }

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
              {connectionInfo && (
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
        {setupComplete && (
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
                  {analysisResult?.diagram_pipeline && (
                    <button
                      onClick={() => setActiveTab('diagram-log')}
                      className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                        activeTab === 'diagram-log'
                          ? 'border-primary-500 text-primary-600'
                          : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center space-x-2">
                        <GitBranch className="h-4 w-4" />
                        <span>Diagram Pipeline</span>
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
                {activeTab === 'diagram-log' && analysisResult?.diagram_pipeline && (
                  <DiagramLog pipeline={analysisResult.diagram_pipeline} />
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="mt-12 border-t border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col items-center space-y-3">
            <p className="text-sm font-medium text-slate-700">
              Project Virgil — AI-Powered ServiceNow Architecture Generator
            </p>
            {/* Knowledge Sources — uncomment when Ian Leu and Jochen Geist approve
            <div className="flex flex-wrap justify-center gap-x-6 gap-y-1 text-xs text-slate-500">
              <span>Knowledge Sources:</span>
              <a href="https://www.linkedin.com/in/ian-leu" target="_blank" rel="noopener noreferrer" className="hover:text-primary-600 transition-colors">
                IT4IT v3 Blueprint — Ian Leu
              </a>
              <a href="https://www.servicenow.com/community/architect-blog/integration-design-how-to-choose-the-best-pattern-to-integrate/ba-p/2874114" target="_blank" rel="noopener noreferrer" className="hover:text-primary-600 transition-colors">
                Integration Pattern Decision Tree — Jochen Geist
              </a>
            </div>
            */}
            <p className="text-xs text-slate-400">
              Built by{' '}
              <a href="https://www.linkedin.com/in/leojmfrancia" target="_blank" rel="noopener noreferrer" className="hover:text-primary-600 transition-colors">Leo Francia</a>
              {' & '}
              <a href="https://www.linkedin.com/in/rninne" target="_blank" rel="noopener noreferrer" className="hover:text-primary-600 transition-colors">Robert Ninness</a>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
