import React, { useEffect, useState } from 'react';
import { Settings, CheckCircle, AlertCircle, Loader2, Zap } from 'lucide-react';
import client from '../api/client';
import type { Settings as SettingsType } from '../types/index.js';

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsType | null>(null);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchSettings = () => {
    client.get('/settings/providers')
      .then(res => setSettings(res.data))
      .catch((error) => {
        if (error.code === 'ERR_NETWORK' || error.message === 'Network Error') {
          console.warn('Backend server is not running.');
        } else {
          console.error('Failed to load settings:', error);
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleSwitchLLM = async (provider: string) => {
    if (!settings || provider === settings.llm.current) return;
    
    setSwitching(provider);
    setMessage(null);
    
    try {
      const res = await client.post('/settings/llm/switch', { provider });
      setMessage({ type: 'success', text: res.data.message });
      // Refresh settings
      fetchSettings();
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 'Failed to switch provider';
      setMessage({ type: 'error', text: errorMsg });
    } finally {
      setSwitching(null);
    }
  };

  if (loading) return <Loader2 className="w-8 h-8 animate-spin mx-auto mt-20 text-blue-600" />;
  if (!settings) {
    return (
      <div className="text-center mt-20 space-y-4">
        <div className="text-red-600 font-medium">Failed to load settings</div>
        <div className="text-sm text-gray-500 max-w-md mx-auto">
          The backend server may not be running. Please start it with:
          <code className="block mt-2 p-2 bg-gray-100 rounded text-xs">
            cd backend && uvicorn app.main:app --reload
          </code>
        </div>
      </div>
    );
  }

  const canSwitch = (key: string, status: string) => {
    return status === 'available' || status === 'active';
  };

  return (
    <div className="space-y-8 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900">Settings</h1>

      {/* Status Message */}
      {message && (
        <div className={`p-4 rounded-lg flex items-center gap-2 ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-800 border border-green-200' 
            : 'bg-red-50 text-red-800 border border-red-200'
        }`}>
          {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Embedding Provider */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <h2 className="text-lg font-semibold mb-2 flex items-center gap-2">
          <Settings className="w-5 h-5 text-gray-400" />
          Embedding Provider
        </h2>
        <p className="text-xs text-amber-600 mb-4">
          Changing embedding model requires re-indexing all documents
        </p>
        
        <div className="space-y-3">
          {Object.entries(settings.embedding.options).map(([key, provider]) => (
            <div 
              key={key}
              className={`p-4 rounded-lg border transition-all ${
                key === settings.embedding.current 
                  ? 'border-blue-500 bg-blue-50' 
                  : 'border-gray-200 opacity-60'
              }`}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <h3 className="font-medium text-gray-900">{provider.name}</h3>
                  {key === 'openai' && provider.available_models ? (
                    <div className="mt-2 space-y-2">
                      {Object.entries(provider.available_models).map(([model, info]) => (
                        <button
                          key={model}
                          onClick={async () => {
                            if (model === provider.model) return;
                            if (!confirm(`Switch to ${model}? This requires re-indexing!`)) return;
                            try {
                              await client.post('/settings/embedding/model/switch', { model });
                              setMessage({ type: 'success', text: `Switched to ${model}` });
                              fetchSettings();
                            } catch (err: any) {
                              setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to switch' });
                            }
                          }}
                          className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${
                            model === provider.model
                              ? 'bg-emerald-100 border-emerald-300 text-emerald-700 font-medium'
                              : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                          }`}
                        >
                          {model}
                          {info.cost === 'cheap' && <span className="ml-1 text-emerald-600">$</span>}
                          {info.cost === 'expensive' && <span className="ml-1 text-amber-600">$$$</span>}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500">{provider.model}</p>
                  )}
                  <p className="text-xs text-gray-400 mt-1">
                    Dimensions: {provider.dimension}
                  </p>
                </div>
                {key === settings.embedding.current && (
                  <CheckCircle className="w-5 h-5 text-blue-600" />
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* LLM Provider */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <h2 className="text-lg font-semibold mb-2 flex items-center gap-2">
          <Zap className="w-5 h-5 text-gray-400" />
          LLM Provider
        </h2>
        <p className="text-xs text-gray-500 mb-4">
          Click on an available provider to switch. Changes take effect immediately.
        </p>
        
        <div className="space-y-3">
          {Object.entries(settings.llm.options).map(([key, provider]) => {
            const isActive = key === settings.llm.current;
            const isSwitching = switching === key;
            const isAvailable = canSwitch(key, provider.status);
            
            return (
              <div 
                key={key}
                onClick={() => isAvailable && !isActive && handleSwitchLLM(key)}
                className={`p-4 rounded-lg border transition-all ${
                  isActive 
                    ? 'border-emerald-500 bg-emerald-50' 
                    : isAvailable
                      ? 'border-gray-200 hover:border-emerald-300 hover:bg-emerald-50/50 cursor-pointer'
                      : 'border-gray-200 opacity-50 cursor-not-allowed'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-medium text-gray-900 flex items-center gap-2">
                      {provider.name}
                      {isSwitching && <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />}
                    </h3>
                    <p className="text-sm text-gray-500">{provider.model}</p>
                    {!isAvailable && provider.status !== 'active' && (
                      <div className="flex items-center gap-1 mt-2 text-xs text-amber-600">
                        <AlertCircle className="w-3 h-3" />
                        <span>
                          {provider.status === 'api_key_missing' 
                            ? 'API key not configured' 
                            : provider.status === 'model_missing'
                              ? 'Model path not configured'
                              : provider.status}
                        </span>
                      </div>
                    )}
                  </div>
                  {isActive ? (
                    <span className="flex items-center gap-1 text-xs font-medium text-emerald-600 bg-emerald-100 px-2 py-1 rounded-full">
                      <CheckCircle className="w-3 h-3" />
                      Active
                    </span>
                  ) : isAvailable ? (
                    <span className="text-xs text-gray-400">Click to switch</span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Configuration Help */}
      <div className="bg-gray-50 p-6 rounded-xl border border-gray-200">
        <h3 className="font-semibold text-gray-900 mb-2">Configure Providers</h3>
        <p className="text-sm text-gray-600 mb-3">
          Add API keys to your <code className="bg-gray-200 px-1 rounded">backend/.env</code> file:
        </p>
        <pre className="bg-gray-800 text-gray-100 p-4 rounded-lg text-xs overflow-x-auto">
{`# OpenAI
OPENAI_API_KEY=sk-...

# Google Gemini
GOOGLE_GEMINI_API_KEY=AIza...

# Local LLM (optional)
LLM_MODEL_PATH=./data/models/your-model.gguf`}
        </pre>
      </div>
    </div>
  );
}

