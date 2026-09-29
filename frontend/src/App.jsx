// src/App.jsx
import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/layout/Sidebar";
import { useAuth } from "./context/AuthContext";

const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const AiOnboardingPage = lazy(() => import("./pages/AiOnboardingPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const TendersPage = lazy(() => import("./pages/TendersPage"));
const RejectedTendersPage = lazy(() => import("./pages/RejectedTendersPage"));
const BuyersPage = lazy(() => import("./pages/BuyersPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const TenderDetailPage = lazy(() => import("./pages/TenderDetailPage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));

function ProtectedLayout({ children, requireSuperadmin = false }) {
  const { isAuthenticated, user, authReady } = useAuth();
  if (!authReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">
        Vérification de la session...
      </div>
    );
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (requireSuperadmin && user?.profil !== "superadmin") return <Navigate to="/" replace />;
  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">Chargement...</div>}>
      <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedLayout><DashboardPage /></ProtectedLayout>} />
      <Route path="/tenders" element={<ProtectedLayout><TendersPage /></ProtectedLayout>} />
      <Route path="/tenders/:id" element={<ProtectedLayout><TenderDetailPage /></ProtectedLayout>} />
      <Route path="/rejected" element={<ProtectedLayout><RejectedTendersPage /></ProtectedLayout>} />
      <Route path="/buyers" element={<ProtectedLayout><BuyersPage /></ProtectedLayout>} />
      <Route path="/settings" element={<ProtectedLayout requireSuperadmin><SettingsPage /></ProtectedLayout>} />
      <Route path="/admin" element={<ProtectedLayout requireSuperadmin><AdminPage /></ProtectedLayout>} />
      <Route path="*" element={<Navigate to="/" replace />} />
      <Route path="/ai-config" element={<ProtectedLayout requireSuperadmin><AiOnboardingPage /></ProtectedLayout>} />
      <Route path="/register" element={<RegisterPage />} />

      </Routes>
    </Suspense>
  );
}