import React, { useEffect, useState } from 'react';
import { Upload, RefreshCw, Trash2, File, Mail, FileText, Loader2, HardDrive } from 'lucide-react';
import client from '../api/client';
import { Document, GoogleAuthStatus } from '../types';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  
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

  const handleSync = async (source: 'gmail' | 'drive') => {
    setSyncing(source);
    try {
      await client.post(`/${source}/sync`, source === 'gmail' ? { max_results: 10 } : { limit: 10 });
      await fetchDocuments();
    } catch (err) {
      console.error(err);
      alert(`Failed to sync ${source}`);
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
            <input type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
          </label>
        </div>
      </div>

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

