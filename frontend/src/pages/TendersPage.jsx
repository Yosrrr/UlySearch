// src/pages/TendersPage.jsx

import { useState } from "react";
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
    data: tenders,
    isLoading,
    isError,
  } = useTenders(filters);

  async function handleExport(format) {
    setExporting(true);

    try {
      await exportTenders(filters, format);
    } catch (err) {
      console.error("Export échoué", err);
    } finally {
      setExporting(false);
    }
  }

  return (
    <PageWrapper
      title="Marchés"
      subtitle="Liste des marchés détectés, filtrables par catégorie, statut et score."
      actions={
        <ExportButtons
          onExport={handleExport}
          exporting={exporting}
        />
      }
    >
      {/* Filtres */}
      <TenderFilters
        value={filters}
        onChange={setFilters}
      />

      {/* Chargement */}
      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {/* Erreur */}
      {isError && (
        <Alert variant="error">
          Impossible de charger les marchés — vérifiez que le backend tourne.
        </Alert>
      )}

      {/* Aucun résultat */}
      {tenders && tenders.length === 0 && (
        <Alert variant="info">
          Aucun marché ne correspond à ces filtres.
        </Alert>
      )}

      {/* Liste des marchés */}
      {tenders && tenders.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {tenders.map((tender) => (
            <TenderCard
              key={tender.id}
              tender={tender}
            />
          ))}
        </div>
      )}
    </PageWrapper>
  );
}