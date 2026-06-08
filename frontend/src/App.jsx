import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ProjectProvider } from './context/ProjectContext';

// Layouts
import MainLayout from './layouts/MainLayout';
import AuthLayout from './layouts/AuthLayout';

// Auth Pages
import Login from './pages/Login';
import Signup from './pages/Signup';

// Landing Page
import Home from './pages/Home';

// Protected Pages
import Dashboard from './pages/Dashboard';
import RequirementMatrix from './pages/RequirementMatrix';
import ReviewerDesk from './pages/ReviewerDesk';
import AuditTrail from './pages/AuditTrail';
import AuditExport from './pages/AuditExport';
import Settings from './pages/Settings';

const ProtectedRoute = () => {
  const { currentUser, loading } = useAuth();
  
  if (loading) return (
    <div className="h-screen w-screen flex flex-col items-center justify-center bg-slate-50 text-slate-500 gap-4">
      <div className="w-12 h-12 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
      <span className="font-bold">Loading workspace...</span>
    </div>
  );
  
  return currentUser ? (
    <ProjectProvider>
      <Outlet />
    </ProjectProvider>
  ) : <Navigate to="/login" replace />;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Landing Page */}
          <Route path="/" element={<Home />} />

          {/* Public Auth Routes */}
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
          </Route>

          {/* Protected App Routes */}
          <Route element={<ProtectedRoute />}>
            <Route element={<MainLayout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/matrix" element={<RequirementMatrix />} />
              <Route path="/reviewer" element={<ReviewerDesk />} />
              <Route path="/audit" element={<AuditTrail />} />
              <Route path="/exports" element={<AuditExport />} />
              <Route path="/settings" element={<Settings />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
