import React, { useState, useEffect, useCallback } from 'react';
import { Upload, File, Trash2, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import axios from 'axios';
import { useDropzone } from 'react-dropzone';

function DocumentUpload() {
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const response = await axios.get('/api/documents');
      setDocuments(response.data.documents);
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

        await axios.post('/api/upload', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        });

        setUploadStatus({
          success: true,
          message: `${file.name} uploaded successfully`
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
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
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
    if (!window.confirm('Are you sure you want to delete this document?')) {
      return;
    }

    try {
      await axios.delete(`/api/documents/${fileId}`);
      loadDocuments();
      setUploadStatus({
        success: true,
        message: 'Document deleted successfully'
      });
    } catch (error) {
      setUploadStatus({
        success: false,
        message: 'Failed to delete document'
      });
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-slate-900 mb-2">
          Upload Reference Documents
        </h3>
        <p className="text-sm text-slate-600 mb-4">
          Upload pricing documents, technical specifications, or reference materials to enhance architecture recommendations.
        </p>

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-primary-500 bg-primary-50'
              : 'border-slate-300 hover:border-primary-400 hover:bg-slate-50'
          }`}
        >
          <input {...getInputProps()} />
          <div className="flex flex-col items-center space-y-3">
            <div className="bg-primary-100 p-3 rounded-full">
              <Upload className="h-8 w-8 text-primary-600" />
            </div>
            {isDragActive ? (
              <p className="text-primary-600 font-medium">Drop files here...</p>
            ) : (
              <>
                <p className="text-slate-700 font-medium">
                  Drag & drop files here, or click to select
                </p>
                <p className="text-sm text-slate-500">
                  Supported: PDF, DOCX, XLSX, TXT, CSV (Max 50MB)
                </p>
              </>
            )}
          </div>
        </div>

        {uploading && (
          <div className="mt-4 flex items-center justify-center space-x-2 text-primary-600">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-sm font-medium">Uploading and processing...</span>
          </div>
        )}

        {uploadStatus && (
          <div
            className={`mt-4 flex items-start space-x-3 p-4 rounded-lg ${
              uploadStatus.success
                ? 'bg-green-50 border border-green-200'
                : 'bg-red-50 border border-red-200'
            }`}
          >
            {uploadStatus.success ? (
              <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            )}
            <p
              className={`text-sm ${
                uploadStatus.success ? 'text-green-800' : 'text-red-800'
              }`}
            >
              {uploadStatus.message}
            </p>
          </div>
        )}
      </div>

      <div>
        <h4 className="text-md font-semibold text-slate-900 mb-3">
          Uploaded Documents ({documents.length})
        </h4>

        {documents.length === 0 ? (
          <div className="text-center py-12 bg-slate-50 rounded-lg border border-slate-200">
            <File className="h-12 w-12 text-slate-400 mx-auto mb-3" />
            <p className="text-slate-600">No documents uploaded yet</p>
            <p className="text-sm text-slate-500 mt-1">
              Upload documents to provide additional context for architecture analysis
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {documents.map((doc) => (
              <div
                key={doc.file_id}
                className="flex items-center justify-between p-4 bg-white border border-slate-200 rounded-lg hover:shadow-sm transition-shadow"
              >
                <div className="flex items-center space-x-3 flex-1">
                  <div className="bg-primary-100 p-2 rounded">
                    <File className="h-5 w-5 text-primary-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">
                      {doc.filename}
                    </p>
                    <div className="flex items-center space-x-4 mt-1">
                      <p className="text-xs text-slate-500">
                        {doc.chunks} chunks
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatFileSize(doc.content_length)}
                      </p>
                      {!doc.exists && (
                        <span className="text-xs text-amber-600 font-medium">
                          File missing
                        </span>
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
