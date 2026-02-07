import React, { useState, useEffect } from 'react';
import { Database, Package, Workflow, Loader2, RefreshCw } from 'lucide-react';
import axios from 'axios';

function InstanceInfo() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState({
    tables: [],
    applications: [],
    components: {}
  });

  useEffect(() => {
    loadInstanceData();
  }, []);

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
        </>
      )}
    </div>
  );
}

export default InstanceInfo;
