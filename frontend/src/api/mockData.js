// src/api/mockData.js
// Données de démonstration — à retirer une fois le backend branché.

export const MOCK_DASHBOARD = {
  stats: {
    nouveaux_marches: 14,
    retenus: 6,
    assignes: 5,
  },
  alertes_du_jour: [
    { id: "t-1", objet: "Acquisition de camions bennes — commune de Sfax", score: 92, commercial: "Ramzi Trabelsi" },
    { id: "t-2", objet: "Chariots élévateurs — Office des Ports Nationaux", score: 88, commercial: "Salah Gharbi" },
  ],
  repartition_commerciaux: [
    { commercial: "Ramzi Trabelsi", marque: "IVECO", nb_marches: 3 },
    { commercial: "Zied Hajji", marque: "CASE", nb_marches: 1 },
    { commercial: "Salah Gharbi", marque: "CG Est Manutention", nb_marches: 2 },
  ],
  dernier_scraping: {
    heure: "2026-07-30T07:14:00",
    sources_ok: 3,
    sources_total: 3,
    erreurs: [],
  },
};