import React, { useState } from 'react';
import { Database, Loader2, AlertCircle, CheckCircle, Wifi, Server } from 'lucide-react';

function ConnectionPanel({ onConnect, loading }) {
  const [formData, setFormData] = useState({
    instance: '',
    username: '',
    password: '',
    jdbc_path: '',
    connection_mode: 'rest_only'
  });
  const [message, setMessage] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage(null);
    
    const result = await onConnect(formData);
    setMessage(result);
    
    if (result.success) {
      setFormData({ instance: '', username: '', password: '', jdbc_path: '', connection_mode: 'rest_only' });
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="bg-white rounded-lg shadow-lg border border-slate-200 p-8">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-100 rounded-full mb-4">
          <Database className="h-8 w-8 text-primary-600" />
        </div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">
          Connect to ServiceNow
        </h2>
        <p className="text-slate-600">
          Enter your ServiceNow instance credentials to begin
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-3">
            Connection Mode
          </label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setFormData({ ...formData, connection_mode: 'rest_only' })}
              className={`p-4 border-2 rounded-lg text-left transition-all ${
                formData.connection_mode === 'rest_only'
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center space-x-2 mb-1">
                <Wifi className="h-4 w-4 text-blue-600" />
                <span className="font-semibold text-slate-900">REST API Only</span>
              </div>
              <p className="text-xs text-slate-500">No JDBC driver or Java required. Works with any ServiceNow instance.</p>
            </button>
            <button
              type="button"
              onClick={() => setFormData({ ...formData, connection_mode: 'rest_and_jdbc' })}
              className={`p-4 border-2 rounded-lg text-left transition-all ${
                formData.connection_mode === 'rest_and_jdbc'
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center space-x-2 mb-1">
                <Server className="h-4 w-4 text-blue-600" />
                <span className="font-semibold text-slate-900">REST API + JDBC</span>
              </div>
              <p className="text-xs text-slate-500">Full access with RaptorDB. Requires JDBC driver and Java.</p>
            </button>
          </div>
        </div>

        <div>
          <label htmlFor="instance" className="block text-sm font-medium text-slate-700 mb-2">
            Instance Name
          </label>
          <input
            type="text"
            id="instance"
            name="instance"
            value={formData.instance}
            onChange={handleChange}
            placeholder="your-instance"
            required
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all"
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
            name="username"
            value={formData.username}
            onChange={handleChange}
            placeholder="admin"
            required
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all"
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-2">
            Password
          </label>
          <input
            type="password"
            id="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            placeholder="••••••••"
            required
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all"
          />
        </div>

        {formData.connection_mode === 'rest_and_jdbc' && (
          <div>
            <label htmlFor="jdbc_path" className="block text-sm font-medium text-slate-700 mb-2">
              JDBC JAR Path (Optional)
            </label>
            <input
              type="text"
              id="jdbc_path"
              name="jdbc_path"
              value={formData.jdbc_path}
              onChange={handleChange}
              placeholder="./jdbc/servicenow-jdbc.jar"
              className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all"
            />
            <p className="mt-1 text-xs text-slate-500">
              Leave empty to use default path
            </p>
          </div>
        )}

        {message && (
          <div
            className={`flex items-start space-x-3 p-4 rounded-lg ${
              message.success
                ? 'bg-green-50 border border-green-200'
                : 'bg-red-50 border border-red-200'
            }`}
          >
            {message.success ? (
              <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            )}
            <p
              className={`text-sm ${
                message.success ? 'text-green-800' : 'text-red-800'
              }`}
            >
              {message.message}
            </p>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-primary-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
        >
          {loading ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Connecting...</span>
            </>
          ) : (
            <>
              <Database className="h-5 w-5" />
              <span>Connect to ServiceNow</span>
            </>
          )}
        </button>
      </form>

      {formData.connection_mode === 'rest_and_jdbc' && (
        <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-800">
            <strong>Note:</strong> Make sure the ServiceNow JDBC driver JAR file is placed in the backend/jdbc directory before connecting.
          </p>
        </div>
      )}
    </div>
  );
}

export default ConnectionPanel;
