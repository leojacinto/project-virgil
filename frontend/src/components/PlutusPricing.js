import React, { useState, useCallback } from 'react';
import {
  Calculator, Loader2, RefreshCw, CheckCircle2,
  Zap, Database, DollarSign, Download,
  Edit3, Save, Info, Package, Layers,
  BookOpen, EyeOff, Search, X, Trash2, RotateCcw
} from 'lucide-react';
import axios from 'axios';
import * as XLSX from 'xlsx';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const tierBadge = (tier) => {
  if (tier?.toLowerCase().includes('professional')) {
    return (
      <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-bold bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300">
        <Zap className="h-4 w-4 mr-1" /> Professional
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-bold bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">
      <Package className="h-4 w-4 mr-1" /> Standard
    </span>
  );
};

const fmtNum = (n) => {
  if (n == null) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
};

const fmtCurrency = (n) => {
  if (n == null) return '—';
  return `$${n.toLocaleString()}`;
};

const TierPill = ({ pro }) => pro ? (
  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 font-medium">PRO</span>
) : (
  <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400">STD</span>
);

// ---------------------------------------------------------------------------
// Reusable usage table
// ---------------------------------------------------------------------------
const UsageTable = ({ items, editMode, overrides, onOverride, onDismiss, onRestore, showEvidence = true, muted = false, dismissed = false }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-slate-200 dark:border-slate-700">
          <th className="text-left py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">Capability</th>
          <th className="text-right py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">Usage/Year</th>
          <th className="text-right py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">Usage/Year (Est.)</th>
          <th className="text-left py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">Unit</th>
          <th className="text-right py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">Rate</th>
          <th className="text-right py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">Credits</th>
          <th className="text-center py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">Tier</th>
          {showEvidence && <th className="text-left py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">Evidence</th>}
          {(editMode || dismissed) && <th className="text-center py-2 px-3 text-slate-500 dark:text-slate-400 font-medium w-16"></th>}
        </tr>
      </thead>
      <tbody>
        {items.map(u => {
          const annual = u.usage_per_year || u.usage_value || 0;
          const isEst = u.is_estimated;
          return (
          <tr key={u.capability_id} className={`border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-700/30 ${muted ? 'opacity-60 hover:opacity-100 transition-opacity' : ''}`}>
            <td className={`py-2 px-3 font-medium ${muted ? 'text-slate-600 dark:text-slate-300' : 'text-slate-900 dark:text-white'}`}>{u.label}</td>
            {/* Usage/Year — actual (data_days >= 365 or non-time-based) */}
            <td className="py-2 px-3 text-right">
              {editMode ? (
                <input
                  type="number"
                  value={overrides[u.capability_id] ?? (annual || '')}
                  onChange={(e) => onOverride(u.capability_id, e.target.value)}
                  placeholder="0"
                  className="w-28 text-right px-2 py-1 border border-amber-300 dark:border-amber-600 rounded bg-amber-50 dark:bg-amber-900/20 text-slate-900 dark:text-white text-sm"
                />
              ) : (
                <span className={`font-mono ${!isEst && annual > 0 ? 'text-slate-900 dark:text-white' : 'text-slate-300 dark:text-slate-600'}`}>
                  {!isEst && annual > 0 ? fmtNum(annual) : '—'}
                </span>
              )}
            </td>
            {/* Usage/Year (Est.) — extrapolated from < 365 days of data */}
            <td className="py-2 px-3 text-right">
              {!editMode && isEst && annual > 0 ? (
                <span className="font-mono text-amber-600 dark:text-amber-400" title={`Extrapolated from ${u.data_days} days of data`}>
                  {fmtNum(annual)}
                  <span className="text-xs ml-1 text-slate-400">({u.data_days}d)</span>
                </span>
              ) : (
                <span className="font-mono text-slate-300 dark:text-slate-600">—</span>
              )}
            </td>
            <td className="py-2 px-3 text-slate-500 dark:text-slate-400">{u.meter_unit}</td>
            <td className="py-2 px-3 text-right text-slate-600 dark:text-slate-300 font-mono">{u.credits_per_unit}</td>
            <td className="py-2 px-3 text-right font-semibold text-slate-900 dark:text-white font-mono">
              {u.total_credits > 0 ? fmtNum(u.total_credits) : '—'}
            </td>
            <td className="py-2 px-3 text-center"><TierPill pro={u.pro_only} /></td>
            {showEvidence && (
              <td className="py-2 px-3 text-xs text-slate-500 dark:text-slate-400 max-w-sm" style={{ whiteSpace: 'normal' }}>
                {u.scan_evidence || u.measurement_rule || '—'}
              </td>
            )}
            {editMode && !dismissed && onDismiss && (
              <td className="py-2 px-3 text-center">
                <button onClick={() => onDismiss(u.capability_id)}
                  title="Exclude from estimate"
                  className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-slate-400 hover:text-red-500 transition-colors">
                  <Trash2 className="h-4 w-4" />
                </button>
              </td>
            )}
            {dismissed && onRestore && (
              <td className="py-2 px-3 text-center">
                <button onClick={() => onRestore(u.capability_id)}
                  title="Restore to estimate"
                  className="p-1 rounded hover:bg-emerald-100 dark:hover:bg-emerald-900/30 text-slate-400 hover:text-emerald-500 transition-colors">
                  <RotateCcw className="h-4 w-4" />
                </button>
              </td>
            )}
          </tr>
          );
        })}
      </tbody>
    </table>
  </div>
);

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
function PlutusPricing() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [originalUsage, setOriginalUsage] = useState([]);
  const [overrides, setOverrides] = useState({});
  const [editMode, setEditMode] = useState(false);
  const [touchedCaps, setTouchedCaps] = useState(new Set());
  const [recalculating, setRecalculating] = useState(false);
  const [activeTab, setActiveTab] = useState('summary');
  // Dismissed capabilities
  const [dismissedCaps, setDismissedCaps] = useState(new Set());
  // Rate card editing
  const [rateCardEditing, setRateCardEditing] = useState(false);
  const [rateCardDraft, setRateCardDraft] = useState(null);
  const [rateCardSaving, setRateCardSaving] = useState(false);

  // -----------------------------------------------------------------------
  // Export to Excel
  // -----------------------------------------------------------------------
  const exportToExcel = () => {
    if (!result) return;
    const wb = XLSX.utils.book_new();
    const usage = result.capability_usage || [];

    // --- Sheet 1: Summary + Usage Breakdown ---
    const summaryRows = [
      ['WDF Credit Sizing — Summary'],
      [],
      ['Recommended Tier', result.recommended_tier || ''],
      ['Est. Annual Credits', result.total_credits || 0],
      ['Packs Required', result.min_packs || 1],
      ['Price per Pack (Yearly)', result.price_per_pack || 100000],
      ['Est. Annual Cost', result.annual_cost || 0],
      [],
      ['Usage Breakdown'],
      ['Capability', 'Usage/Year', 'Usage/Year (Est.)', 'Unit', 'Rate (credits/unit)', 'Annual Credits', 'Tier', 'Evidence'],
    ];

    const sections = [
      { label: '— Detected', items: usage.filter(u => u.measurable !== false && (u.detected || u.usage_value > 0) && !dismissedCaps.has(u.capability_id)) },
      { label: '— Measurable but not Detected', items: usage.filter(u => u.measurable !== false && !u.detected && u.usage_value === 0 && !dismissedCaps.has(u.capability_id)) },
      { label: '— Not Measured', items: usage.filter(u => u.measurable === false && !dismissedCaps.has(u.capability_id)) },
      { label: '— Excluded', items: usage.filter(u => dismissedCaps.has(u.capability_id)) },
    ];

    for (const section of sections) {
      if (section.items.length === 0) continue;
      summaryRows.push([section.label]);
      for (const u of section.items) {
        const annual = u.usage_per_year || u.usage_value || 0;
        summaryRows.push([
          u.label,
          !u.is_estimated && annual > 0 ? annual : '',
          u.is_estimated && annual > 0 ? annual : '',
          u.meter_unit,
          u.credits_per_unit,
          u.total_credits || 0,
          u.pro_only ? 'PRO' : 'STD',
          u.scan_evidence || '',
        ]);
      }
    }

    const ws1 = XLSX.utils.aoa_to_sheet(summaryRows);
    // Widen columns
    ws1['!cols'] = [
      { wch: 35 }, { wch: 14 }, { wch: 18 }, { wch: 14 },
      { wch: 16 }, { wch: 16 }, { wch: 6 }, { wch: 60 },
    ];
    XLSX.utils.book_append_sheet(wb, ws1, 'Usage Breakdown');

    // --- Sheet 2: Rate Card ---
    const rateCardRows = [
      ['WDF Rate Card'],
      [],
      ['Capability', 'Meter Unit', 'Fabric Credits', 'Tier', 'Measurable'],
    ];
    for (const cap of result.pricing_config?.rate_card || []) {
      rateCardRows.push([
        cap.label,
        cap.meter_unit,
        cap.credits,
        cap.pro_only ? 'PRO' : 'STD',
        cap.measurable !== false ? 'Auto' : 'Manual',
      ]);
    }
    const ws2 = XLSX.utils.aoa_to_sheet(rateCardRows);
    ws2['!cols'] = [{ wch: 35 }, { wch: 18 }, { wch: 14 }, { wch: 6 }, { wch: 12 }];
    XLSX.utils.book_append_sheet(wb, ws2, 'Rate Card');

    // --- Sheet 3: How Usage is Measured ---
    const measureRows = [
      ['How Usage is Measured'],
      [],
      ['Note: Usage/Year shows actual data when ≥365 days of logs exist. Usage/Year (Est.) extrapolates from shorter periods using average daily rate × 365.'],
      [],
      ['Capability', 'Tier', 'Measurable', 'Credits per Unit', 'Measurement Rule', 'Scan Tables'],
    ];
    for (const cap of result.pricing_config?.rate_card || []) {
      measureRows.push([
        cap.label,
        cap.pro_only ? 'PRO' : 'STD',
        cap.measurable !== false ? 'Auto' : 'Manual',
        cap.credits > 0 ? `${cap.credits} credit/${cap.meter_unit}` : cap.meter_unit,
        (cap.measurement_rule || cap.scan_hint || '').trim(),
        (cap.scan_tables || []).join(', '),
      ]);
    }
    const ws3 = XLSX.utils.aoa_to_sheet(measureRows);
    ws3['!cols'] = [{ wch: 35 }, { wch: 6 }, { wch: 12 }, { wch: 18 }, { wch: 80 }, { wch: 40 }];
    XLSX.utils.book_append_sheet(wb, ws3, 'How Usage is Measured');

    XLSX.writeFile(wb, 'WDF_Credit_Sizing.xlsx');
  };

  const runScan = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await axios.post('/api/plutus/scan');
      setResult(resp.data);
      setOriginalUsage(resp.data.capability_usage || []);
      setDismissedCaps(new Set());
      setTouchedCaps(new Set());
      const ov = {};
      for (const u of resp.data.capability_usage || []) {
        const annual = u.usage_per_year || u.usage_value || 0;
        if (annual > 0) ov[u.capability_id] = annual;
      }
      setOverrides(ov);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  const recalculate = useCallback(async (newOverrides) => {
    setRecalculating(true);
    try {
      const resp = await axios.post('/api/plutus/recalculate', {
        overrides: newOverrides || overrides,
        previous_usage: originalUsage,
      });
      setResult(resp.data);
    } catch (e) {
      console.error('Recalculate failed:', e);
    } finally {
      setRecalculating(false);
    }
  }, [overrides, result]);

  const handleOverride = (capId, value) => {
    setOverrides(prev => ({ ...prev, [capId]: parseFloat(value) || 0 }));
    setTouchedCaps(prev => new Set([...prev, capId]));
  };

  const applyOverrides = () => {
    // Only send overrides for capabilities the user actually changed + dismissed
    const finalOv = {};
    for (const capId of touchedCaps) {
      finalOv[capId] = overrides[capId] ?? 0;
    }
    for (const capId of dismissedCaps) {
      finalOv[capId] = 0;
    }
    recalculate(finalOv);
    setEditMode(false);
    setTouchedCaps(new Set());
  };

  const dismissCapability = (capId) => {
    setDismissedCaps(prev => new Set([...prev, capId]));
  };

  const restoreCapability = (capId) => {
    const newDismissed = new Set(dismissedCaps);
    newDismissed.delete(capId);
    setDismissedCaps(newDismissed);
    // Remove from touched so backend uses original scan evidence
    const newTouched = new Set(touchedCaps);
    newTouched.delete(capId);
    setTouchedCaps(newTouched);
    // Restore original scanned value from the initial scan
    const orig = originalUsage.find(u => u.capability_id === capId);
    if (orig) {
      setOverrides(prev => ({ ...prev, [capId]: orig.usage_per_year || orig.usage_value }));
    }
    // Recalculate: send only touched + remaining dismissed as overrides
    const finalOv = {};
    for (const cid of newTouched) {
      finalOv[cid] = overrides[cid] ?? 0;
    }
    for (const cid of newDismissed) {
      finalOv[cid] = 0;
    }
    recalculate(finalOv);
  };

  // Rate card editing
  const startRateCardEdit = () => {
    const config = result?.pricing_config;
    if (config) {
      setRateCardDraft(JSON.parse(JSON.stringify(config)));
      setRateCardEditing(true);
    }
  };

  const updateRateCardField = (capIdx, field, value) => {
    setRateCardDraft(prev => {
      const next = { ...prev, rate_card: [...prev.rate_card] };
      next.rate_card[capIdx] = { ...next.rate_card[capIdx], [field]: value };
      return next;
    });
  };

  const addRateCardCapability = () => {
    setRateCardDraft(prev => {
      const next = { ...prev, rate_card: [...prev.rate_card] };
      next.rate_card.push({
        id: `custom_${Date.now()}`,
        label: 'New Capability',
        meter_unit: 'Unit',
        credits: 1,
        pro_only: false,
        measurable: false,
        scan_tables: [],
        scan_method: 'manual',
        scan_hint: '',
        measurement_rule: 'Manually entered.',
      });
      return next;
    });
  };

  const removeRateCardCapability = (idx) => {
    setRateCardDraft(prev => {
      const next = { ...prev, rate_card: prev.rate_card.filter((_, i) => i !== idx) };
      return next;
    });
  };

  const saveRateCard = async () => {
    setRateCardSaving(true);
    try {
      await axios.post('/api/plutus/config', rateCardDraft);
      setRateCardEditing(false);
      setRateCardDraft(null);
      // Re-scan to pick up new rates
      await runScan();
    } catch (e) {
      console.error('Save failed:', e);
    } finally {
      setRateCardSaving(false);
    }
  };

  // -----------------------------------------------------------------------
  // Initial state
  // -----------------------------------------------------------------------
  if (!result && !loading) {
    return (
      <div className="space-y-6">
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-8 text-center">
          <Calculator className="h-16 w-16 text-amber-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-2">
            Workflow Data Fabric — Credit Estimator
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 max-w-lg mx-auto mb-6">
            Scan the connected ServiceNow instance to estimate WDF credit consumption.
            Measures actual execution volumes for Integration Hub, API egress, and RPA.
            Identifies candidates for Zero Copy Connectors, Stream Connect, and Data Catalog.
          </p>
          <button
            onClick={runScan}
            className="inline-flex items-center px-6 py-3 bg-amber-500 hover:bg-amber-600 text-white font-semibold rounded-lg shadow-sm transition-colors"
          >
            <Database className="h-5 w-5 mr-2" />
            Scan Instance
          </button>
          {error && (
            <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  // -----------------------------------------------------------------------
  // Loading
  // -----------------------------------------------------------------------
  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-12 text-center">
        <Loader2 className="h-12 w-12 text-amber-500 animate-spin mx-auto mb-4" />
        <p className="text-slate-600 dark:text-slate-300 font-medium">Running Plutus scan...</p>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Scanning execution logs, data sources, outbound HTTP...
        </p>
      </div>
    );
  }

  // -----------------------------------------------------------------------
  // Results — categorize capabilities
  // -----------------------------------------------------------------------
  const usage = result?.capability_usage || [];
  const detected = usage.filter(u => u.measurable !== false && (u.detected || u.usage_value > 0) && !dismissedCaps.has(u.capability_id));
  const measurableNotDetected = usage.filter(u => u.measurable !== false && !u.detected && u.usage_value === 0 && !dismissedCaps.has(u.capability_id));
  const notMeasured = usage.filter(u => u.measurable === false && !dismissedCaps.has(u.capability_id));
  const dismissedItems = usage.filter(u => dismissedCaps.has(u.capability_id));
  const rateCardSource = rateCardEditing ? (rateCardDraft?.rate_card || []) : (result?.pricing_config?.rate_card || []);

  return (
    <div className="space-y-6">
      {/* ===== Header bar ===== */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">WDF Credit Sizing</h2>
          {recalculating && <Loader2 className="h-4 w-4 text-amber-500 animate-spin" />}
        </div>
        <div className="flex items-center space-x-2">
          <button onClick={exportToExcel}
            className="inline-flex items-center px-3 py-1.5 text-sm bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300 rounded-lg hover:bg-emerald-100 dark:hover:bg-emerald-900/40 transition-colors border border-emerald-200 dark:border-emerald-700/50">
            <Download className="h-4 w-4 mr-1" /> Export Excel
          </button>
          <button onClick={runScan} disabled={loading}
            className="inline-flex items-center px-3 py-1.5 text-sm bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors">
            <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} /> Re-scan
          </button>
          {!editMode ? (
            <button onClick={() => setEditMode(true)}
              className="inline-flex items-center px-3 py-1.5 text-sm bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 rounded-lg hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors">
              <Edit3 className="h-4 w-4 mr-1" /> Edit Usage
            </button>
          ) : (
            <button onClick={applyOverrides}
              className="inline-flex items-center px-3 py-1.5 text-sm bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors">
              <Save className="h-4 w-4 mr-1" /> Recalculate
            </button>
          )}
        </div>
      </div>

      {/* ===== Summary cards ===== */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-4">
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">Recommended Tier</p>
          <div className="mb-1">{tierBadge(result?.recommended_tier)}</div>
          {result?.requires_pro && result?.pro_reasons?.length > 0 && (
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">{result.pro_reasons[0]}</p>
          )}
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-4">
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">Est. Annual Credits</p>
          <p className="text-2xl font-bold text-slate-900 dark:text-white">{fmtNum(result?.total_credits)}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">of {fmtNum((result?.min_packs || 1) * (result?.credits_per_pack || 2000000))} available</p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-4">
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">Packs Required</p>
          <p className="text-2xl font-bold text-slate-900 dark:text-white">{result?.min_packs || 1}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">@ {fmtCurrency(result?.price_per_pack || 100000)} / pack / yr</p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-4">
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">Est. Annual Cost</p>
          <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">{fmtCurrency(result?.annual_cost)}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">minimum list price</p>
        </div>
      </div>

      {/* ===== Tab nav ===== */}
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700">
        <div className="border-b border-slate-200 dark:border-slate-700">
          <nav className="flex space-x-4 px-6 overflow-x-auto" aria-label="Tabs">
            {[
              { key: 'summary', label: 'Usage Breakdown', icon: Layers },
              { key: 'rate-card', label: 'Rate Card', icon: DollarSign },
              { key: 'measurement', label: 'How Usage is Measured', icon: BookOpen },
            ].map(tab => (
              <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors flex items-center space-x-2 whitespace-nowrap ${
                  activeTab === tab.key
                    ? 'border-amber-500 text-amber-600 dark:text-amber-400'
                    : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
                }`}>
                <tab.icon className="h-4 w-4" />
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">

          {/* ================================================================
              USAGE BREAKDOWN TAB — 3 sections
              ================================================================ */}
          {activeTab === 'summary' && (
            <div className="space-y-6">
              {/* Section 1: Detected */}
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center mb-3">
                  <CheckCircle2 className="h-4 w-4 text-emerald-500 mr-2" />
                  Detected ({detected.length})
                </h3>
                {detected.length > 0 ? (
                  <>
                    <UsageTable items={detected} editMode={editMode} overrides={overrides} onOverride={handleOverride} onDismiss={dismissCapability} />
                    <div className="mt-2 text-right">
                      <span className="text-sm font-bold text-amber-600 dark:text-amber-400">
                        Total: {fmtNum(result?.total_credits)} credits
                      </span>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-slate-500 dark:text-slate-400 ml-6">No measurable usage detected on this instance.</p>
                )}
              </div>

              {/* Section 2: Measurable but not Detected */}
              {measurableNotDetected.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center mb-3">
                    <Search className="h-4 w-4 text-blue-400 mr-2" />
                    Measurable but not Detected ({measurableNotDetected.length})
                    {editMode && <span className="text-xs font-normal text-slate-500 ml-2">— enter values to include</span>}
                  </h3>
                  <UsageTable items={measurableNotDetected} editMode={editMode} overrides={overrides} onOverride={handleOverride} onDismiss={dismissCapability} muted />
                </div>
              )}

              {/* Section: Dismissed */}
              {dismissedItems.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center mb-3">
                    <Trash2 className="h-4 w-4 text-red-400 mr-2" />
                    Excluded ({dismissedItems.length})
                    <span className="text-xs font-normal text-slate-500 ml-2">— removed from credit estimate</span>
                  </h3>
                  <UsageTable items={dismissedItems} editMode={false} overrides={overrides} onOverride={handleOverride} onRestore={restoreCapability} muted dismissed />
                </div>
              )}

              {/* Section 3: Not Measured */}
              {notMeasured.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center mb-3">
                    <EyeOff className="h-4 w-4 text-slate-400 mr-2" />
                    Not Measured ({notMeasured.length})
                    <span className="text-xs font-normal text-slate-500 ml-2">— usage not accessible via REST API</span>
                  </h3>
                  <UsageTable items={notMeasured} editMode={editMode} overrides={overrides} onOverride={handleOverride} onDismiss={dismissCapability} muted />
                </div>
              )}
            </div>
          )}


          {/* ================================================================
              RATE CARD TAB — editable in browser
              ================================================================ */}
          {activeTab === 'rate-card' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  WDF v2 Data Fabric Credit rate card.
                </p>
                {!rateCardEditing ? (
                  <button onClick={startRateCardEdit}
                    className="inline-flex items-center px-3 py-1.5 text-sm bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 rounded-lg hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors">
                    <Edit3 className="h-4 w-4 mr-1" /> Edit Rate Card
                  </button>
                ) : (
                  <div className="flex items-center space-x-2">
                    <button onClick={() => { setRateCardEditing(false); setRateCardDraft(null); }}
                      className="inline-flex items-center px-3 py-1.5 text-sm bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors">
                      <X className="h-4 w-4 mr-1" /> Cancel
                    </button>
                    <button onClick={saveRateCard} disabled={rateCardSaving}
                      className="inline-flex items-center px-3 py-1.5 text-sm bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors">
                      {rateCardSaving ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
                      Save & Re-scan
                    </button>
                  </div>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-700/50">
                      <th className="text-left py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">Capability</th>
                      <th className="text-left py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">Meter Unit</th>
                      <th className="text-right py-2 px-3 text-slate-500 dark:text-slate-400 font-medium"># Fabric Credits</th>
                      <th className="text-center py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">Tier</th>
                      <th className="text-center py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">Measurable</th>
                      {rateCardEditing && <th className="text-center py-2 px-3 text-slate-500 dark:text-slate-400 font-medium w-12"></th>}
                    </tr>
                  </thead>
                  <tbody>
                    {rateCardSource.map((cap, idx) => (
                      <tr key={cap.id} className="border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-700/30">
                        <td className="py-2 px-3 font-medium text-slate-900 dark:text-white">
                          {rateCardEditing ? (
                            <input type="text" value={cap.label || ''} onChange={(e) => updateRateCardField(idx, 'label', e.target.value)}
                              className="w-full px-2 py-1 border border-amber-300 dark:border-amber-600 rounded bg-amber-50 dark:bg-amber-900/20 text-slate-900 dark:text-white text-sm" />
                          ) : cap.label}
                        </td>
                        <td className="py-2 px-3 text-slate-600 dark:text-slate-300">
                          {rateCardEditing ? (
                            <input type="text" value={cap.meter_unit || ''} onChange={(e) => updateRateCardField(idx, 'meter_unit', e.target.value)}
                              className="w-40 px-2 py-1 border border-amber-300 dark:border-amber-600 rounded bg-amber-50 dark:bg-amber-900/20 text-slate-900 dark:text-white text-sm" />
                          ) : cap.meter_unit}
                        </td>
                        <td className="py-2 px-3 text-right font-mono font-semibold text-slate-900 dark:text-white">
                          {rateCardEditing ? (
                            <input type="number" value={cap.credits ?? 0} onChange={(e) => updateRateCardField(idx, 'credits', parseFloat(e.target.value) || 0)}
                              className="w-20 text-right px-2 py-1 border border-amber-300 dark:border-amber-600 rounded bg-amber-50 dark:bg-amber-900/20 text-slate-900 dark:text-white text-sm" />
                          ) : (
                            cap.credits > 0 ? `${cap.credits} credit${cap.credits !== 1 ? 's' : ''}` : 'Included'
                          )}
                        </td>
                        <td className="py-2 px-3 text-center">
                          {rateCardEditing ? (
                            <button onClick={() => updateRateCardField(idx, 'pro_only', !cap.pro_only)}
                              className={`text-xs px-2 py-0.5 rounded-full font-medium transition-colors ${cap.pro_only ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300' : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'}`}>
                              {cap.pro_only ? 'PRO' : 'STD'}
                            </button>
                          ) : <TierPill pro={cap.pro_only} />}
                        </td>
                        <td className="py-2 px-3 text-center">
                          {cap.measurable !== false ? (
                            <span className="text-xs text-emerald-600 dark:text-emerald-400">Auto</span>
                          ) : (
                            <span className="text-xs text-slate-400 dark:text-slate-500">Manual</span>
                          )}
                        </td>
                        {rateCardEditing && (
                          <td className="py-2 px-3 text-center">
                            <button onClick={() => removeRateCardCapability(idx)}
                              title="Remove capability"
                              className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-slate-400 hover:text-red-500 transition-colors">
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {rateCardEditing && (
                  <button onClick={addRateCardCapability}
                    className="mt-3 inline-flex items-center px-3 py-1.5 text-sm bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300 rounded-lg hover:bg-emerald-100 dark:hover:bg-emerald-900/40 transition-colors border border-emerald-200 dark:border-emerald-700/50">
                    + Add Capability
                  </button>
                )}
              </div>

              {/* Tier summary cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
                <div className="border border-emerald-200 dark:border-emerald-700/50 rounded-lg p-4 bg-emerald-50/50 dark:bg-emerald-900/10">
                  <h4 className="font-semibold text-emerald-700 dark:text-emerald-300 mb-2 flex items-center">
                    <Package className="h-4 w-4 mr-2" /> WDF Standard
                  </h4>
                  <ul className="text-sm text-slate-600 dark:text-slate-300 space-y-1">
                    <li>Min 1 pack — $100K/yr — 2M credits</li>
                    <li>Integration Hub, RPA, API Access</li>
                    <li>External Content Connectors</li>
                    <li>AI Data Explorer</li>
                  </ul>
                </div>
                <div className="border border-amber-200 dark:border-amber-700/50 rounded-lg p-4 bg-amber-50/50 dark:bg-amber-900/10">
                  <h4 className="font-semibold text-amber-700 dark:text-amber-300 mb-2 flex items-center">
                    <Zap className="h-4 w-4 mr-2" /> WDF Professional
                  </h4>
                  <ul className="text-sm text-slate-600 dark:text-slate-300 space-y-1">
                    <li>Min 4 packs — $400K/yr — 8M credits</li>
                    <li className="font-medium">Everything in Standard, plus:</li>
                    <li>Stream Connect for Apache Kafka</li>
                    <li>Zero Copy Connectors (SQL, ERP)</li>
                    <li>Data Catalog</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* ================================================================
              HOW USAGE IS MEASURED TAB
              ================================================================ */}
          {activeTab === 'measurement' && (
            <div className="space-y-4">
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
                How Plutus measures each WDF capability on the connected instance.
              </p>
              <div className="border border-blue-200 dark:border-blue-700/50 rounded-lg p-4 bg-blue-50/50 dark:bg-blue-900/10 mb-2">
                <h4 className="font-semibold text-blue-700 dark:text-blue-300 mb-2 flex items-center">
                  <Info className="h-4 w-4 mr-2" /> Understanding Usage/Year vs Usage/Year (Est.)
                </h4>
                <div className="text-sm text-slate-600 dark:text-slate-300 space-y-2">
                  <p>
                    <strong>Usage/Year</strong> — Shown when the instance holds <strong>365 days or more</strong> of execution log data for that capability.
                    The value represents the actual observed count over the full data retention window and can be treated as a reliable annual figure.
                  </p>
                  <p>
                    <strong>Usage/Year (Est.)</strong> — Shown when the instance holds <strong>fewer than 365 days</strong> of data (e.g. 90-day log retention).
                    The value is extrapolated using the <em>average daily rate</em> method:
                  </p>
                  <p className="font-mono text-xs bg-white dark:bg-slate-800 rounded px-3 py-2 border border-slate-200 dark:border-slate-700">
                    yearly estimate = (observed count / days of data) × 365
                  </p>
                  <p>
                    The number of days used is shown in parentheses, e.g. <span className="font-mono text-amber-600 dark:text-amber-400">(90d)</span>.
                    This approach uses the mean daily rate, which avoids the bias of peak-period or low-period extrapolation and produces a neutral, defensible annual estimate.
                  </p>
                  <p>
                    For capabilities that measure <strong>definitions</strong> rather than time-based logs (e.g. count of supported databases, reports),
                    the value is shown as Usage/Year because it reflects the current cumulative state, not a time-series.
                  </p>
                </div>
              </div>
              {[...(result?.pricing_config?.rate_card || [])].sort((a, b) => {
                // 1. Name A-Z
                const nameCompare = (a.label || '').localeCompare(b.label || '');
                if (nameCompare !== 0) return nameCompare;
                // 2. STD before PRO
                if (a.pro_only !== b.pro_only) return a.pro_only ? 1 : -1;
                // 3. Auto before Manual
                const aAuto = a.measurable !== false ? 0 : 1;
                const bAuto = b.measurable !== false ? 0 : 1;
                return aAuto - bAuto;
              }).map(cap => (
                <div key={cap.id} className="border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-slate-900 dark:text-white">{cap.label}</span>
                      <TierPill pro={cap.pro_only} />
                      {cap.measurable !== false ? (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">Auto-measured</span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-200 dark:bg-slate-600 text-slate-600 dark:text-slate-300">Manual entry</span>
                      )}
                    </div>
                    <span className="text-xs text-slate-400 dark:text-slate-500 font-mono">
                      {cap.credits > 0 ? `${cap.credits} credit/${cap.meter_unit}` : cap.meter_unit}
                    </span>
                  </div>
                  <p className="text-sm text-slate-600 dark:text-slate-300 whitespace-pre-line">
                    {cap.measurement_rule || cap.scan_hint || 'No measurement rule defined.'}
                  </p>
                  {cap.scan_tables && cap.scan_tables.length > 0 && (
                    <div className="mt-2 flex items-center space-x-1">
                      <span className="text-xs text-slate-400">Tables:</span>
                      {cap.scan_tables.map(t => (
                        <code key={t} className="text-xs bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 rounded text-slate-600 dark:text-slate-300">{t}</code>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

export default PlutusPricing;
