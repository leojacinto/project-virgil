import React, { useState, useEffect } from 'react';
import { Database, Package, Workflow, Loader2, RefreshCw, Search, Lock, Shield, GitBranch, AlertTriangle, ChevronDown, ChevronRight, CheckCircle2, Info } from 'lucide-react';
import axios from 'axios';

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

  useEffect(() => {
    loadInstanceData();
    loadRuleSummary();
  }, []);

  const loadRuleSummary = async () => {
    try {
      const res = await axios.get('/api/assess/rules');
      setRuleSummary(res.data.summary);
    } catch (err) {
      // Non-critical — just won't show rule preview
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

      setData({
        tables: tablesRes.data.tables || [],
        applications: summaryRes.data.applications || [],
        components: componentsRes.data.components || {},
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
    <div className="bg-white border border-slate-200 rounded-lg p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-600 mb-1">{title}</p>
          <p className="text-3xl font-bold text-slate-900">{count}</p>
        </div>
        <div className={`p-3 rounded-lg ${color}`}>
          <Icon className="h-8 w-8 text-white" />
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-900">
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
              count={data.tables.length}
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
              count={data.components.workflows?.length || 0}
              color="bg-purple-600"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white border border-slate-200 rounded-lg p-6">
              <h4 className="font-semibold text-slate-900 mb-4 flex items-center space-x-2">
                <Database className="h-5 w-5 text-blue-600" />
                <span>Recent Tables</span>
              </h4>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {data.tables.slice(0, 20).map((table, index) => (
                  <div
                    key={index}
                    className="px-3 py-2 bg-slate-50 rounded text-sm text-slate-700 font-mono"
                  >
                    {table}
                  </div>
                ))}
                {data.tables.length > 20 && (
                  <p className="text-xs text-slate-500 text-center pt-2">
                    ... and {data.tables.length - 20} more tables
                  </p>
                )}
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-lg p-6">
              <h4 className="font-semibold text-slate-900 mb-4 flex items-center space-x-2">
                <Package className="h-5 w-5 text-green-600" />
                <span>Installed Applications</span>
              </h4>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {data.applications.slice(0, 10).map((app, index) => (
                  <div
                    key={index}
                    className="p-3 bg-slate-50 rounded border border-slate-200"
                  >
                    <p className="text-sm font-medium text-slate-900">{app.name}</p>
                    <div className="flex items-center space-x-3 mt-1">
                      {app.version && (
                        <span className="text-xs text-slate-600">v{app.version}</span>
                      )}
                      {app.scope && (
                        <span className="text-xs text-slate-600 font-mono">{app.scope}</span>
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

          <div className="bg-white border border-slate-200 rounded-lg p-6">
            <h4 className="font-semibold text-slate-900 mb-4 flex items-center space-x-2">
              <Workflow className="h-5 w-5 text-purple-600" />
              <span>Components Summary</span>
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(data.components).map(([key, value]) => (
                <div key={key} className="bg-slate-50 p-4 rounded-lg">
                  <p className="text-xs text-slate-600 mb-1">
                    {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </p>
                  <p className="text-2xl font-bold text-slate-900">
                    {Array.isArray(value) ? value.length : 0}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* ============================================================ */}
          {/* Instance Assessment (Nirvana) */}
          {/* ============================================================ */}
          <div className="bg-white border-2 border-slate-200 rounded-xl overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-indigo-100">
                    <Search className="h-5 w-5 text-indigo-600" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-slate-900 flex items-center space-x-2">
                      <span>Instance Assessment</span>
                      <span className="text-[10px] font-medium text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded">Nirvana</span>
                    </h4>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Deterministic analysis against {ruleSummary?.total_rules || 33} rules. No LLM required.
                    </p>
                  </div>
                </div>
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

              {/* Assessment results (when enabled and run) */}
              {assessResult && assessResult.status === 'completed' && assessResult.findings?.length > 0 && (
                <div className="space-y-3 mb-4">
                  {assessResult.findings.map((f, i) => (
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
                        <span className="text-xs font-medium text-slate-700">{f.rule_name}</span>
                      </div>
                      <p className="text-xs text-slate-600">{f.message}</p>
                      <p className="text-xs text-indigo-600 mt-1">{f.recommendation}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Assessment completed but disabled */}
              {assessResult && assessResult.status === 'disabled' && (
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-4">
                  <div className="flex items-start space-x-3">
                    <Info className="h-5 w-5 text-slate-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-slate-700">Scanner infrastructure verified</p>
                      <p className="text-xs text-slate-500 mt-1">
                        Instance connection is working and scan queries are ready. Rule evaluation
                        will produce findings once the knowledge source approvals are received.
                      </p>
                      {assessResult.instance_model && (
                        <div className="mt-3 grid grid-cols-2 gap-2">
                          <div className="bg-white p-2 rounded border border-slate-200">
                            <p className="text-[10px] text-slate-500">Plugins Detected</p>
                            <p className="text-sm font-semibold text-slate-800">
                              {Object.keys(assessResult.instance_model.installed_plugins || {}).length}
                            </p>
                          </div>
                          <div className="bg-white p-2 rounded border border-slate-200">
                            <p className="text-[10px] text-slate-500">Integration Flows</p>
                            <p className="text-sm font-semibold text-slate-800">
                              {assessResult.instance_model.integration_flows_count || 0}
                            </p>
                          </div>
                          <div className="bg-white p-2 rounded border border-slate-200">
                            <p className="text-[10px] text-slate-500">CMDB CIs</p>
                            <p className="text-sm font-semibold text-slate-800">
                              {assessResult.instance_model.cmdb_stats?.total_cis?.toLocaleString() || 0}
                            </p>
                          </div>
                          <div className="bg-white p-2 rounded border border-slate-200">
                            <p className="text-[10px] text-slate-500">MID Servers</p>
                            <p className="text-sm font-semibold text-slate-800">
                              {assessResult.instance_model.mid_servers?.length || 0}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Rule catalog preview */}
              {ruleSummary && (
                <div>
                  <button
                    onClick={() => setRulesExpanded(!rulesExpanded)}
                    className="flex items-center space-x-1 text-xs text-slate-500 hover:text-slate-700 transition-colors"
                  >
                    {rulesExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                    <span>Rule catalog ({ruleSummary.total_rules} rules)</span>
                  </button>
                  {rulesExpanded && (
                    <div className="mt-3 space-y-3">
                      <div className="grid grid-cols-3 gap-3">
                        {Object.entries(ruleSummary.by_source || {}).map(([source, count]) => (
                          <div key={source} className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                            <p className="text-xs text-slate-500">{source}</p>
                            <p className="text-lg font-bold text-slate-800">{count}</p>
                            <p className="text-[10px] text-slate-400">rules</p>
                          </div>
                        ))}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(ruleSummary.by_severity || {}).map(([severity, count]) => count > 0 && (
                          <span key={severity} className={`text-[10px] font-medium px-2 py-1 rounded-full ${
                            severity === 'critical' ? 'bg-red-100 text-red-700' :
                            severity === 'high' ? 'bg-orange-100 text-orange-700' :
                            severity === 'medium' ? 'bg-amber-100 text-amber-700' :
                            severity === 'low' ? 'bg-slate-100 text-slate-600' :
                            'bg-blue-100 text-blue-600'
                          }`}>
                            {count} {severity}
                          </span>
                        ))}
                      </div>
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
