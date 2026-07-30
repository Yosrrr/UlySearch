// src/pages/TendersPage.jsx
import { useState } from "react";
import PageWrapper from "../components/layout/PageWrapper";
import TenderFilters from "../components/tender/TenderFilters";
import TenderCard from "../components/tender/TenderCard";
import Spinner from "../components/ui/Spinner";
import Alert from "../components/ui/Alert";
import { useTenders } from "../hooks/useTenders";

export default function TendersPage() {
  const [filters, setFilters] = useState({ statut: "Tous" });
  const { data: tenders, isLoading, isError } = useTenders(filters);

  return (
    <PageWrapper
      title="Marchés"
      subtitle="Liste des marchés détectés, filtrables par catégorie, statut et score."
    >
      <TenderFilters value={filters} onChange={setFilters} />

      {isLoading && (
        <div className="flex justify-center py-16"><Spinner /></div>
      )}
      {isError && (
        <Alert variant="error">Impossible de charger les marchés — vérifiez que le backend tourne.</Alert>
      )}
      {tenders && tenders.length === 0 && (
        <Alert variant="info">Aucun marché ne correspond à ces filtres.</Alert>
      )}
      {tenders && tenders.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {tenders.map((t) => (
            <TenderCard key={t.id} tender={t} />
          ))}
        </div>
      )}
    </PageWrapper>
  );
}