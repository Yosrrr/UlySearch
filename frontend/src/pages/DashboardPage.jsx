// src/pages/DashboardPage.jsx
import { AlertTriangle, Clock, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import StatCard from "../components/ui/StatCard";
import { MOCK_DASHBOARD } from "../api/mockData";

export default function DashboardPage() {
  // TODO : remplacer par un vrai appel API (useQuery) une fois la route
  // GET /api/dashboard disponible côté backend.
  const data = MOCK_DASHBOARD;

  const heureScraping = new Date(data.dernier_scraping.heure).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <h1 className="font-display text-2xl font-semibold text-ink-900">Dashboard</h1>
      <p className="mt-1 text-sm text-slate-600">Qu'est-ce qui a bougé aujourd'hui ?</p>

      {/* Indicateurs clés */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Nouveaux marchés détectés" value={data.stats.nouveaux_marches} />
        <StatCard label="Retenus après filtrage" value={data.stats.retenus} accent="teal" />
        <StatCard label="Déjà assignés" value={data.stats.assignes} accent="amber" />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Alertes du jour */}
        <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-display text-base font-semibold text-ink-900">
              <AlertTriangle size={16} className="text-amber-500" />
              Alertes du jour
            </h2>
            <Link to="/tenders" className="flex items-center gap-1 text-xs font-medium text-ink-700 hover:underline">
              Voir tous les marchés <ArrowRight size={12} />
            </Link>
          </div>

          {data.alertes_du_jour.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500">
              Aucune alerte à score élevé aujourd'hui.
            </p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.alertes_du_jour.map((a) => (
                <li key={a.id}>
                  <Link
                    to={`/tenders/${a.id}`}
                    className="flex items-center justify-between gap-3 py-3 hover:bg-slate-50"
                  >
                    <span className="text-sm text-ink-900">{a.objet}</span>
                    <span className="flex items-center gap-2 whitespace-nowrap">
                      <span className="rounded-full bg-amber-500 px-2 py-0.5 font-mono text-xs font-semibold text-white">
                        {a.score}%
                      </span>
                      <span className="text-xs text-slate-500">{a.commercial}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Répartition par commercial + statut scraping */}
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-3 font-display text-base font-semibold text-ink-900">
              Charge par commercial
            </h2>
            <ul className="space-y-2">
              {data.repartition_commerciaux.map((r) => (
                <li key={r.commercial} className="flex items-center justify-between text-sm">
                  <div>
                    <p className="text-ink-900">{r.commercial}</p>
                    <p className="text-xs text-slate-400">{r.marque}</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-xs font-semibold text-ink-800">
                    {r.nb_marches}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-2 flex items-center gap-2 font-display text-base font-semibold text-ink-900">
              <Clock size={16} className="text-slate-400" />
              Dernier scraping
            </h2>
            <p className="text-sm text-slate-600">
              {heureScraping} — {data.dernier_scraping.sources_ok}/{data.dernier_scraping.sources_total} sources OK
            </p>
            {data.dernier_scraping.erreurs.length > 0 ? (
              <p className="mt-1 text-xs text-rose-500">{data.dernier_scraping.erreurs.join(", ")}</p>
            ) : (
              <p className="mt-1 text-xs text-teal-600">Aucune erreur</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}