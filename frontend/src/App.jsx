// src/App.jsx
import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/layout/Sidebar";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import TendersPage from "./pages/TendersPage";
import RejectedTendersPage from "./pages/RejectedTendersPage";
import BuyersPage from "./pages/BuyersPage";
import SettingsPage from "./pages/SettingsPage";
import TenderDetailPage from "./pages/TenderDetailPage";
import AdminPage from "./pages/AdminPage";
import { useAuth } from "./context/AuthContext";

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
    </Routes>
  );
}