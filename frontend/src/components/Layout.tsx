import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { MessageSquare, Search, FileText, Settings, Database } from 'lucide-react';
import clsx from 'clsx';

const NavItem = ({ to, icon: Icon, label }: { to: string; icon: any; label: string }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      clsx(
        'flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-lg transition-colors',
        isActive
          ? 'bg-blue-50 text-blue-600'
          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
      )
    }
  >
    <Icon className="w-5 h-5" />
    {label}
  </NavLink>
);

export default function Layout() {
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center gap-2 font-bold text-xl text-gray-900">
            <Database className="w-6 h-6 text-blue-600" />
            <span>PK Engine</span>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          <NavItem to="/" icon={Search} label="Search" />
          <NavItem to="/chat" icon={MessageSquare} label="Chat Assistant" />
          <NavItem to="/documents" icon={FileText} label="Documents" />
          <NavItem to="/settings" icon={Settings} label="Settings" />
        </nav>

        <div className="p-4 border-t border-gray-200 text-xs text-gray-500">
          v0.1.0 • Local/Hybrid
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
