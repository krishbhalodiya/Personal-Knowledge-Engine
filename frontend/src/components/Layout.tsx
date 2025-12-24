import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { MessageSquare, Search, FileText, Settings, Database, FolderOpen } from 'lucide-react';
import clsx from 'clsx';

const NavItem = ({ to, icon: Icon, label }: { to: string; icon: any; label: string }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      clsx(
        'flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-xl transition-all duration-200 group',
        isActive
          ? 'bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow-lg shadow-blue-500/25'
          : 'text-gray-600 hover:bg-white/60 hover:text-gray-900 hover:shadow-sm'
      )
    }
  >
    <Icon className={clsx('w-5 h-5 transition-transform', 'group-hover:scale-110')} />
    {label}
  </NavLink>
);

export default function Layout() {
  return (
    <div className="flex h-screen">
      <div className="w-64 glass border-r border-white/40 flex flex-col shadow-xl">
        <div className="p-6 border-b border-white/20">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-gradient-to-br from-blue-500 to-purple-500 rounded-xl shadow-lg">
              <Database className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg gradient-text">PK Engine</span>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1.5">
          <NavItem to="/" icon={Search} label="Search" />
          <NavItem to="/chat" icon={MessageSquare} label="Chat" />
          <NavItem to="/documents" icon={FileText} label="Documents" />
          <NavItem to="/sources" icon={FolderOpen} label="Sources" />
          <NavItem to="/settings" icon={Settings} label="Settings" />
        </nav>

        <div className="p-4 border-t border-white/20 text-xs text-gray-400">
          v0.1.0
        </div>
      </div>

      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
