// src/pages/RejectedTendersPage.jsx
import { useState, useMemo } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { Search, Undo2 } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import Spinner from "../components/ui/Spinner";
import Alert from "../components/ui/Alert";
import { useRejectedTenders } from "../hooks/useTenders";
import { updateTenderStatus } from "../api/tenders";

export default function RejectedTendersPage() {
  const { data: tenders, isLoading, isError } = useRejectedTenders();
  const [search, setSearch] = useState("");
  const queryClient = useQueryClient();

  const restoreMutation = useMutation({
    mutationFn: (id) => updateTenderStatus(id, "retenu"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rejected-tenders"] });
      queryClient.invalidateQueries({ queryKey: ["tenders"] });
    },
  });

  const filtered = useMemo(() => {
    if (!tenders) return [];
    if (!search) return tenders;
    const s = search.toLowerCase();
    return tenders.filter(
      (t) => t.objet.toLowerCase().includes(s) || t.acheteur.toLowerCase().includes(s)
    );
  }, [tenders, search]);

  return (
    <PageWrapper
      title="Non retenus"
      subtitle="Marchés écartés par le filtrage automatique — rien n'est supprimé, tout reste consultable."
    >
      <div className="mb-5 flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <Search size={16} className="text-slate-400" />
        <input
          type="text"
          placeholder="Vérifier qu'un marché connu n'a pas été rejeté à tort..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 text-sm outline-none"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center py-16"><Spinner /></div>
      )}
      {isError && <Alert variant="error">Impossible de charger les marchés non retenus.</Alert>}
      {filtered.length === 0 && !isLoading && (
        <Alert variant="info">Aucun marché non retenu ne correspond.</Alert>
      )}

      <div className="space-y-2">
        {filtered.map((t) => (
          <div key={t.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate font-medium text-ink-900">{t.objet}</p>
                <p className="mt-0.5 truncate text-sm text-slate-600">{t.acheteur}</p>
              </div>
              <span className="whitespace-nowrap rounded-full bg-slate-100 px-2.5 py-1 font-mono text-xs text-slate-500">
                {t.score}%
              </span>
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-slate-500">{t.raison_rejet}</span>
              <button
                onClick={() => restoreMutation.mutate(t.id)}
                disabled={restoreMutation.isPending}
                className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-ink-800 hover:bg-slate-50 disabled:opacity-60"
              >
                <Undo2 size={12} /> Repêcher vers Marchés
              </button>
            </div>
          </div>
        ))}
      </div>
    </PageWrapper>
  );
}