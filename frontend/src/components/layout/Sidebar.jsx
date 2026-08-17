// src/components/layout/Sidebar.jsx

import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  ClipboardList,
  Archive,
  Building2,
  SlidersHorizontal,
  ShieldAlert,
  LogOut,
  ChevronRight,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";

const ITEMS = [
  {
    to: "/",
    label: "Dashboard",
    icon: LayoutDashboard,
    end: true,
  },
  {
    to: "/tenders",
    label: "Marchés",
    icon: ClipboardList,
  },
  {
    to: "/rejected",
    label: "Non retenus",
    icon: Archive,
  },
  {
    to: "/buyers",
    label: "Acheteurs",
    icon: Building2,
  },
  {
    to: "/admin",
    label: "Utilisateurs & Système",
    icon: ShieldAlert,
    superadminOnly: true,
  },
  {
    to: "/settings",
    label: "Configuration",
    icon: SlidersHorizontal,
    superadminOnly: true,
  },
];

export default function Sidebar() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const visibleItems = ITEMS.filter(
    (item) =>
      !item.superadminOnly ||
      user?.profil === "superadmin"
  );

  const handleLogout = () => {
    signOut();
    navigate("/login");
  };

  const userInitial = user?.email
    ? user.email.charAt(0).toUpperCase()
    : "U";

  return (
    <aside className="w-60 shrink-0 self-stretch border-r border-slate-800 bg-ink-900 text-white">
      <div className="sticky top-0 flex h-screen flex-col">
        {/* Logo */}
        <div className="border-b border-white/10 px-5 py-5">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2">
  <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-lg">
    <img
      src="/logo_sot.png"
      alt="Sotradies"
      className="h-full w-full object-contain"
    />
  </div>
</div>

            <div>
              <p className="font-display text-base font-semibold tracking-tight">
                SOTRADIES
              </p>

              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                Veille A.O.
              </p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-5">
          <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            Navigation
          </p>

          <div className="space-y-1">
            {visibleItems.map(
              ({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    [
                      "group flex items-center gap-3 rounded-lg px-3 py-2.5",
                      "text-sm font-medium transition-all duration-150",
                      isActive
                        ? "bg-white/10 text-white shadow-sm"
                        : "text-slate-400 hover:bg-white/5 hover:text-white",
                    ].join(" ")
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span
                        className={[
                          "flex h-7 w-7 items-center justify-center rounded-md transition-colors",
                          isActive
                            ? "bg-amber-500/15 text-amber-400"
                            : "text-slate-500 group-hover:text-slate-300",
                        ].join(" ")}
                      >
                        <Icon size={16} strokeWidth={1.8} />
                      </span>

                      <span className="flex-1">
                        {label}
                      </span>

                      {isActive && (
                        <ChevronRight
                          size={14}
                          className="text-slate-500"
                        />
                      )}
                    </>
                  )}
                </NavLink>
              )
            )}
          </div>
        </nav>

        {/* Utilisateur / Déconnexion */}
        <div className="border-t border-white/10 p-3">
          <div className="mb-2 flex items-center gap-3 rounded-lg px-2 py-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-semibold text-white">
              {userInitial}
            </div>

            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-slate-200">
                {user?.email || "Utilisateur"}
              </p>

              {user?.profil && (
                <p className="mt-0.5 text-[10px] capitalize text-slate-500">
                  {user.profil}
                </p>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm text-slate-400 transition-colors hover:bg-red-500/10 hover:text-red-300"
          >
            <LogOut size={16} strokeWidth={1.8} />
            <span>Déconnexion</span>
          </button>
        </div>
      </div>
    </aside>
  );
}