// src/components/layout/Sidebar.jsx
import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, ClipboardList, Archive, Building2, SlidersHorizontal, ShieldAlert, LogOut,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";

const ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/tenders", label: "Marchés", icon: ClipboardList },
  { to: "/rejected", label: "Non retenus", icon: Archive },
  { to: "/buyers", label: "Acheteurs", icon: Building2 },
  { to: "/admin", label: "Utilisateurs & Système", icon: ShieldAlert, superadminOnly: true },
  { to: "/settings", label: "Configuration", icon: SlidersHorizontal, superadminOnly: true },
];

export default function Sidebar() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const visibleItems = ITEMS.filter((item) => !item.superadminOnly || user?.profil === "superadmin");

  return (
    <aside className="flex h-screen w-60 flex-col bg-ink-900 text-white">
      <div className="px-5 py-5 font-display text-lg font-semibold">
        SOTRADIES <span className="text-amber-500">·</span> Veille A.O.
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {visibleItems.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium ${
                isActive ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"
              }`
            }
          >
            <Icon size={16} /> {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 px-3 py-4">
        <p className="truncate px-2 text-xs text-slate-400">{user?.email}</p>
        <button
          onClick={() => { signOut(); navigate("/login"); }}
          className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white"
        >
          <LogOut size={16} /> Déconnexion
        </button>
      </div>
    </aside>
  );
}