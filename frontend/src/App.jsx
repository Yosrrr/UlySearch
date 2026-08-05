// src/App.jsx
import { Routes, Route, Navigate } from "react-router";
import Sidebar from "./components/layout/Sidebar";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import TendersPage from "./pages/TendersPage";
import RejectedTendersPage from "./pages/RejectedTendersPage";
import BuyersPage from "./pages/BuyersPage";
import SettingsPage from "./pages/SettingsPage";
import UsersPage from "./pages/UsersPage";
import { useAuth } from "./context/AuthContext";

function ProtectedLayout({ children }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
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
      <Route path="/rejected" element={<ProtectedLayout><RejectedTendersPage /></ProtectedLayout>} />
      <Route path="/buyers" element={<ProtectedLayout><BuyersPage /></ProtectedLayout>} />
      <Route path="/settings" element={<ProtectedLayout><SettingsPage /></ProtectedLayout>} />
      <Route path="/users" element={<ProtectedLayout><UsersPage /></ProtectedLayout>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
