import React, { useState, useEffect } from 'react';
import { Database, FileText, Search, Loader2, GitBranch, Sun, Moon, ArrowLeft, Brain, ShieldCheck, Calculator } from 'lucide-react';
import { useTheme } from './ThemeContext';
import ModeSelector from './components/ModeSelector';
import SettingsDialog from './components/SettingsDialog';
import DocumentUpload from './components/DocumentUpload';
import QueryInterface from './components/QueryInterface';
import ResultsDisplay from './components/ResultsDisplay';
import InstanceInfo from './components/InstanceInfo';
import DiagramLog from './components/DiagramLog';
import PlutusPricing from './components/PlutusPricing';
import axios from 'axios';

const modeConfig = {
  virgil:  { name: 'Virgil',      subtitle: 'Architecture Advisor', icon: Brain,       color: 'indigo' },
  minos:   { name: 'Minos',       subtitle: 'Instance Assessment',  icon: ShieldCheck, color: 'emerald' },
  plutus:  { name: 'Plutus',      subtitle: 'Credit Estimator',     icon: Calculator,  color: 'amber' },
};

function App() {
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState(null);
  const [activeTab, setActiveTab] = useState('query');
  const [llmConfigured, setLlmConfigured] = useState(false);
  const [instanceConnected, setInstanceConnected] = useState(false);
  const [instanceName, setInstanceName] = useState('');
  const [settingsDialog, setSettingsDialog] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [query, setQuery] = useState('');
  const [queryOptions, setQueryOptions] = useState({
    include_web_search: true,
    include_pricing: true
  });
  const { darkMode, toggleTheme } = useTheme();

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      const healthCheck = await axios.get('/api/health');
      if (healthCheck.data.status === 'healthy') {
        const [llmStatus, connectionStatus] = await Promise.all([
          axios.get('/api/llm/status'),
          axios.get('/api/connection/status')
        ]);
        setLlmConfigured(!!llmStatus.data.configured);
        if (connectionStatus.data.connected) {
          setInstanceConnected(true);
          setInstanceName(connectionStatus.data.instance || '');
        }
      }
    } catch (error) {
      console.error('Backend not ready yet:', error);
      setTimeout(checkStatus, 2000);
      return;
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = (update) => {
    if (update.llmConfigured !== undefined) setLlmConfigured(update.llmConfigured);
    if (update.instanceConnected !== undefined) setInstanceConnected(update.instanceConnected);
    if (update.instanceName !== undefined) setInstanceName(update.instanceName);
  };

  const handleAnalysis = (result) => {
    setAnalysisResult(result);
    setActiveTab('results');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-12 w-12 text-primary-600 animate-spin mx-auto mb-4" />
          <p className="text-slate-600 dark:text-slate-300 font-medium">Waiting for backend server...</p>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-2">Installing dependencies if needed</p>
        </div>
      </div>
    );
  }

  // --- Mode selector landing ---
  if (!mode) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
        <div className="absolute top-4 right-4">
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg bg-white/80 dark:bg-slate-700/80 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors shadow-sm"
            title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
        </div>
        <ModeSelector
          onSelectMode={setMode}
          onOpenSettings={setSettingsDialog}
          llmConfigured={llmConfigured}
          instanceConnected={instanceConnected}
          instanceName={instanceName}
        />
        <SettingsDialog
          show={settingsDialog}
          onClose={() => setSettingsDialog(null)}
          onStatusChange={handleStatusChange}
          llmConfigured={llmConfigured}
          instanceConnected={instanceConnected}
        />
        <footer className="border-t border-slate-200 dark:border-slate-700 bg-white/50 dark:bg-slate-800/50">
          <div className="max-w-7xl mx-auto px-4 py-4">
            <p className="text-xs text-slate-400 dark:text-slate-500 text-center">
              Built by{' '}
              <a href="https://www.linkedin.com/in/leojmfrancia" target="_blank" rel="noopener noreferrer" className="hover:text-primary-600 transition-colors">Leo Francia</a>
              {' & '}
              <a href="https://www.linkedin.com/in/rninne" target="_blank" rel="noopener noreferrer" className="hover:text-primary-600 transition-colors">Robert Ninness</a>
            </p>
          </div>
        </footer>
      </div>
    );
  }

  // --- Active mode workspace ---
  const currentMode = modeConfig[mode];
  const ModeIcon = currentMode?.icon || Database;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <header className="bg-white dark:bg-slate-800 shadow-sm border-b border-slate-200 dark:border-slate-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setMode(null)}
                className="p-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
                title="Back to mode selector"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
              <div className="bg-primary-600 p-2 rounded-lg">
                <ModeIcon className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                  {currentMode.name}
                </h1>
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  {currentMode.subtitle}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {instanceConnected && (
                <div className="flex items-center space-x-2 bg-green-50 dark:bg-green-900/30 px-3 py-2 rounded-lg">
                  <div className="h-2 w-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-sm font-medium text-green-700 dark:text-green-400">
                    {instanceName}
                  </span>
                </div>
              )}
              <button
                onClick={toggleTheme}
                className="p-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
                title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* ========== VIRGIL MODE ========== */}
        {mode === 'virgil' && (
          <div className="space-y-6">
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700">
              <div className="border-b border-slate-200 dark:border-slate-700">
                <nav className="flex space-x-8 px-6" aria-label="Tabs">
                  <button
                    onClick={() => setActiveTab('query')}
                    className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                      activeTab === 'query'
                        ? 'border-primary-500 text-primary-600'
                        : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600'
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
                        : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600'
                    }`}
                  >
                    <div className="flex items-center space-x-2">
                      <FileText className="h-4 w-4" />
                      <span>Documents</span>
                    </div>
                  </button>
                  {analysisResult && (
                    <button
                      onClick={() => setActiveTab('results')}
                      className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                        activeTab === 'results'
                          ? 'border-primary-500 text-primary-600'
                          : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600'
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
                          : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600'
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
                  <QueryInterface
                    onAnalysisComplete={handleAnalysis}
                    query={query}
                    setQuery={setQuery}
                    options={queryOptions}
                    setOptions={setQueryOptions}
                  />
                )}
                {activeTab === 'documents' && <DocumentUpload />}
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

        {/* ========== MINOS MODE ========== */}
        {mode === 'minos' && <InstanceInfo />}

        {/* ========== PLUTUS MODE ========== */}
        {mode === 'plutus' && <PlutusPricing />}
      </main>

      <footer className="mt-12 border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col items-center space-y-3">
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Project Virgil — AI-Powered ServiceNow Architecture Platform
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-500">
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
