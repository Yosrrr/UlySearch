// src/components/tender/TenderFilters.jsx
import { useQuery } from "@tanstack/react-query";
import { getRuntimeThresholds, getCategories } from "../../api/config";

const STATUTS = ["Tous", "nouveau", "retenu", "sans_suite"];
export default function TenderFilters({ value, onChange }) {
  const { data } = useQuery({
    queryKey: ["runtime-thresholds"],
    queryFn: getRuntimeThresholds,
    staleTime: 60_000,
  });
  const { data: categories = [] } = useQuery({
    queryKey: ["config-categories"],
    queryFn: getCategories,
    staleTime: 60_000,
  });
  const instantThreshold = data?.score_instant_alert_threshold ?? 70;

  function update(field, val) {
    onChange({ ...value, [field]: val });
  }

  return (
    <div className="mb-5 flex flex-wrap gap-3 rounded-xl border border-slate-200 bg-white p-3">
      <input
        type="text"
        placeholder="Rechercher (objet, acheteur)..."
        value={value.search ?? ""}
        onChange={(e) => update("search", e.target.value)}
        className="min-w-[220px] flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-ink-700"
      />
      <select
        value={value.categorie ?? "Toutes"}
        onChange={(e) => update("categorie", e.target.value)}
        className="w-52 rounded-lg border border-slate-200 px-3 py-2 text-sm"
      >
        <option value="Toutes">Toutes les catégories</option>
        {categories.map((category) => (
          <option key={category.id} value={category.id}>
            {category.label || category.id}
          </option>
        ))}
      </select>
      <select
        value={value.statut ?? "Tous"}
        onChange={(e) => update("statut", e.target.value)}
        className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
      >
        {STATUTS.map((s) => (
          <option key={s} value={s}>{s === "Tous" ? "Tous les statuts" : s.replace("_", " ")}</option>
        ))}
      </select>
      <select
        value={value.score_min ?? ""}
        onChange={(e) => update("score_min", e.target.value)}
        className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
      >
        <option value="">Score minimum</option>
        <option value={instantThreshold}>≥ {instantThreshold}% (priorité)</option>
        <option value="50">≥ 50%</option>
      </select>
    </div>
  );
}