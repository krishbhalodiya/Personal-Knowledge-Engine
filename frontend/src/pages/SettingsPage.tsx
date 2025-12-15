import React, { useEffect, useState } from 'react';
import { Settings, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import client from '../api/client';
import { Settings as SettingsType } from '../types';

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsType | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client.get('/settings/providers')
      .then(res => setSettings(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loader2 className="w-8 h-8 animate-spin mx-auto mt-20 text-blue-600" />;
  if (!settings) return <div className="text-center mt-20 text-red-600">Failed to load settings</div>;

  return (
    <div className="space-y-8 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900">Settings</h1>

      {/* Embedding Provider */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Settings className="w-5 h-5 text-gray-400" />
          Embedding Provider
        </h2>
        
        <div className="space-y-4">
          {Object.entries(settings.embedding.options).map(([key, provider]) => (
            <div 
              key={key}
              className={`p-4 rounded-lg border ${
                key === settings.embedding.current 
                  ? 'border-blue-500 bg-blue-50' 
                  : 'border-gray-200 opacity-60'
              }`}
            >
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-medium text-gray-900">{provider.name}</h3>
                  <p className="text-sm text-gray-500">{provider.model}</p>
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
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Settings className="w-5 h-5 text-gray-400" />
          LLM Provider
        </h2>
        
        <div className="space-y-4">
          {Object.entries(settings.llm.options).map(([key, provider]) => (
            <div 
              key={key}
              className={`p-4 rounded-lg border ${
                key === settings.llm.current 
                  ? 'border-emerald-500 bg-emerald-50' 
                  : 'border-gray-200 opacity-60'
              }`}
            >
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-medium text-gray-900">{provider.name}</h3>
                  <p className="text-sm text-gray-500">{provider.model}</p>
                  {provider.status !== 'available' && provider.status !== 'active' && (
                    <div className="flex items-center gap-1 mt-2 text-xs text-red-600">
                      <AlertCircle className="w-3 h-3" />
                      <span>{provider.status}</span>
                    </div>
                  )}
                </div>
                {key === settings.llm.current && (
                  <CheckCircle className="w-5 h-5 text-emerald-600" />
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

