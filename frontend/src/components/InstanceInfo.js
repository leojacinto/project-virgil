import React, { useState, useEffect, useRef } from 'react';
import { Database, Package, Workflow, Loader2, RefreshCw, Search, Lock, Shield, GitBranch, AlertTriangle, ChevronDown, ChevronRight, CheckCircle2, Info, Eye, Lightbulb, ClipboardList, BarChart3, BookOpen, ArrowRight, Download, FileText, Pencil, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import RuleEditor from './RuleEditor';
import { downloadMermaid, exportToPDF } from '../utils/exportUtils';
import axios from 'axios';
import mermaid from 'mermaid';

function InstanceInfo() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState({
    tables: [],
    applications: [],
    components: {}
  });
  const [assessLoading, setAssessLoading] = useState(false);
  const [assessResult, setAssessResult] = useState(null);
  const [assessError, setAssessError] = useState(null);
  const [ruleSummary, setRuleSummary] = useState(null);
  const [rulesExpanded, setRulesExpanded] = useState(false);
  const [assessTab, setAssessTab] = useState('gap-analysis');
  const [knowledgeBase, setKnowledgeBase] = useState(null);
  const [kbExpanded, setKbExpanded] = useState(null);
  const [ruleExpanded, setRuleExpanded] = useState(null);
  const [writeMode, setWriteMode] = useState(false);
  const diagramRef = useRef(null);
  const diagramWrapRef = useRef(null);
  const assessContentRef = useRef(null);
  const [exporting, setExporting] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const isPanning = useRef(false);
  const panStart = useRef({ x: 0, y: 0 });

  useEffect(() => {
    loadInstanceData();
    loadRuleSummary();
    loadKnowledgeBase();
    mermaid.initialize({
      startOnLoad: false,
      theme: 'default',
      securityLevel: 'loose',
      flowchart: { useMaxWidth: true, htmlLabels: true },
    });
  }, []);

  useEffect(() => {
    if (assessResult && diagramRef.current) {
      const renderDiagram = async () => {
        const container = diagramRef.current;
        if (!container) return;
        const diagramCode = assessTab === 'recommended' && assessResult.recommended_diagram
          ? assessResult.recommended_diagram
          : assessResult.as_is_diagram;
        if (!diagramCode) return;
        container.innerHTML = '';
        setZoom(1);
        setPan({ x: 0, y: 0 });
        try {
          const id = `minos-${Date.now()}`;
          const { svg } = await mermaid.render(id, diagramCode);
          container.innerHTML = svg;
          const svgEl = container.querySelector('svg');
          if (svgEl) {
            svgEl.style.maxWidth = 'none';
            svgEl.style.width = '100%';
            svgEl.style.height = 'auto';
          }
        } catch (e) {
          container.innerHTML = `<pre class="text-xs text-red-500">${e.message}</pre>`;
        }
      };
      renderDiagram();
    }
  }, [assessResult, assessTab]);

  const handleWheelRef = useRef(null);
  handleWheelRef.current = (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setZoom(z => Math.min(Math.max(0.2, z + delta), 5));
  };

  useEffect(() => {
    const el = diagramWrapRef.current;
    if (!el) return;
    const handler = (e) => handleWheelRef.current(e);
    el.addEventListener('wheel', handler, { passive: false });
    return () => el.removeEventListener('wheel', handler);
  });

  const handleMouseDown = (e) => {
    if (e.button !== 0) return;
    isPanning.current = true;
    panStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    e.currentTarget.style.cursor = 'grabbing';
  };

  const handleMouseMove = (e) => {
    if (!isPanning.current) return;
    setPan({ x: e.clientX - panStart.current.x, y: e.clientY - panStart.current.y });
  };

  const handleMouseUp = (e) => {
    isPanning.current = false;
    if (e.currentTarget) e.currentTarget.style.cursor = 'grab';
  };

  const loadRuleSummary = async () => {
    try {
      const res = await axios.get('/api/assess/rules');
      setRuleSummary(res.data.summary);
    } catch (err) {
      // Non-critical — just won't show rule preview
    }
  };

  const loadKnowledgeBase = async () => {
    try {
      const res = await axios.get('/api/assess/knowledge-base');
      setKnowledgeBase(res.data.sources);
    } catch (err) {
      // Non-critical
    }
  };

  const runAssessment = async () => {
    setAssessLoading(true);
    setAssessError(null);
    setAssessResult(null);
    try {
      const res = await axios.post('/api/assess');
      setAssessResult(res.data);
    } catch (err) {
      setAssessError(err.response?.data?.detail || 'Assessment failed');
    } finally {
      setAssessLoading(false);
    }
  };

  const loadInstanceData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Use new comprehensive endpoint that combines SN Utils REST API + JDBC metadata
      const summaryRes = await axios.get('/api/servicenow/instance-summary');
      
      // Also get tables for backward compatibility
      const tablesRes = await axios.get('/api/servicenow/tables');
      
      // Also get components for workflow/business rules data
      const componentsRes = await axios.get('/api/servicenow/components');

      const comps = componentsRes.data.components || {};
      setData({
        tables: tablesRes.data.tables || [],
        tableCount: tablesRes.data.count || (tablesRes.data.tables || []).length,
        applications: summaryRes.data.applications || [],
        components: comps,
        componentCounts: comps.counts || {},
        capabilities: summaryRes.data.key_capabilities || {},
        jdbcMetadata: summaryRes.data.jdbc_metadata || {}
      });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch instance data');
    } finally {
      setLoading(false);
    }
  };

  const StatCard = ({ icon: Icon, title, count, color }) => (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-1">{title}</p>
          <p className="text-3xl font-bold text-slate-900 dark:text-white">{count}</p>
        </div>
        <div className={`p-3 rounded-lg ${color}`}>
          <Icon className="h-8 w-8 text-white" />
        </div>
      </div>
    </div>
  );

  const describeCheck = (check) => {
    if (check.plugin_absent) return <><span className="font-mono text-amber-600 dark:text-amber-400">plugin_absent</span> <span className="font-mono">{check.plugin_absent}</span></>;
    if (check.plugin_present) return <><span className="font-mono text-emerald-600 dark:text-emerald-400">plugin_present</span> <span className="font-mono">{check.plugin_present}</span></>;
    if (check.table_lte) return <><span className="font-mono text-blue-600 dark:text-blue-400">table</span> <span className="font-mono">{check.table_lte.table}</span> ≤ {check.table_lte.value}</>;
    if (check.table_eq) return <><span className="font-mono text-blue-600 dark:text-blue-400">table</span> <span className="font-mono">{check.table_eq.table}</span> = {check.table_eq.value}</>;
    if (check.table_gt) return <><span className="font-mono text-blue-600 dark:text-blue-400">table</span> <span className="font-mono">{check.table_gt.table}</span> &gt; {check.table_gt.value}</>;
    if (check.table_between) return <><span className="font-mono text-blue-600 dark:text-blue-400">table</span> <span className="font-mono">{check.table_between.table}</span> in [{check.table_between.min}, {check.table_between.below})</>;
    if (check.table_exceeds) return <><span className="font-mono text-blue-600 dark:text-blue-400">table</span> <span className="font-mono">{check.table_exceeds.table}</span> &gt; <span className="font-mono">{check.table_exceeds.other}</span></>;
    if (check.table_ratio_below) return <><span className="font-mono text-blue-600 dark:text-blue-400">table</span> <span className="font-mono">{check.table_ratio_below.table}</span> &lt; <span className="font-mono">{check.table_ratio_below.other}</span> × {check.table_ratio_below.ratio}</>;
    if (check.cmdb_below) return <><span className="font-mono text-purple-600 dark:text-purple-400">cmdb</span> {check.cmdb_below.field} &lt; {check.cmdb_below.value}</>;
    if (check.cmdb_gt) return <><span className="font-mono text-purple-600 dark:text-purple-400">cmdb</span> {check.cmdb_gt.field} &gt; {check.cmdb_gt.value}</>;
    if (check.cmdb_flag_false) return <><span className="font-mono text-purple-600 dark:text-purple-400">cmdb</span> {check.cmdb_flag_false} = false</>;
    if (check.property_neq) return <><span className="font-mono text-orange-600 dark:text-orange-400">property</span> <span className="font-mono">{check.property_neq.property}</span> ≠ {check.property_neq.value}</>;
    if (check.property_prefix_absent) return <><span className="font-mono text-orange-600 dark:text-orange-400">property</span> no {check.property_prefix_absent}* found</>;
    if (check.mid_server_eq !== undefined) return <><span className="font-mono text-cyan-600 dark:text-cyan-400">mid_servers</span> count = {check.mid_server_eq}</>;
    if (check.flow_count_eq !== undefined) return <><span className="font-mono text-cyan-600 dark:text-cyan-400">flows</span> count = {check.flow_count_eq}</>;
    if (check.all || check.any) return renderEvalBlock(check, 1);
    return <span className="font-mono text-slate-500">{JSON.stringify(check)}</span>;
  };

  const renderEvalBlock = (block, depth = 0) => {
    if (!block) return null;
    const ml = depth > 0 ? `ml-${Math.min(depth * 3, 6)}` : '';
    if (block.all) {
      return (
        <div className={ml}>
          <span className="text-[9px] font-semibold text-slate-500 uppercase">all of:</span>
          {block.all.map((check, i) => (
            <div key={i} className="flex items-start space-x-1 ml-2">
              <span className="text-indigo-400 text-[9px] mt-px">•</span>
              <span className="text-[9px] text-slate-700 dark:text-slate-300">{describeCheck(check)}</span>
            </div>
          ))}
        </div>
      );
    }
    if (block.any) {
      return (
        <div className={ml}>
          <span className="text-[9px] font-semibold text-slate-500 uppercase">any of:</span>
          {block.any.map((check, i) => (
            <div key={i} className="flex items-start space-x-1 ml-2">
              <span className="text-amber-400 text-[9px] mt-px">•</span>
              <span className="text-[9px] text-slate-700 dark:text-slate-300">{describeCheck(check)}</span>
            </div>
          ))}
        </div>
      );
    }
    if (block.streams_covered_below) {
      const info = block.streams_covered_below;
      return (
        <div className={ml}>
          <span className="text-[9px] font-semibold text-slate-500 uppercase">value streams covered &lt; {info.threshold}:</span>
          {Object.entries(info.streams).map(([name, streamBlock]) => (
            <div key={name} className="ml-2">
              <span className="text-[9px] font-mono font-semibold text-slate-600 dark:text-slate-400">{name}:</span>
              {renderEvalBlock(streamBlock, depth + 1)}
            </div>
          ))}
        </div>
      );
    }
    return <span className="text-[9px] font-mono text-slate-500">{JSON.stringify(block)}</span>;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
          ServiceNow Instance Overview
        </h3>
        <button
          onClick={loadInstanceData}
          disabled={loading}
          className="flex items-center space-x-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {loading && !data.tables.length ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 text-primary-600 animate-spin" />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard
              icon={Database}
              title="Available Tables"
              count={data.tableCount || data.tables.length}
              color="bg-blue-600"
            />
            <StatCard
              icon={Package}
              title="Installed Applications"
              count={data.applications.length}
              color="bg-green-600"
            />
            <StatCard
              icon={Workflow}
              title="Active Workflows"
              count={data.componentCounts?.workflows || data.components.workflows?.length || 0}
              color="bg-purple-600"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-6">
              <h4 className="font-semibold text-slate-900 dark:text-white mb-4 flex items-center space-x-2">
                <Database className="h-5 w-5 text-blue-600" />
                <span>Recent Tables</span>
              </h4>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {data.tables.slice(0, 20).map((table, index) => (
                  <div
                    key={index}
                    className="px-3 py-2 bg-slate-50 dark:bg-slate-700/50 rounded text-sm text-slate-700 dark:text-slate-300 font-mono"
                  >
                    {table}
                  </div>
                ))}
                {(data.tableCount || data.tables.length) > 20 && (
                  <p className="text-xs text-slate-500 text-center pt-2">
                    ... and {(data.tableCount || data.tables.length) - 20} more tables
                  </p>
                )}
              </div>
            </div>

            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-6">
              <h4 className="font-semibold text-slate-900 dark:text-white mb-4 flex items-center space-x-2">
                <Package className="h-5 w-5 text-green-600" />
                <span>Installed Applications</span>
              </h4>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {data.applications.slice(0, 10).map((app, index) => (
                  <div
                    key={index}
                    className="p-3 bg-slate-50 dark:bg-slate-700/50 rounded border border-slate-200 dark:border-slate-700"
                  >
                    <p className="text-sm font-medium text-slate-900 dark:text-white">{app.name}</p>
                    <div className="flex items-center space-x-3 mt-1">
                      {app.version && (
                        <span className="text-xs text-slate-600 dark:text-slate-400">v{app.version}</span>
                      )}
                      {app.scope && (
                        <span className="text-xs text-slate-600 dark:text-slate-400 font-mono">{app.scope}</span>
                      )}
                    </div>
                  </div>
                ))}
                {data.applications.length > 10 && (
                  <p className="text-xs text-slate-500 text-center pt-2">
                    ... and {data.applications.length - 10} more applications
                  </p>
                )}
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-6">
            <h4 className="font-semibold text-slate-900 dark:text-white mb-4 flex items-center space-x-2">
              <Workflow className="h-5 w-5 text-purple-600" />
              <span>Components Summary</span>
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(data.components).filter(([key]) => key !== 'counts').map(([key, value]) => (
                <div key={key} className="bg-slate-50 dark:bg-slate-700/50 p-4 rounded-lg">
                  <p className="text-xs text-slate-600 dark:text-slate-400 mb-1">
                    {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </p>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white">
                    {data.componentCounts?.[key] || (Array.isArray(value) ? value.length : 0)}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* ============================================================ */}
          {/* Instance Assessment (Minos) */}
          {/* ============================================================ */}
          <div className="bg-white dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100 dark:border-slate-700 bg-gradient-to-r from-slate-50 to-white dark:from-slate-800 dark:to-slate-800">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-indigo-100">
                    <Search className="h-5 w-5 text-indigo-600" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-slate-900 dark:text-white flex items-center space-x-2">
                      <span>Instance Assessment</span>
                      <span className="text-[10px] font-medium text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded">Minos</span>
                    </h4>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      Deterministic analysis against {ruleSummary?.total_rules || 33} rules. No LLM required.
                    </p>
                  </div>
                </div>
                {assessResult && assessResult.status === 'completed' && (
                  <button
                    onClick={async () => {
                      setExporting(true);
                      try {
                        await exportToPDF(assessContentRef.current, 'Instance_Assessment');
                      } finally {
                        setExporting(false);
                      }
                    }}
                    disabled={exporting}
                    className="flex items-center space-x-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-600 transition-colors disabled:opacity-50"
                    title="Export assessment to PDF"
                  >
                    {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                    <span>PDF</span>
                  </button>
                )}
                <button
                  onClick={runAssessment}
                  disabled={assessLoading || (ruleSummary && !ruleSummary.enabled)}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    ruleSummary && !ruleSummary.enabled
                      ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                      : 'bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50'
                  }`}
                >
                  {assessLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : ruleSummary && !ruleSummary.enabled ? (
                    <Lock className="h-4 w-4" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                  <span>{assessLoading ? 'Scanning...' : ruleSummary && !ruleSummary.enabled ? 'Pending Approval' : 'Run Assessment'}</span>
                </button>
              </div>
            </div>

            <div className="px-6 py-4">
              {/* Disabled state */}
              {ruleSummary && !ruleSummary.enabled && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                  <div className="flex items-start space-x-3">
                    <Lock className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-amber-800">Assessment rules pending approval</p>
                      <p className="text-xs text-amber-600 mt-1">
                        The rule engine contains knowledge derived from external sources that require
                        author approval before activation. The scanner infrastructure is ready and will
                        be enabled once approvals are received.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Error state */}
              {assessError && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                  <p className="text-sm text-red-700">{assessError}</p>
                </div>
              )}

              {/* Assessment results with tabs */}
              {assessResult && assessResult.status === 'completed' && (
                <div ref={assessContentRef}>
                  {/* IT4IT Coverage Bar */}
                  {assessResult.it4it_coverage && (
                    <div className="mb-4 p-3 bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-700 rounded-lg">
                      <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-2">IT4IT Value Stream Coverage</p>
                      <div className="grid grid-cols-4 gap-2">
                        {[
                          { key: 'S2P', label: 'Strategy to Portfolio', icon: '📋' },
                          { key: 'R2D', label: 'Requirement to Deploy', icon: '🚀' },
                          { key: 'R2F', label: 'Request to Fulfill', icon: '📨' },
                          { key: 'D2C', label: 'Detect to Correct', icon: '🔍' },
                        ].map(({ key, label, icon }) => (
                          <div key={key} className={`p-2 rounded-lg border text-center ${
                            assessResult.it4it_coverage[key]
                              ? 'bg-emerald-50 border-emerald-200'
                              : 'bg-red-50 border-red-200'
                          }`}>
                            <p className="text-sm">{icon}</p>
                            <p className={`text-[10px] font-bold ${
                              assessResult.it4it_coverage[key] ? 'text-emerald-700' : 'text-red-600'
                            }`}>{key}</p>
                            <p className="text-[9px] text-slate-500 leading-tight">{label}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Stats Row */}
                  <div className="grid grid-cols-4 gap-2 mb-4">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-2 text-center">
                      <p className="text-lg font-bold text-blue-700">{assessResult.active_node_count || 0}</p>
                      <p className="text-[10px] text-blue-600">Active Components</p>
                    </div>
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 text-center">
                      <p className="text-lg font-bold text-amber-700">{assessResult.recommended_node_count || 0}</p>
                      <p className="text-[10px] text-amber-600">Recommended</p>
                    </div>
                    <div className="bg-orange-50 border border-orange-200 rounded-lg p-2 text-center">
                      <p className="text-lg font-bold text-orange-700">{assessResult.total_findings || 0}</p>
                      <p className="text-[10px] text-orange-600">Findings</p>
                    </div>
                    <div className="bg-slate-50 border border-slate-200 rounded-lg p-2 text-center">
                      <p className="text-lg font-bold text-slate-700">
                        {Object.keys(assessResult.instance_model?.installed_plugins || {}).length}
                      </p>
                      <p className="text-[10px] text-slate-500">Plugins</p>
                    </div>
                  </div>

                  {/* Tab navigation */}
                  <div className="flex space-x-1 mb-4 bg-slate-100 dark:bg-slate-700 rounded-lg p-1">
                    {[
                      { id: 'gap-analysis', label: 'Gap Analysis', icon: BarChart3 },
                      { id: 'as-is', label: 'Current', icon: Eye },
                      { id: 'recommended', label: 'Recommended', icon: Lightbulb },
                      { id: 'findings', label: `Findings (${assessResult.total_findings || 0})`, icon: ClipboardList },
                    ].map(({ id, label, icon: Icon }) => (
                      <button
                        key={id}
                        onClick={() => setAssessTab(id)}
                        className={`flex-1 flex items-center justify-center space-x-1.5 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                          assessTab === id
                            ? 'bg-white dark:bg-slate-600 text-slate-900 dark:text-white shadow-sm'
                            : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
                        }`}
                      >
                        <Icon className="h-3.5 w-3.5" />
                        <span>{label}</span>
                      </button>
                    ))}
                  </div>

                  {/* Gap Analysis tab */}
                  {assessTab === 'gap-analysis' && assessResult.gap_analysis && (
                    <div className="space-y-4">
                      {/* Summary bar */}
                      <div className="bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-700 rounded-lg p-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-4 text-xs">
                            <span className="font-medium text-slate-700 dark:text-slate-300">
                              {assessResult.gap_analysis.summary.streams_covered}/4 streams covered
                            </span>
                            <span className="text-slate-400">|</span>
                            <span className="text-orange-600 font-medium">
                              {assessResult.gap_analysis.summary.total_gaps} value stream gaps
                            </span>
                            <span className="text-slate-400">|</span>
                            <span className="text-red-600 font-medium">
                              {assessResult.gap_analysis.summary.integration_issues} integration issues
                            </span>
                            <span className="text-slate-400">|</span>
                            <span className="text-amber-600 font-medium">
                              {assessResult.gap_analysis.summary.health_issues} health
                            </span>
                            {assessResult.gap_analysis.summary.security_issues > 0 && (<>
                              <span className="text-slate-400">|</span>
                              <span className="text-rose-600 font-medium">
                                {assessResult.gap_analysis.summary.security_issues} security
                              </span>
                            </>)}
                            {assessResult.gap_analysis.summary.efficiency_issues > 0 && (<>
                              <span className="text-slate-400">|</span>
                              <span className="text-slate-600 font-medium">
                                {assessResult.gap_analysis.summary.efficiency_issues} efficiency
                              </span>
                            </>)}
                          </div>
                        </div>
                      </div>

                      {/* Per-stream breakdown */}
                      {assessResult.gap_analysis.streams.map((stream) => (
                        <div key={stream.key} className={`border rounded-lg overflow-hidden ${
                          stream.health === 'healthy' ? 'border-emerald-200' :
                          stream.health === 'gaps' ? 'border-amber-200' :
                          'border-red-200'
                        }`}>
                          <div className={`px-4 py-3 flex items-center justify-between ${
                            stream.health === 'healthy' ? 'bg-emerald-50' :
                            stream.health === 'gaps' ? 'bg-amber-50' :
                            'bg-red-50'
                          }`}>
                            <div className="flex items-center space-x-3">
                              <span className={`text-sm font-bold px-2 py-0.5 rounded ${
                                stream.health === 'healthy' ? 'bg-emerald-100 text-emerald-800' :
                                stream.health === 'gaps' ? 'bg-amber-100 text-amber-800' :
                                'bg-red-100 text-red-800'
                              }`}>{stream.key}</span>
                              <div>
                                <p className="text-xs font-semibold text-slate-800">{stream.label}</p>
                                <p className="text-[10px] text-slate-500">{stream.description}</p>
                              </div>
                            </div>
                            <div className="flex items-center space-x-2">
                              {stream.health === 'healthy' && (
                                <span className="flex items-center space-x-1 text-[10px] font-medium text-emerald-700">
                                  <CheckCircle2 className="h-3.5 w-3.5" />
                                  <span>Healthy</span>
                                </span>
                              )}
                              {stream.health === 'gaps' && (
                                <span className="flex items-center space-x-1 text-[10px] font-medium text-amber-700">
                                  <AlertTriangle className="h-3.5 w-3.5" />
                                  <span>{stream.finding_count} gap{stream.finding_count !== 1 ? 's' : ''}</span>
                                </span>
                              )}
                              {stream.health === 'uncovered' && (
                                <span className="flex items-center space-x-1 text-[10px] font-medium text-red-700">
                                  <AlertTriangle className="h-3.5 w-3.5" />
                                  <span>Uncovered</span>
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="px-4 py-3 bg-white dark:bg-slate-800 space-y-2">
                            {/* Active capabilities */}
                            {stream.active_capabilities.length > 0 && (
                              <div>
                                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-1">Active</p>
                                <div className="flex flex-wrap gap-1">
                                  {stream.active_capabilities.map((cap, j) => (
                                    <span key={j} className="px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-50 border border-emerald-200 text-emerald-700">
                                      {cap}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                            {/* Missing capabilities */}
                            {stream.missing_capabilities.length > 0 && (
                              <div>
                                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-1">Missing</p>
                                <div className="space-y-1">
                                  {stream.missing_capabilities.map((m, j) => (
                                    <div key={j} className="flex items-center space-x-2 text-[10px]">
                                      <ArrowRight className="h-3 w-3 text-amber-500 flex-shrink-0" />
                                      <span className="font-medium text-amber-800">{m.label}</span>
                                      <span className="text-slate-500">— {m.reason}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {/* Findings for this stream */}
                            {stream.findings.length > 0 && (
                              <div>
                                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-1">Rule Findings</p>
                                {stream.findings.map((f, j) => (
                                  <div key={j} className="bg-slate-50 border border-slate-200 rounded p-2 mb-1">
                                    <div className="flex items-center space-x-1.5 mb-0.5">
                                      <span className={`text-[9px] font-bold uppercase px-1 py-0.5 rounded ${
                                        f.severity === 'critical' ? 'bg-red-100 text-red-700' :
                                        f.severity === 'high' ? 'bg-orange-100 text-orange-700' :
                                        f.severity === 'medium' ? 'bg-amber-100 text-amber-700' :
                                        'bg-slate-100 text-slate-600'
                                      }`}>{f.severity}</span>
                                      <span className="text-[10px] font-medium text-slate-700">{f.rule_name}</span>
                                    </div>
                                    <p className="text-[10px] text-slate-600">{f.message}</p>
                                    <p className="text-[10px] text-indigo-600 mt-0.5">{f.recommendation}</p>
                                  </div>
                                ))}
                              </div>
                            )}
                            {stream.active_capabilities.length === 0 && stream.missing_capabilities.length === 0 && stream.findings.length === 0 && (
                              <p className="text-[10px] text-slate-400 italic">No capabilities mapped to this stream.</p>
                            )}
                          </div>
                        </div>
                      ))}

                      {/* Integration section */}
                      {assessResult.gap_analysis.integration.has_issues && (
                        <div className="border border-orange-200 rounded-lg overflow-hidden">
                          <div className="px-4 py-3 bg-orange-50 flex items-center justify-between">
                            <div className="flex items-center space-x-3">
                              <span className="text-sm font-bold px-2 py-0.5 rounded bg-orange-100 text-orange-800">INT</span>
                              <div>
                                <p className="text-xs font-semibold text-slate-800">Integration Patterns</p>
                                <p className="text-[10px] text-slate-500">Pattern selection, error handling, and MID Server configuration.</p>
                              </div>
                            </div>
                            <span className="text-[10px] font-medium text-orange-700">
                              {assessResult.gap_analysis.integration.finding_count} issue{assessResult.gap_analysis.integration.finding_count !== 1 ? 's' : ''}
                            </span>
                          </div>
                          <div className="px-4 py-3 bg-white dark:bg-slate-800 space-y-1">
                            {assessResult.gap_analysis.integration.findings.map((f, i) => (
                              <div key={i} className="bg-slate-50 border border-slate-200 rounded p-2">
                                <div className="flex items-center space-x-1.5 mb-0.5">
                                  <span className={`text-[9px] font-bold uppercase px-1 py-0.5 rounded ${
                                    f.severity === 'critical' ? 'bg-red-100 text-red-700' :
                                    f.severity === 'high' ? 'bg-orange-100 text-orange-700' :
                                    'bg-amber-100 text-amber-700'
                                  }`}>{f.severity}</span>
                                  <span className="text-[10px] font-medium text-slate-700">{f.rule_name}</span>
                                </div>
                                <p className="text-[10px] text-slate-600">{f.message}</p>
                                <p className="text-[10px] text-indigo-600 mt-0.5">{f.recommendation}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Health section */}
                      {assessResult.gap_analysis.health.has_issues && (
                        <div className="border border-amber-200 rounded-lg overflow-hidden">
                          <div className="px-4 py-3 bg-amber-50 flex items-center justify-between">
                            <div className="flex items-center space-x-3">
                              <span className="text-sm font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800">HEALTH</span>
                              <div>
                                <p className="text-xs font-semibold text-slate-800">Architectural Health</p>
                                <p className="text-[10px] text-slate-500">CMDB hygiene, modernization, and platform best practices.</p>
                              </div>
                            </div>
                            <span className="text-[10px] font-medium text-amber-700">
                              {assessResult.gap_analysis.health.finding_count} issue{assessResult.gap_analysis.health.finding_count !== 1 ? 's' : ''}
                            </span>
                          </div>
                          <div className="px-4 py-3 bg-white dark:bg-slate-800 space-y-1">
                            {assessResult.gap_analysis.health.findings.map((f, i) => (
                              <div key={i} className="bg-slate-50 border border-slate-200 rounded p-2">
                                <div className="flex items-center space-x-1.5 mb-0.5">
                                  <span className={`text-[9px] font-bold uppercase px-1 py-0.5 rounded ${
                                    f.severity === 'critical' ? 'bg-red-100 text-red-700' :
                                    f.severity === 'high' ? 'bg-orange-100 text-orange-700' :
                                    'bg-amber-100 text-amber-700'
                                  }`}>{f.severity}</span>
                                  <span className="text-[10px] font-medium text-slate-700">{f.rule_name}</span>
                                </div>
                                <p className="text-[10px] text-slate-600">{f.message}</p>
                                <p className="text-[10px] text-indigo-600 mt-0.5">{f.recommendation}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Security section */}
                      {assessResult.gap_analysis.security?.has_issues && (
                        <div className="border border-rose-200 rounded-lg overflow-hidden">
                          <div className="px-4 py-3 bg-rose-50 flex items-center justify-between">
                            <div className="flex items-center space-x-3">
                              <span className="text-sm font-bold px-2 py-0.5 rounded bg-rose-100 text-rose-800">SEC</span>
                              <div>
                                <p className="text-xs font-semibold text-slate-800">Security Posture</p>
                                <p className="text-[10px] text-slate-500">CSRF protection, audit logging, and SecOps coverage.</p>
                              </div>
                            </div>
                            <span className="text-[10px] font-medium text-rose-700">
                              {assessResult.gap_analysis.security.finding_count} issue{assessResult.gap_analysis.security.finding_count !== 1 ? 's' : ''}
                            </span>
                          </div>
                          <div className="px-4 py-3 bg-white dark:bg-slate-800 space-y-1">
                            {assessResult.gap_analysis.security.findings.map((f, i) => (
                              <div key={i} className="bg-slate-50 border border-slate-200 rounded p-2">
                                <div className="flex items-center space-x-1.5 mb-0.5">
                                  <span className={`text-[9px] font-bold uppercase px-1 py-0.5 rounded ${
                                    f.severity === 'critical' ? 'bg-red-100 text-red-700' :
                                    f.severity === 'high' ? 'bg-orange-100 text-orange-700' :
                                    'bg-amber-100 text-amber-700'
                                  }`}>{f.severity}</span>
                                  <span className="text-[10px] font-medium text-slate-700">{f.rule_name}</span>
                                </div>
                                <p className="text-[10px] text-slate-600">{f.message}</p>
                                <p className="text-[10px] text-indigo-600 mt-0.5">{f.recommendation}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Efficiency section */}
                      {assessResult.gap_analysis.efficiency?.has_issues && (
                        <div className="border border-slate-200 rounded-lg overflow-hidden">
                          <div className="px-4 py-3 bg-slate-50 flex items-center justify-between">
                            <div className="flex items-center space-x-3">
                              <span className="text-sm font-bold px-2 py-0.5 rounded bg-slate-200 text-slate-700">EFF</span>
                              <div>
                                <p className="text-xs font-semibold text-slate-800">Platform Efficiency</p>
                                <p className="text-[10px] text-slate-500">Shelfware detection and automation modernization.</p>
                              </div>
                            </div>
                            <span className="text-[10px] font-medium text-slate-600">
                              {assessResult.gap_analysis.efficiency.finding_count} issue{assessResult.gap_analysis.efficiency.finding_count !== 1 ? 's' : ''}
                            </span>
                          </div>
                          <div className="px-4 py-3 bg-white dark:bg-slate-800 space-y-1">
                            {assessResult.gap_analysis.efficiency.findings.map((f, i) => (
                              <div key={i} className="bg-slate-50 border border-slate-200 rounded p-2">
                                <div className="flex items-center space-x-1.5 mb-0.5">
                                  <span className="text-[9px] font-bold uppercase px-1 py-0.5 rounded bg-slate-100 text-slate-600">{f.severity}</span>
                                  <span className="text-[10px] font-medium text-slate-700">{f.rule_name}</span>
                                </div>
                                <p className="text-[10px] text-slate-600">{f.message}</p>
                                <p className="text-[10px] text-indigo-600 mt-0.5">{f.recommendation}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Architecture diagram tabs */}
                  {(assessTab === 'as-is' || assessTab === 'recommended') && (
                    <div>
                      <div className="flex items-center gap-4 mb-2 text-[10px] text-slate-500">
                        <span className="flex items-center space-x-1">
                          <span className="inline-block w-3 h-3 rounded bg-blue-100 border-2 border-blue-500" />
                          <span>Active</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <span className="inline-block w-3 h-3 rounded bg-emerald-100 border-2 border-emerald-500" />
                          <span>Foundation</span>
                        </span>
                        {assessTab === 'recommended' && assessResult.recommended_node_count > 0 && (
                          <span className="flex items-center space-x-1">
                            <span className="inline-block w-3 h-3 rounded bg-amber-100 border-2 border-amber-500 border-dashed" />
                            <span>Recommended</span>
                          </span>
                        )}
                      </div>
                      <div className="bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 relative group">
                        {/* Toolbar */}
                        <div className="absolute top-2 right-2 z-20 flex items-center space-x-1">
                          <button
                            onClick={() => setZoom(z => Math.min(z + 0.25, 5))}
                            className="p-1.5 rounded-md bg-white/90 dark:bg-slate-700/90 border border-slate-200 dark:border-slate-600 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 transition-all"
                            title="Zoom in"
                          >
                            <ZoomIn className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => setZoom(z => Math.max(z - 0.25, 0.2))}
                            className="p-1.5 rounded-md bg-white/90 dark:bg-slate-700/90 border border-slate-200 dark:border-slate-600 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 transition-all"
                            title="Zoom out"
                          >
                            <ZoomOut className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
                            className="p-1.5 rounded-md bg-white/90 dark:bg-slate-700/90 border border-slate-200 dark:border-slate-600 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 transition-all"
                            title="Reset view"
                          >
                            <Maximize2 className="h-3.5 w-3.5" />
                          </button>
                          <span className="text-[9px] font-mono text-slate-400 px-1">{Math.round(zoom * 100)}%</span>
                          <button
                            onClick={() => {
                              const code = assessTab === 'recommended' && assessResult.recommended_diagram
                                ? assessResult.recommended_diagram
                                : assessResult.as_is_diagram;
                              if (code) downloadMermaid(code, `assessment_${assessTab}_diagram`);
                            }}
                            className="p-1.5 rounded-md bg-white/90 dark:bg-slate-700/90 border border-slate-200 dark:border-slate-600 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 transition-all"
                            title="Download Mermaid syntax"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        {/* Pannable / zoomable viewport */}
                        <div
                          ref={diagramWrapRef}
                          className="overflow-hidden p-4"
                          style={{ cursor: 'grab', minHeight: 600 }}
                          onMouseDown={handleMouseDown}
                          onMouseMove={handleMouseMove}
                          onMouseUp={handleMouseUp}
                          onMouseLeave={handleMouseUp}
                        >
                          <div
                            ref={diagramRef}
                            className="flex justify-center origin-center"
                            style={{
                              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                              transformOrigin: 'center center',
                              transition: isPanning.current ? 'none' : 'transform 0.15s ease-out',
                            }}
                          />
                        </div>
                      </div>
                      {assessTab === 'as-is' && assessResult.active_nodes?.length > 0 && (
                        <div className="mt-3">
                          <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-1.5">Active Components</p>
                          <div className="flex flex-wrap gap-1.5">
                            {assessResult.active_nodes.map((n, i) => (
                              <span key={i} className={`px-2 py-1 rounded text-[10px] font-medium ${
                                n.layer === 'data' ? 'bg-emerald-50 border border-emerald-200 text-emerald-700' :
                                n.layer === 'application' ? 'bg-blue-50 border border-blue-200 text-blue-700' :
                                n.layer === 'ui' ? 'bg-indigo-50 border border-indigo-200 text-indigo-700' :
                                n.layer === 'orchestration' ? 'bg-amber-50 border border-amber-200 text-amber-700' :
                                n.layer === 'platform' ? 'bg-orange-50 border border-orange-200 text-orange-700' :
                                'bg-slate-50 border border-slate-200 text-slate-600'
                              }`} title={n.evidence}>
                                {n.label}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {assessTab === 'recommended' && assessResult.recommended_nodes?.length > 0 && (
                        <div className="mt-3">
                          <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-1.5">Recommended Additions</p>
                          <div className="space-y-1.5">
                            {assessResult.recommended_nodes.map((n, i) => (
                              <div key={i} className="flex items-center space-x-2 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
                                <Lightbulb className="h-3 w-3 text-amber-500 flex-shrink-0" />
                                <span className="text-[10px] font-medium text-amber-800">{n.label}</span>
                                <span className="text-[9px] text-amber-600">— {n.reason}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Findings tab */}
                  {assessTab === 'findings' && (
                    <div className="space-y-2">
                      {assessResult.findings?.length > 0 ? (
                        assessResult.findings.map((f, i) => (
                          <div key={i} className={`p-3 rounded-lg border ${
                            f.severity === 'critical' ? 'bg-red-50 border-red-200' :
                            f.severity === 'high' ? 'bg-orange-50 border-orange-200' :
                            f.severity === 'medium' ? 'bg-amber-50 border-amber-200' :
                            'bg-slate-50 border-slate-200'
                          }`}>
                            <div className="flex items-center space-x-2 mb-1">
                              <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                                f.severity === 'critical' ? 'bg-red-100 text-red-700' :
                                f.severity === 'high' ? 'bg-orange-100 text-orange-700' :
                                f.severity === 'medium' ? 'bg-amber-100 text-amber-700' :
                                'bg-slate-100 text-slate-600'
                              }`}>{f.severity}</span>
                              <span className="text-[10px] text-slate-400">{f.source}</span>
                            </div>
                            <p className="text-xs font-medium text-slate-700 mb-0.5">{f.rule_name}</p>
                            <p className="text-xs text-slate-600">{f.message}</p>
                            <p className="text-xs text-indigo-600 mt-1">{f.recommendation}</p>
                          </div>
                        ))
                      ) : (
                        <div className="text-center py-6">
                          <CheckCircle2 className="h-8 w-8 text-emerald-400 mx-auto mb-2" />
                          <p className="text-sm font-medium text-emerald-700">No findings</p>
                          <p className="text-xs text-slate-500">Instance architecture looks healthy.</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Assessment completed but disabled */}
              {assessResult && assessResult.status === 'disabled' && (
                <div className="bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-700 rounded-lg p-4 mb-4">
                  <div className="flex items-start space-x-3">
                    <Info className="h-5 w-5 text-slate-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Scanner infrastructure verified</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                        Instance connection is working and scan queries are ready. Rule evaluation
                        will produce findings once the knowledge source approvals are received.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Knowledge Base */}
              {knowledgeBase && (
                <div className="mt-1 pt-3 border-t border-slate-100 dark:border-slate-700">
                  <div className="flex items-center justify-between">
                    <button
                      onClick={() => setRulesExpanded(!rulesExpanded)}
                      className="flex items-center space-x-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
                    >
                      <BookOpen className="h-3.5 w-3.5" />
                      {rulesExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      <span>Rule Knowledge Base ({ruleSummary?.total_rules || 33} rules from {knowledgeBase.length} sources)</span>
                    </button>
                    {rulesExpanded && (
                      <button
                        onClick={() => setWriteMode(!writeMode)}
                        className={`flex items-center space-x-1 px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                          writeMode
                            ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400'
                            : 'bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-400 dark:hover:bg-slate-600'
                        }`}
                      >
                        <Pencil className="h-3 w-3" />
                        <span>{writeMode ? 'Exit Editor' : 'Edit Rules'}</span>
                      </button>
                    )}
                  </div>
                  {rulesExpanded && writeMode && (
                    <div className="mt-3">
                      <RuleEditor
                        onClose={() => setWriteMode(false)}
                        onSaved={() => { loadRuleSummary(); loadKnowledgeBase(); }}
                      />
                    </div>
                  )}
                  {rulesExpanded && !writeMode && (
                    <div className="mt-3 space-y-3">
                      {knowledgeBase.map((source) => (
                        <div key={source.id} className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
                          <button
                            onClick={() => setKbExpanded(kbExpanded === source.id ? null : source.id)}
                            className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-700/50 flex items-center justify-between hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-left"
                          >
                            <div className="flex items-center space-x-3">
                              <div className={`p-1.5 rounded ${
                                source.id === 'ian_leu' ? 'bg-blue-100' :
                                source.id === 'jochen_geist' ? 'bg-orange-100' :
                                'bg-emerald-100'
                              }`}>
                                <BookOpen className={`h-4 w-4 ${
                                  source.id === 'ian_leu' ? 'text-blue-600' :
                                  source.id === 'jochen_geist' ? 'text-orange-600' :
                                  'text-emerald-600'
                                }`} />
                              </div>
                              <div>
                                <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">{source.title}</p>
                                <p className="text-[10px] text-slate-500 dark:text-slate-400">{source.author} · {source.rule_count} rules</p>
                              </div>
                            </div>
                            {kbExpanded === source.id
                              ? <ChevronDown className="h-4 w-4 text-slate-400" />
                              : <ChevronRight className="h-4 w-4 text-slate-400" />
                            }
                          </button>
                          {kbExpanded === source.id && (
                            <div className="px-4 py-3 space-y-3">
                              <p className="text-xs text-slate-600 dark:text-slate-400">{source.description}</p>
                              <div>
                                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-1.5">Focus Areas</p>
                                <div className="grid grid-cols-2 gap-2">
                                  {source.focus_areas.map((fa) => (
                                    <div key={fa.key} className="bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-700 rounded p-2">
                                      <p className="text-[10px] font-semibold text-slate-700 dark:text-slate-300">{fa.label}</p>
                                      <p className="text-[9px] text-slate-500 dark:text-slate-400 leading-tight mt-0.5">{fa.description}</p>
                                    </div>
                                  ))}
                                </div>
                              </div>
                              <div>
                                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-1.5">Key Principles</p>
                                <div className="space-y-1">
                                  {source.key_principles.map((p, i) => (
                                    <div key={i} className="flex items-start space-x-1.5">
                                      <span className="text-indigo-500 mt-0.5 text-[10px]">•</span>
                                      <p className="text-[10px] text-slate-600 dark:text-slate-400">{p}</p>
                                    </div>
                                  ))}
                                </div>
                              </div>
                              {/* Individual Rules with Execution Details */}
                              <div>
                                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-1.5">Rules ({source.rules.length})</p>
                                <div className="space-y-1">
                                  {source.rules.map((rule) => (
                                    <div key={rule.id} className="border border-slate-200 dark:border-slate-600 rounded overflow-hidden">
                                      <button
                                        onClick={() => setRuleExpanded(ruleExpanded === rule.id ? null : rule.id)}
                                        className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
                                      >
                                        <div className="flex items-center space-x-2">
                                          <span className={`inline-block w-1.5 h-1.5 rounded-full ${
                                            rule.severity === 'critical' ? 'bg-red-500' :
                                            rule.severity === 'high' ? 'bg-orange-500' :
                                            rule.severity === 'medium' ? 'bg-yellow-500' : 'bg-slate-400'
                                          }`} />
                                          <span className="text-[10px] font-mono text-slate-400">{rule.id}</span>
                                          <span className="text-[10px] font-medium text-slate-700 dark:text-slate-300">{rule.name}</span>
                                        </div>
                                        {ruleExpanded === rule.id
                                          ? <ChevronDown className="h-3 w-3 text-slate-400 flex-shrink-0" />
                                          : <ChevronRight className="h-3 w-3 text-slate-400 flex-shrink-0" />
                                        }
                                      </button>
                                      {ruleExpanded === rule.id && (
                                        <div className="px-3 py-2 bg-slate-50 dark:bg-slate-700/30 border-t border-slate-200 dark:border-slate-600 space-y-2">
                                          <p className="text-[10px] text-slate-600 dark:text-slate-400">{rule.description}</p>
                                          {rule.eval && (
                                            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded p-2 space-y-1.5">
                                              <p className="text-[9px] font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">Execution Logic</p>
                                              <div className="space-y-0.5">
                                                {renderEvalBlock(rule.eval, 0)}
                                              </div>
                                            </div>
                                          )}
                                          <div className="flex flex-wrap gap-1">
                                            {rule.tags.map((tag) => (
                                              <span key={tag} className="text-[8px] bg-slate-200 dark:bg-slate-600 text-slate-600 dark:text-slate-300 px-1.5 py-0.5 rounded">{tag}</span>
                                            ))}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default InstanceInfo;
