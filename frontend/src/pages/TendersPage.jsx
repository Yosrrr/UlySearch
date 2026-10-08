// src/pages/TendersPage.jsx

import { useState, useEffect } from "react";
import PageWrapper from "../components/layout/PageWrapper";
import TenderFilters from "../components/tender/TenderFilters";
import TenderCard from "../components/tender/TenderCard";
import Spinner from "../components/ui/Spinner";
import Alert from "../components/ui/Alert";
import ExportButtons from "../components/ui/ExportButtons";
import { useTenders } from "../hooks/useTenders";
import { exportTenders } from "../api/tenders";

export default function TendersPage() {
  const [filters, setFilters] = useState({
    statut: "Tous",
  });

  const [exporting, setExporting] = useState(false);

  const {
    items: tenders,
    total,
    limit,
    offset,
    hasMore,
    nextPage,
    prevPage,
    resetPage,
    isLoading,
    isError,
    isFetching,
  } = useTenders(filters);

  // Retour page 1 à chaque changement de filtres
  useEffect(() => {
    resetPage?.();
  }, [filters]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleExport(format) {
    setExporting(true);
    try {
      // Adapte l'ordre si ton api/tenders.js est (format, filters)
      await exportTenders({ ...filters, format });
      // ou : await exportTenders(format, filters);
    } catch (err) {
      console.error("Export échoué", err);
    } finally {
      setExporting(false);
    }
  }

  function handleFiltersChange(next) {
    setFilters(next);
  }

  const showEmpty =
    !isLoading && !isError && Array.isArray(tenders) && tenders.length === 0;

  const showList =
    !isLoading && !isError && Array.isArray(tenders) && tenders.length > 0;

  return (
    <PageWrapper
      title="Marchés"
      subtitle="Liste des marchés détectés, filtrables par catégorie, statut et score."
      actions={
        <ExportButtons onExport={handleExport} exporting={exporting} />
      }
    >
      <TenderFilters value={filters} onChange={handleFiltersChange} />

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {isError && (
        <Alert variant="error">
          Impossible de charger les marchés — vérifiez que le backend tourne.
        </Alert>
      )}

      {showEmpty && (
        <Alert variant="info">
          Aucun marché ne correspond à ces filtres.
        </Alert>
      )}

      {showList && (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            {tenders.map((tender) => (
              <TenderCard key={tender.id} tender={tender} />
            ))}
          </div>

          {/* F-019 pagination */}
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3 text-sm text-slate-600">
            <button
              type="button"
              onClick={prevPage}
              disabled={offset === 0 || isFetching}
              className="rounded border border-slate-300 px-3 py-1.5 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Précédent
            </button>

            <span className="min-w-[8rem] text-center tabular-nums">
              {total === 0
                ? "0"
                : `${offset + 1}–${Math.min(offset + tenders.length, total)}`}
              {" / "}
              {total}
              {limit ? (
                <span className="ml-1 text-slate-400">({limit}/page)</span>
              ) : null}
            </span>

            <button
              type="button"
              onClick={nextPage}
              disabled={!hasMore || isFetching}
              className="rounded border border-slate-300 px-3 py-1.5 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Suivant
            </button>
          </div>
        </>
      )}
    </PageWrapper>
  );
}