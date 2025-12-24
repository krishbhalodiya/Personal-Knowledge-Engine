import React, { useEffect, useState } from 'react';
import { Upload, RefreshCw, Trash2, File, Mail, FileText, Loader2, HardDrive, AlertCircle, Image } from 'lucide-react';
import client from '../api/client';
import type { Document, GoogleAuthStatus } from '../types/index.js';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  
  // Auth status
  const [gmailAuth, setGmailAuth] = useState<GoogleAuthStatus | null>(null);
  const [driveAuth, setDriveAuth] = useState<GoogleAuthStatus | null>(null);

  const fetchDocuments = async () => {
    try {
      const res = await client.get('/documents');
      setDocuments(res.data.documents);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const checkAuth = async () => {
    try {
      const [gRes, dRes] = await Promise.all([
        client.get('/gmail/auth/status'),
        client.get('/drive/auth/status')
      ]);
      setGmailAuth(gRes.data);
      setDriveAuth(dRes.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchDocuments();
    checkAuth();
  }, []);

  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  const handleSync = async (source: 'gmail' | 'drive') => {
    setSyncing(source);
    setSyncError(null);
    setSyncMessage(null);
    
    try {
      // Gmail: Use primary filter to skip promotions, also skip promotional patterns
      // Drive: Just limit results
      const payload = source === 'gmail' 
        ? { 
            max_results: 20,
            filter_type: 'primary',  // Only primary inbox
            skip_promotional: true   // Also skip promotional-looking emails
          } 
        : { limit: 10 };
      
      const res = await client.post(`/${source}/sync`, payload);
      
      // Show sync stats
      if (res.data.skipped > 0) {
        setSyncMessage(`Synced ${res.data.processed} emails (${res.data.skipped} promotional skipped)`);
      } else {
        setSyncMessage(`Synced ${res.data.processed} items`);
      }
      
      await fetchDocuments();
    } catch (err: any) {
      console.error(err);
      const errorDetail = err.response?.data?.detail || err.message;
      
      // Check if it's an auth error
      if (err.response?.status === 401 || err.response?.status === 500) {
        setSyncError(`${source === 'gmail' ? 'Gmail' : 'Drive'} sync failed. Your Google authorization may have expired. Please reconnect your Google account.`);
        // Reset auth status to show connect button
        if (source === 'gmail') {
          setGmailAuth({ authenticated: false });
        } else {
          setDriveAuth({ authenticated: false });
        }
      } else {
        setSyncError(`Failed to sync ${source}: ${errorDetail}`);
      }
    } finally {
      setSyncing(null);
    }
  };

  const handleConnect = async () => {
    try {
      const res = await client.get('/auth/google/url');
      window.location.href = res.data.url;
    } catch (err) {
      console.error(err);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    
    setUploading(true);
    const formData = new FormData();
    formData.append('file', e.target.files[0]);

    try {
      await client.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      await fetchDocuments();
    } catch (err) {
      console.error(err);
      alert('Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure?')) return;
    try {
      await client.delete(`/documents/${id}`);
      setDocuments(docs => docs.filter(d => d.id !== id));
    } catch (err) {
      console.error(err);
    }
  };

  const getIcon = (type: string) => {
    if (type === 'email') return Mail;
    if (type === 'pdf') return FileText;
    if (type === 'image') return Image;
    return File;
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Documents</h1>
          <p className="text-gray-500">Manage your knowledge base</p>
        </div>
        
        {/* Actions */}
        <div className="flex gap-3">
          <label className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg cursor-pointer hover:bg-blue-700 transition-colors">
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            <span>Upload File</span>
            <input 
              type="file" 
              className="hidden" 
              onChange={handleUpload} 
              disabled={uploading}
              accept=".pdf,.docx,.doc,.md,.markdown,.txt,.text,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.tif,.webp"
            />
          </label>
        </div>
      </div>

      {/* Sync Messages */}
      {syncError && (
        <div className="flex items-center gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-800">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm">{syncError}</p>
          </div>
          <button 
            onClick={() => setSyncError(null)}
            className="text-amber-600 hover:text-amber-800 text-sm font-medium"
          >
            Dismiss
          </button>
        </div>
      )}
      
      {syncMessage && !syncError && (
        <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-xl text-green-800">
          <RefreshCw className="w-5 h-5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm">{syncMessage}</p>
          </div>
          <button 
            onClick={() => setSyncMessage(null)}
            className="text-green-600 hover:text-green-800 text-sm font-medium"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Sync Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Gmail Card */}
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-50 text-red-600 rounded-lg">
                <Mail className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">Gmail</h3>
                <p className="text-xs text-gray-500">
                  {gmailAuth?.authenticated ? 'Connected' : 'Not Connected'}
                </p>
              </div>
            </div>
            {gmailAuth?.authenticated ? (
              <button 
                onClick={() => handleSync('gmail')}
                disabled={!!syncing}
                className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg disabled:opacity-50"
              >
                <RefreshCw className={`w-5 h-5 ${syncing === 'gmail' ? 'animate-spin' : ''}`} />
              </button>
            ) : (
              <button 
                onClick={handleConnect}
                className="px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100"
              >
                Connect
              </button>
            )}
          </div>
        </div>

        {/* Drive Card */}
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
                <HardDrive className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">Google Drive</h3>
                <p className="text-xs text-gray-500">
                  {driveAuth?.authenticated ? 'Connected' : 'Not Connected'}
                </p>
              </div>
            </div>
            {driveAuth?.authenticated ? (
              <button 
                onClick={() => handleSync('drive')}
                disabled={!!syncing}
                className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg disabled:opacity-50"
              >
                <RefreshCw className={`w-5 h-5 ${syncing === 'drive' ? 'animate-spin' : ''}`} />
              </button>
            ) : (
              <button 
                onClick={handleConnect}
                className="px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100"
              >
                Connect
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Document List */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-left">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-6 py-3 text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-xs font-medium text-gray-500 uppercase">Type</th>
              <th className="px-6 py-3 text-xs font-medium text-gray-500 uppercase">Chunks</th>
              <th className="px-6 py-3 text-xs font-medium text-gray-500 uppercase">Date</th>
              <th className="px-6 py-3 text-xs font-medium text-gray-500 uppercase text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                  <Loader2 className="w-6 h-6 animate-spin mx-auto" />
                </td>
              </tr>
            ) : documents.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                  No documents found. Upload or sync to get started.
                </td>
              </tr>
            ) : (
              documents.map((doc) => {
                const Icon = getIcon(doc.doc_type);
                return (
                  <tr key={doc.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <Icon className="w-4 h-4 text-gray-400" />
                        <span className="font-medium text-gray-900 truncate max-w-xs" title={doc.title}>
                          {doc.title || doc.filename}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 uppercase">{doc.doc_type}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{doc.chunk_count}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button 
                        onClick={() => handleDelete(doc.id)}
                        className="text-gray-400 hover:text-red-600 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

