// src/pages/DashboardPage.jsx
import { AlertTriangle, Clock, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import StatCard from "../components/ui/StatCard";
import Spinner from "../components/ui/Spinner";
import Alert from "../components/ui/Alert";
import { useDashboardData } from "../hooks/useDashboardData";
import { categoryLabel } from "../utils/categories";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function DashboardPage() {
  const { dashboard, isLoading, isError } = useDashboardData();

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-16">
        <div className="flex justify-center"><Spinner /></div>
      </div>
    );
  }

  if (isError || !dashboard) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-8">
        <Alert variant="error">Impossible de charger les données du dashboard.</Alert>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <h1 className="font-display text-2xl font-semibold text-ink-900">Dashboard</h1>
      <p className="mt-1 text-sm text-slate-600">Qu'est-ce qui a bougé aujourd'hui ?</p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Marchés détectés" value={dashboard.stats.nouveaux_marches} />
        <StatCard label="Retenus après filtrage" value={dashboard.stats.retenus} accent="teal" />
        <StatCard label="Déjà assignés" value={dashboard.stats.assignes} accent="amber" />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-display text-base font-semibold text-ink-900">
              <AlertTriangle size={16} className="text-amber-500" />
              Alertes (score &gt; 70%)
            </h2>
            <Link to="/tenders" className="flex items-center gap-1 text-xs font-medium text-ink-700 hover:underline">
              Voir tous les marchés <ArrowRight size={12} />
            </Link>
          </div>

          {dashboard.alertes_du_jour.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500">
              Aucune alerte à score élevé pour le moment.
            </p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {dashboard.alertes_du_jour.map((t) => (
                <li key={t.id}>
                  <Link
                    to={`/tenders/${t.id}`}
                    className="flex items-center justify-between gap-3 py-3 hover:bg-slate-50"
                  >
                    <span className="text-sm text-ink-900">{t.objet}</span>
                    <span className="flex items-center gap-2 whitespace-nowrap">
                      <span className="rounded-full bg-amber-500 px-2 py-0.5 font-mono text-xs font-semibold text-white">
                        {t.score}%
                      </span>
                      <span className="text-xs text-slate-500">{t.commercial_assigne || "Non assigné"}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
        

        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-3 font-display text-base font-semibold text-ink-900">
              Charge par commercial
            </h2>
            {dashboard.repartition_commerciaux.length === 0 ? (
              <p className="text-sm text-slate-500">Aucun marché assigné pour le moment.</p>
            ) : (
              <ul className="space-y-2">
                {dashboard.repartition_commerciaux.map((r) => (
                  <li key={r.commercial} className="flex items-center justify-between text-sm">
                    <div>
                      <p className="text-ink-900">{r.commercial}</p>
                      <p className="text-xs text-slate-400">{categoryLabel(r.categorie)}</p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-xs font-semibold text-ink-800">
                      {r.nb_marches}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-2 flex items-center gap-2 font-display text-base font-semibold text-ink-900">
              <Clock size={16} className="text-slate-400" />
              Dernière détection
            </h2>
            <p className="text-sm text-slate-600">
              {dashboard.derniere_detection
                ? new Date(dashboard.derniere_detection).toLocaleString("fr-FR")
                : "—"}
            </p>
          </div>
          
        </div>
        
      </div>
      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
  <h2 className="mb-4 font-display text-base font-semibold text-ink-900">
    Marchés détectés par semaine
  </h2>
  <ResponsiveContainer width="100%" height={220}>
    <LineChart data={dashboard.weekly_counts}>
      <CartesianGrid strokeDasharray="3 3" stroke="#EEF1F4" />
      <XAxis dataKey="semaine" tick={{ fontSize: 12, fill: "#5B6472" }} />
      <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#5B6472" }} />
      <Tooltip
        contentStyle={{ borderRadius: 8, border: "1px solid #DDE2E8", fontSize: 13 }}
      />
      <Line
        type="monotone"
        dataKey="marches"
        stroke="#E8873A"
        strokeWidth={2}
        dot={{ fill: "#E8873A", r: 3 }}
        name="Marchés détectés"
      />
    </LineChart>
  </ResponsiveContainer>
</div>
    </div>
  );
}
