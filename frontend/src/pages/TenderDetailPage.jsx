// src/pages/TenderDetailPage.jsx
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, ExternalLink } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import ScoreBadge from "../components/tender/ScoreBadge";
import TenderStatusBadge from "../components/tender/TenderStatusBadge";
import Spinner from "../components/ui/Spinner";
import Alert from "../components/ui/Alert";
import { useTender } from "../hooks/useTenders";
import { formatDate } from "../utils/formatters";

export default function TenderDetailPage() {
  const { id } = useParams();
  const { data: tender, isLoading, isError } = useTender(id);

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
        <Alert variant="error">
          Ce marché n'a pas pu être chargé.
        </Alert>
      </PageWrapper>
    );
  }

  const scoreCalcule =
    tender.score_details &&
    Object.values(tender.score_details).some((v) => typeof v === "number");

  return (
    <PageWrapper>
      <Link
        to="/tenders"
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-ink-900"
      >
        <ArrowLeft size={14} />
        Retour à la liste
      </Link>

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-mono text-slate-400">
              {tender.reference}
            </p>

            <h1 className="font-display text-xl font-semibold text-ink-900">
              {tender.objet}
            </h1>

            <p className="mt-1 text-sm text-slate-600">
              {tender.acheteur}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {scoreCalcule ? (
              <ScoreBadge score={tender.score} />
            ) : (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-400">
                Score à venir
              </span>
            )}

            <TenderStatusBadge statut={tender.statut} />
          </div>
        </div>

        <dl className="mt-6 grid grid-cols-2 gap-4 border-t border-slate-100 pt-6 text-sm sm:grid-cols-3">
          <Field label="Source" value={tender.source} />
          <Field label="Catégorie" value={tender.categorie} />
          <Field
            label="Date de publication"
            value={formatDate(tender.date_publication)}
          />
          <Field
            label="Date limite"
            value={formatDate(tender.date_limite)}
          />
          <Field
            label="Budget estimé"
            value={
              tender.budget_estime
                ? `${tender.budget_estime} TND`
                : "Non communiqué"
            }
          />
          <Field
            label="Commercial assigné"
            value={tender.commercial_assigne}
          />
        </dl>

        {tender.score_details && (
          <div className="mt-6 border-t border-slate-100 pt-6">
            <p className="mb-2 text-sm font-medium text-ink-900">
              Détail du score par catégorie
            </p>

            <div className="flex flex-wrap gap-2">
              {Object.entries(tender.score_details).map(([cat, val]) => (
                <span
                  key={cat}
                  className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600"
                >
                  {cat} : {val == null ? "—" : val}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="mt-6 border-t border-slate-100 pt-6">
          <a
            href={tender.lien}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-700 hover:underline"
          >
            <ExternalLink size={14} />
            Ouvrir l'annonce source
          </a>
        </div>
      </div>
    </PageWrapper>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-400">
        {label}
      </dt>
      <dd className="mt-0.5 font-medium text-ink-900">
        {value || "—"}
      </dd>
    </div>
  );
}