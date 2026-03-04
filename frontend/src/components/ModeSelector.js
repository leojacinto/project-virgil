import React, { useState } from 'react';
import { Brain, ShieldCheck, Calculator, ArrowRight, Wifi, WifiOff, Sparkles, Settings, CheckCircle, Lock, AlertCircle } from 'lucide-react';
import axios from 'axios';

const modes = [
  {
    id: 'virgil',
    name: 'Virgil',
    subtitle: 'Architecture Advisor',
    icon: Brain,
    color: 'indigo',
    description: 'LLM-powered architecture recommendations using ontology, RAG, and optional live instance data.',
    features: ['AI-generated solution designs', 'Mermaid diagram generation', 'Ontology-validated recommendations', 'Document-aware context (RAG)'],
    requiresLLM: true,
    requiresInstance: false,
    instanceNote: 'Instance optional — enhances with live data',
    ready: true,
  },
  {
    id: 'minos',
    name: 'Minos',
    subtitle: 'Architecture & Design Scan',
    icon: ShieldCheck,
    color: 'emerald',
    description: 'Deterministic, zero-LLM architecture and anti-pattern scan of your ServiceNow instance against 45 rules across 6 categories.',
    features: ['IT4IT value stream gap analysis', 'Integration pattern & anti-pattern detection', 'Product adoption maturity assessment', 'As-Is and Recommended architecture diagrams'],
    requiresLLM: false,
    requiresInstance: true,
    instanceNote: 'Requires active ServiceNow connection',
    ready: true,
  },
  {
    id: 'plutus',
    name: 'Plutus',
    subtitle: 'Usage Scanner',
    icon: Calculator,
    color: 'amber',
    description: 'Scan your instance for Workflow Data Fabric utilization — Integration Hub, Zero Copy, Stream Connect, RPA, and more. Use the results as additional inputs in the official WDF calculator.',
    features: ['Auto-detect WDF capability usage from execution logs', 'Annualized usage estimation (actual or extrapolated)', 'ZCC, Stream Connect & AI Data Explorer detection', 'Export to Excel for offline analysis'],
    requiresLLM: false,
    requiresInstance: true,
    instanceNote: 'Requires active ServiceNow connection',
    ready: true,
  },
];

const colorMap = {
  indigo: {
    bg: 'bg-indigo-50 dark:bg-indigo-900/20',
    border: 'border-indigo-200 dark:border-indigo-700',
    hoverBorder: 'hover:border-indigo-400 dark:hover:border-indigo-500',
    iconBg: 'bg-indigo-100 dark:bg-indigo-800',
    iconText: 'text-indigo-600 dark:text-indigo-400',
    button: 'bg-indigo-600 hover:bg-indigo-700 text-white',
    ring: 'ring-indigo-400',
  },
  emerald: {
    bg: 'bg-emerald-50 dark:bg-emerald-900/20',
    border: 'border-emerald-200 dark:border-emerald-700',
    hoverBorder: 'hover:border-emerald-400 dark:hover:border-emerald-500',
    iconBg: 'bg-emerald-100 dark:bg-emerald-800',
    iconText: 'text-emerald-600 dark:text-emerald-400',
    button: 'bg-emerald-600 hover:bg-emerald-700 text-white',
    ring: 'ring-emerald-400',
  },
  amber: {
    bg: 'bg-amber-50 dark:bg-amber-900/20',
    border: 'border-amber-200 dark:border-amber-700',
    hoverBorder: 'hover:border-amber-400 dark:hover:border-amber-500',
    iconBg: 'bg-amber-100 dark:bg-amber-800',
    iconText: 'text-amber-600 dark:text-amber-400',
    button: 'bg-amber-600 hover:bg-amber-700 text-white',
    ring: 'ring-amber-400',
  },
};

/**
 * Props:
 *   onSelectMode(modeId)
 *   onOpenSettings(dialogType: 'llm' | 'instance' | 'both')
 *   llmConfigured: boolean
 *   instanceConnected: boolean
 *   instanceName: string
 */
function ModeSelector({ onSelectMode, onOpenSettings, llmConfigured, instanceConnected, instanceName }) {
  const [hoveredMode, setHoveredMode] = useState(null);
  const [showPwModal, setShowPwModal] = useState(false);
  const [pwInput, setPwInput] = useState('');
  const [pwError, setPwError] = useState('');
  const [pwLoading, setPwLoading] = useState(false);

  const handleCardClick = (mode) => {
    if (!mode.ready) return;
    // Check prerequisites
    const needsLLM = mode.requiresLLM && !llmConfigured;
    const needsInstance = mode.requiresInstance && !instanceConnected;
    if (needsLLM && needsInstance) {
      onOpenSettings('both');
    } else if (needsLLM) {
      onOpenSettings('llm');
    } else if (needsInstance) {
      onOpenSettings('instance');
    } else if (mode.id === 'plutus') {
      setShowPwModal(true);
      setPwInput('');
      setPwError('');
    } else {
      onSelectMode(mode.id);
    }
  };

  const verifyPlutusPw = async () => {
    setPwLoading(true);
    setPwError('');
    try {
      await axios.post('/api/plutus/verify-password', { password: pwInput });
      setShowPwModal(false);
      onSelectMode('plutus');
    } catch (err) {
      const status = err?.response?.status;
      if (status === 401) setPwError('Incorrect password.');
      else if (status === 503) setPwError('Password not configured on server.');
      else setPwError('Verification failed.');
    } finally {
      setPwLoading(false);
    }
  };

  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center px-4">
      {/* Header */}
      <div className="text-center mb-10">
        <div className="flex items-center justify-center space-x-3 mb-4">
          <div className="bg-gradient-to-br from-indigo-500 to-purple-600 p-3 rounded-xl shadow-lg">
            <Sparkles className="h-8 w-8 text-white" />
          </div>
        </div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
          Project Virgil
        </h1>
        <p className="text-slate-500 dark:text-slate-400 max-w-lg mx-auto">
          AI-powered ServiceNow architecture advisory platform.
          Choose a mode to get started.
        </p>

        {/* Status pills */}
        <div className="mt-4 flex items-center justify-center gap-3 flex-wrap">
          <div className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${
            llmConfigured
              ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400'
              : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'
          }`}>
            {llmConfigured
              ? <><CheckCircle className="h-3.5 w-3.5" /><span>LLM configured</span></>
              : <><Brain className="h-3.5 w-3.5" /><span>LLM not configured</span></>
            }
          </div>
          <div className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${
            instanceConnected
              ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400'
              : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'
          }`}>
            {instanceConnected
              ? <><Wifi className="h-3.5 w-3.5" /><span>{instanceName || 'Instance connected'}</span></>
              : <><WifiOff className="h-3.5 w-3.5" /><span>No instance</span></>
            }
          </div>
          <button
            onClick={() => onOpenSettings('both')}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
            title="Configure LLM and Instance"
          >
            <Settings className="h-3.5 w-3.5" />
            <span>Settings</span>
          </button>
        </div>
      </div>

      {/* Mode cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl w-full">
        {modes.map((mode) => {
          const c = colorMap[mode.color];
          const Icon = mode.icon;
          const comingSoon = !mode.ready;
          const needsLLM = mode.requiresLLM && !llmConfigured;
          const needsInstance = mode.requiresInstance && !instanceConnected;
          const missingPrereq = needsLLM || needsInstance;

          return (
            <div
              key={mode.id}
              className={`relative rounded-2xl border-2 transition-all duration-200 cursor-pointer
                ${c.border} ${c.hoverBorder}
                ${hoveredMode === mode.id ? `shadow-lg ${c.bg} ring-2 ${c.ring}` : 'bg-white dark:bg-slate-800 shadow-sm'}
                ${comingSoon ? 'opacity-75' : ''}
              `}
              onMouseEnter={() => setHoveredMode(mode.id)}
              onMouseLeave={() => setHoveredMode(null)}
              onClick={() => handleCardClick(mode)}
            >
              {comingSoon && (
                <div className="absolute top-3 right-3">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-slate-200 dark:bg-slate-600 text-slate-600 dark:text-slate-300">
                    Coming Soon
                  </span>
                </div>
              )}

              <div className="p-6">
                {/* Icon + title */}
                <div className="flex items-start space-x-4 mb-4">
                  <div className={`p-3 rounded-xl ${c.iconBg}`}>
                    <Icon className={`h-7 w-7 ${c.iconText}`} />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-slate-900 dark:text-white">{mode.name}</h2>
                    <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      {mode.subtitle}
                    </p>
                  </div>
                </div>

                {/* Description */}
                <p className="text-sm text-slate-600 dark:text-slate-300 mb-4 leading-relaxed">
                  {mode.description}
                </p>

                {/* Features */}
                <ul className="space-y-1.5 mb-5">
                  {mode.features.map((f, i) => (
                    <li key={i} className="flex items-center space-x-2 text-xs text-slate-600 dark:text-slate-400">
                      <span className={`h-1.5 w-1.5 rounded-full ${c.iconText} flex-shrink-0`} style={{ backgroundColor: 'currentColor' }} />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>

                {/* Prerequisite status */}
                <div className="space-y-1 mb-4">
                  {mode.requiresLLM && (
                    <div className="flex items-center space-x-1.5 text-[10px]">
                      {llmConfigured
                        ? <><CheckCircle className="h-3 w-3 text-green-500" /><span className="text-green-600 dark:text-green-400">LLM configured</span></>
                        : <><Brain className="h-3 w-3 text-amber-500" /><span className="text-amber-600 dark:text-amber-400">LLM required — click to configure</span></>
                      }
                    </div>
                  )}
                  {mode.requiresInstance ? (
                    <div className="flex items-center space-x-1.5 text-[10px]">
                      {instanceConnected
                        ? <><CheckCircle className="h-3 w-3 text-green-500" /><span className="text-green-600 dark:text-green-400">Instance connected</span></>
                        : <><WifiOff className="h-3 w-3 text-amber-500" /><span className="text-amber-600 dark:text-amber-400">Instance required — click to connect</span></>
                      }
                    </div>
                  ) : (
                    <div className="flex items-center space-x-1.5 text-[10px] text-slate-400">
                      <span>{mode.instanceNote}</span>
                    </div>
                  )}
                </div>

                {/* CTA button */}
                {!comingSoon ? (
                  <button
                    className={`w-full py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center space-x-2 transition-all shadow-sm ${
                      missingPrereq
                        ? 'bg-slate-200 dark:bg-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-500'
                        : `${c.button}`
                    }`}
                  >
                    <span>{missingPrereq ? 'Configure & Launch' : `Launch ${mode.name}`}</span>
                    <ArrowRight className="h-4 w-4" />
                  </button>
                ) : (
                  <div className="w-full py-2.5 rounded-lg text-sm font-medium text-center bg-slate-100 dark:bg-slate-700 text-slate-400 dark:text-slate-500">
                    Awaiting pricing data
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer hint */}
      <p className="mt-8 text-xs text-slate-400 dark:text-slate-500">
        You can switch modes at any time using the back button.
      </p>

      {/* Plutus password modal */}
      {showPwModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-700 w-full max-w-sm mx-4 p-6">
            <div className="flex items-center space-x-3 mb-4">
              <div className="p-2 rounded-lg bg-amber-100 dark:bg-amber-900/40">
                <Lock className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">Plutus Access</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">Internal ServiceNow tool — directional sizing, not a commercial quote</p>
              </div>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); verifyPlutusPw(); }}>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Enter password:</label>
              <input
                type="password"
                autoFocus
                value={pwInput}
                onChange={(e) => setPwInput(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-amber-400 focus:border-transparent text-sm"
                placeholder="Password"
              />
              {pwError && (
                <div className="flex items-center space-x-1.5 mt-2 text-xs text-red-600 dark:text-red-400">
                  <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                  <span>{pwError}</span>
                </div>
              )}
              <div className="flex items-center justify-end space-x-2 mt-4">
                <button type="button" onClick={() => setShowPwModal(false)}
                  className="px-4 py-2 text-sm rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={pwLoading || !pwInput}
                  className="px-4 py-2 text-sm font-semibold rounded-lg bg-amber-600 hover:bg-amber-700 text-white disabled:opacity-50 transition-colors">
                  {pwLoading ? 'Verifying...' : 'Continue'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default ModeSelector;
