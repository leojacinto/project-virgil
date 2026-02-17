import React, { useState, useEffect, useCallback } from 'react';
import { Upload, File, Trash2, Loader2, CheckCircle, AlertCircle, BookOpen, FileText } from 'lucide-react';
import axios from 'axios';
import { useDropzone } from 'react-dropzone';

const STORES = {
  servicenow_assets: {
    label: 'ServiceNow Assets',
    icon: BookOpen,
    color: 'purple',
    description: 'Reference architecture diagrams, best practice guides, capability matrices, and platform documentation. These assets provide authoritative ServiceNow architectural context shared across all customer engagements.',
    emptyText: 'No ServiceNow assets uploaded yet',
    emptyHint: 'Upload reference architectures, best practice guides, or platform documentation'
  },
  customer_documents: {
    label: 'Customer Documents',
    icon: FileText,
    color: 'blue',
    description: 'Customer-specific documents such as RFPs, SOWs, pricing sheets, technical specifications, and requirements. These are unique to each engagement and provide customer context.',
    emptyText: 'No customer documents uploaded yet',
    emptyHint: 'Upload RFPs, pricing docs, technical specs, or requirements'
  }
};

function DocumentUpload() {
  const [activeStore, setActiveStore] = useState('servicenow_assets');
  const [documents, setDocuments] = useState({ servicenow_assets: [], customer_documents: [] });
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const [snResponse, custResponse] = await Promise.all([
        axios.get('/api/documents?store=servicenow_assets'),
        axios.get('/api/documents?store=customer_documents')
      ]);
      setDocuments({
        servicenow_assets: snResponse.data.documents,
        customer_documents: custResponse.data.documents
      });
    } catch (error) {
      console.error('Error loading documents:', error);
    }
  };

  const onDrop = useCallback(async (acceptedFiles) => {
    setUploading(true);
    setUploadStatus(null);

    for (const file of acceptedFiles) {
      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('store', activeStore);

        await axios.post('/api/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });

        setUploadStatus({
          success: true,
          message: `${file.name} uploaded to ${STORES[activeStore].label}`
        });
      } catch (error) {
        setUploadStatus({
          success: false,
          message: error.response?.data?.detail || `Failed to upload ${file.name}`
        });
      }
    }

    setUploading(false);
    loadDocuments();
  }, [activeStore]);

  const dropzone = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'text/plain': ['.txt'],
      'text/csv': ['.csv']
    },
    multiple: true
  });

  const handleDelete = async (fileId) => {
    if (!window.confirm('Are you sure you want to delete this document?')) return;

    try {
      await axios.delete(`/api/documents/${fileId}`);
      loadDocuments();
      setUploadStatus({ success: true, message: 'Document deleted successfully' });
    } catch (error) {
      setUploadStatus({ success: false, message: 'Failed to delete document' });
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const storeCfg = STORES[activeStore];
  const StoreIcon = storeCfg.icon;
  const storeDocs = documents[activeStore] || [];
  const snCount = documents.servicenow_assets?.length || 0;
  const custCount = documents.customer_documents?.length || 0;

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-1">Document Stores</h3>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
          Two separate stores provide context during architecture analysis. <strong>ServiceNow Assets</strong> contain
          platform reference material shared across engagements. <strong>Customer Documents</strong> hold
          engagement-specific materials like RFPs and technical specs. Both stores are searched during analysis,
          with results tagged by source so the AI distinguishes authoritative guidance from customer requirements.
        </p>
      </div>

      <div className="flex border-b border-slate-200 dark:border-slate-700">
        {Object.entries(STORES).map(([key, cfg]) => {
          const Icon = cfg.icon;
          const count = key === 'servicenow_assets' ? snCount : custCount;
          const isActive = activeStore === key;
          return (
            <button
              key={key}
              onClick={() => { setActiveStore(key); setUploadStatus(null); }}
              className={`flex items-center space-x-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                isActive
                  ? `border-${cfg.color}-600 text-${cfg.color}-700`
                  : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{cfg.label}</span>
              {count > 0 && (
                <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                  isActive ? `bg-${cfg.color}-100 text-${cfg.color}-700` : 'bg-slate-100 text-slate-600'
                }`}>{count}</span>
              )}
            </button>
          );
        })}
      </div>

      <div className={`p-4 rounded-lg border ${
        storeCfg.color === 'purple' ? 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800' : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
      }`}>
        <p className={`text-sm ${storeCfg.color === 'purple' ? 'text-purple-800 dark:text-purple-300' : 'text-blue-800 dark:text-blue-300'}`}>
          {storeCfg.description}
        </p>
      </div>

      <div
        {...dropzone.getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          dropzone.isDragActive
            ? `border-${storeCfg.color}-500 bg-${storeCfg.color}-50`
            : 'border-slate-300 dark:border-slate-600 hover:border-primary-400 hover:bg-slate-50 dark:hover:bg-slate-700'
        }`}
      >
        <input {...dropzone.getInputProps()} />
        <div className="flex flex-col items-center space-y-3">
          <div className={`p-3 rounded-full ${
            storeCfg.color === 'purple' ? 'bg-purple-100' : 'bg-blue-100'
          }`}>
            <Upload className={`h-8 w-8 ${
              storeCfg.color === 'purple' ? 'text-purple-600' : 'text-blue-600'
            }`} />
          </div>
          {dropzone.isDragActive ? (
            <p className="text-primary-600 font-medium">Drop files here...</p>
          ) : (
            <>
              <p className="text-slate-700 dark:text-slate-300 font-medium">
                Drag & drop files to <span className="font-semibold">{storeCfg.label}</span>
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Supported: PDF, DOCX, XLSX, TXT, CSV (Max 50MB)
              </p>
            </>
          )}
        </div>
      </div>

      {uploading && (
        <div className="flex items-center justify-center space-x-2 text-primary-600">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm font-medium">Uploading and processing...</span>
        </div>
      )}

      {uploadStatus && (
        <div className={`flex items-start space-x-3 p-4 rounded-lg ${
          uploadStatus.success ? 'bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800'
        }`}>
          {uploadStatus.success
            ? <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
            : <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />}
          <p className={`text-sm ${uploadStatus.success ? 'text-green-800 dark:text-green-300' : 'text-red-800 dark:text-red-300'}`}>
            {uploadStatus.message}
          </p>
        </div>
      )}

      <div>
        <h4 className="text-md font-semibold text-slate-900 dark:text-white mb-3">
          {storeCfg.label} ({storeDocs.length})
        </h4>

        {storeDocs.length === 0 ? (
          <div className="text-center py-12 bg-slate-50 dark:bg-slate-700/50 rounded-lg border border-slate-200 dark:border-slate-700">
            <StoreIcon className="h-12 w-12 text-slate-400 mx-auto mb-3" />
            <p className="text-slate-600 dark:text-slate-400">{storeCfg.emptyText}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{storeCfg.emptyHint}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {storeDocs.map((doc) => (
              <div
                key={doc.file_id}
                className="flex items-center justify-between p-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg hover:shadow-sm transition-shadow"
              >
                <div className="flex items-center space-x-3 flex-1">
                  <div className={`p-2 rounded ${
                    storeCfg.color === 'purple' ? 'bg-purple-100' : 'bg-blue-100'
                  }`}>
                    <File className={`h-5 w-5 ${
                      storeCfg.color === 'purple' ? 'text-purple-600' : 'text-blue-600'
                    }`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{doc.filename}</p>
                    <div className="flex items-center space-x-4 mt-1">
                      <p className="text-xs text-slate-500 dark:text-slate-400">{doc.chunks} chunks</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{formatFileSize(doc.content_length)}</p>
                      {!doc.exists && (
                        <span className="text-xs text-amber-600 font-medium">File missing</span>
                      )}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(doc.file_id)}
                  className="ml-4 p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  title="Delete document"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default DocumentUpload;
