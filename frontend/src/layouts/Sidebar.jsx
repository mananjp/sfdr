import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Table, ClipboardCheck, History, Settings, X, ShieldAlert, LogOut, Package, Scale } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const Sidebar = ({ isOpen, onClose }) => {
  const { logout, currentUser } = useAuth();
  
  return (
    <>
      {/* Mobile Overlay */}
      <div 
        className={`fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-30 transition-opacity lg:hidden ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`} 
        onClick={onClose}
      ></div>
      
      <aside 
        className={`fixed lg:static inset-y-0 left-0 w-64 bg-white/80 backdrop-blur-xl border-r border-white/50 shadow-[4px_0_24px_rgba(0,0,0,0.02)] flex flex-col z-40 transition-transform duration-300 ease-out ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
      >
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-primary-600 to-accent-indigo rounded-xl flex items-center justify-center text-white shadow-lg shadow-primary-500/30">
              <ShieldAlert size={18} strokeWidth={2.5} />
            </div>
            <span className="font-bold text-lg text-slate-800 tracking-tight">SFDR<span className="text-primary-600 font-black">.</span>AI</span>
          </div>
          <button className="lg:hidden text-slate-500 hover:text-slate-700" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {[
            { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
            { to: '/matrix', icon: Table, label: 'Requirement Matrix' },
            { to: '/reviewer', icon: ClipboardCheck, label: 'Reviewer Desk' },
            { to: '/whatif', icon: Scale, label: 'What-If Simulator' },
            { to: '/audit', icon: History, label: 'Audit Trail' },
            { to: '/exports', icon: Package, label: 'Export Package' },
            { to: '/settings', icon: Settings, label: 'Settings' }
          ].map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onClose}
              className={({ isActive }) => `
                relative flex items-center gap-3 px-4 py-3 rounded-xl font-medium text-sm transition-all duration-200 group overflow-hidden
                ${isActive 
                  ? 'text-primary-700 bg-primary-50/80 shadow-[inset_0_1px_0_white,0_1px_3px_rgba(0,0,0,0.02)] border border-primary-100' 
                  : 'text-slate-600 hover:bg-slate-50/80 hover:text-slate-900 border border-transparent'}
              `}
            >
              {({ isActive }) => (
                <>
                  <item.icon size={18} className={`transition-colors ${isActive ? 'text-primary-600' : 'text-slate-400 group-hover:text-slate-600'}`} />
                  <span className="relative z-10">{item.label}</span>
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-primary-500 rounded-r-md"></div>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-100 bg-slate-50/50 m-4 rounded-xl border flex flex-col gap-3">
          <div>
            <div className="text-xs font-semibold text-slate-800">{currentUser?.username ? `Welcome, ${currentUser.username}` : 'Admin Workspace'}</div>
            <div className="text-[10px] text-slate-500 mt-1 uppercase tracking-wider">{currentUser?.role || 'Premium Edition'}</div>
          </div>
          <button 
            onClick={logout}
            className="flex items-center justify-center gap-2 w-full py-2 bg-white border border-slate-200 rounded-lg text-sm font-bold text-slate-600 hover:text-rose-600 hover:border-rose-200 hover:bg-rose-50 transition-colors"
          >
            <LogOut size={16} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
