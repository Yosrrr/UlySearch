// src/components/tender/DecisionBadge.jsx
// Décision non définitive : affichée à côté du statut commercial.
export default function DecisionBadge({ decision }) {
  if (decision === "a_verifier") {
    return (
      <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
            title="L'IA était indisponible : retenue sur mot-clé seul, réévaluée automatiquement au prochain run">
        Provisoire
      </span>
    );
  }
  if (decision === "a_examiner") {
    return (
      <span className="rounded bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-800"
            title="Aucun mot-clé du client, mais l'IA la juge pertinente : à examiner, jamais retenue automatiquement">
        À examiner
      </span>
    );
  }
  return null;
}
