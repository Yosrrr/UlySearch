// src/pages/TenderDetailPage.jsx
import { useParams, Link } from "react-router";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, Check } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import ScoreBadge from "../components/tender/ScoreBadge";
import TenderStatusBadge from "../components/tender/TenderStatusBadge";
import Spinner from "../components/ui/Spinner";
import Alert from "../components/ui/Alert";
import { useTender } from "../hooks/useTenders";
import { updateTenderStatus } from "../api/tenders";
import { formatDate } from "../utils/formatters";
import { extractScoreInfo } from "../utils/scoreDetails";
import { categoryLabel } from "../utils/categories";

const STATUTS = [
  { value: "nouveau", label: "Nouveau" },
  { value: "retenu", label: "Retenu" },
  { value: "sans_suite", label: "Sans suite" },
];

export default function TenderDetailPage() {
  const { id } = useParams();
  const { data: tender, isLoading, isError } = useTender(id);
  const queryClient = useQueryClient();

  const statusMutation = useMutation({
    mutationFn: (statut) => updateTenderStatus(id, statut),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tender", id] });
      queryClient.invalidateQueries({ queryKey: ["tenders"] });
    },
  });

  if (isLoading) {
    return (
      <PageWrapper>
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      </PageWrapper>
    );
  }

  if (isError || !tender) {
    return (
      <PageWrapper>
        <Alert variant="error">Ce marché n'a pas pu être chargé.</Alert>
      </PageWrapper>
    );
  }

  const { hasScore, score } = extractScoreInfo(tender.score_details);

  return (
    <PageWrapper>
      <Link to="/tenders" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-ink-900">
        <ArrowLeft size={14} /> Retour à la liste
      </Link>

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-mono text-slate-400">{tender.reference}</p>
            <h1 className="font-display text-xl font-semibold text-ink-900">{tender.objet}</h1>
            <p className="mt-1 text-sm text-slate-600">{tender.acheteur}</p>
          </div>
          <div className="flex items-center gap-2">
            {hasScore ? (
              <ScoreBadge score={score} />
            ) : (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-400">Score à venir</span>
            )}
            <TenderStatusBadge statut={tender.statut} />
          </div>
        </div>

        <dl className="mt-6 grid grid-cols-2 gap-4 border-t border-slate-100 pt-6 text-sm sm:grid-cols-3">
          <Field label="Source" value={tender.source} />
          <Field label="Catégorie" value={tender.categorie} />
          <Field label="Date de publication" value={formatDate(tender.date_publication)} />
          <Field label="Date limite" value={formatDate(tender.date_limite)} />
          <Field label="Commercial assigné" value={tender.commercial_assigne} />
          <Field label="Acheteur connu" value={tender.acheteur_connu ? "Oui" : "Non"} />
        </dl>

        {tender.score_details && (
          <div className="mt-6 border-t border-slate-100 pt-6">
            <p className="mb-2 text-sm font-medium text-ink-900">Détail du score par catégorie</p>
            <div className="space-y-2">
              {Object.entries(tender.score_details).map(([cat, val]) => {
                const catScore = typeof val === "object" ? val?.score : val;
                const matched = typeof val === "object" ? val?.mots_cles_matches : null;
                return (
                  <div key={cat} className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
                      {categoryLabel(cat)} : {catScore ?? "-"}
                    </span>
                    {matched && matched.length > 0 && (
                      <span className="text-slate-500">mots-clés : {matched.join(", ")}</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-6">
          <span className="text-sm font-medium text-ink-900">Changer le statut :</span>
          {STATUTS.map(({ value, label }) => {
            const isCurrent = tender.statut === value;
            return (
              <button
                key={value}
                disabled={isCurrent || statusMutation.isPending}
                onClick={() => statusMutation.mutate(value)}
                className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium ${
                  isCurrent
                    ? "border-ink-800 bg-ink-800 text-white"
                    : "border-slate-200 text-ink-900 hover:bg-slate-50"
                } disabled:opacity-60`}
              >
                {isCurrent && <Check size={12} />}
                {label}
              </button>
            );
          })}
          {statusMutation.isPending && <Spinner className="h-4 w-4" />}
        </div>
        {statusMutation.isError && (
          <div className="mt-3">
            <Alert variant="error">Le changement de statut a échoué — réessayez.</Alert>
          </div>
        )}

<div className="mt-6 border-t border-slate-100 pt-6">
          <a
            href={tender.lien}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-700 hover:underline"
          >
            <ExternalLink size={14} /> Ouvrir l'annonce source
          </a>
        </div>
      </div>
    </PageWrapper>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 font-medium text-ink-900">{value || "—"}</dd>
    </div>
  );
}
