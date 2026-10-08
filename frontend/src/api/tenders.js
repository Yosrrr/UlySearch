// src/api/tenders.js
import apiClient from "./client";



function asPage(data, limit = 50, offset = 0) {
  if (Array.isArray(data)) {
    return { items: data, total: data.length, limit, offset };
  }
  return {
    items: data.items ?? [],
    total: data.total ?? 0,
    limit: data.limit ?? limit,
    offset: data.offset ?? offset,
  };
}
export async function fetchTenders(params = {}) {
  const { limit = 50, offset = 0, ...rest } = params;
  const { data } = await apiClient.get("/tenders", {
    params: {
      ...rest,
      limit,
      offset,
      search: rest.search || undefined,
      commercial: rest.commercial || undefined,
      statut: rest.statut || undefined,
      categorie: rest.categorie || undefined,
      score_min: rest.score_min ?? undefined,
      include_rejected: rest.include_rejected ?? false,
    },
  });
  if (Array.isArray(data)) {
    return { items: data, total: data.length, limit, offset };
  }
  return data;
}

export async function fetchRejectedTenders({ limit = 50, offset = 0 } = {}) {
  const { data } = await apiClient.get("/tenders/rejected", {
    params: { limit, offset },
  });
  return asPage(data, limit, offset);
}

export async function fetchTender(id) {
  const { data } = await apiClient.get(`/tenders/${id}`);
  return data;
}

export async function updateTenderStatus(id, statut) {
  const { data } = await apiClient.patch(`/tenders/${id}`, { statut });
  return data;
}

export async function updateTenderFeedback(id, feedback) {
  const { data } = await apiClient.patch(`/tenders/${id}/feedback`, {
    feedback,
  });
  return data;
}

export async function exportTenders(format, params = {}) {
  const response = await apiClient.get("/tenders/export", {
    params: { format, ...params },
    responseType: "blob",
  });
  return response.data;
}
export async function getTenders(filters = {}) {
  const { data } = await apiClient.get("/tenders", { params: filters });
  return data;
}

export async function repêcherTender(id) {
  const { data } = await apiClient.patch(`/tenders/${id}`, {
    decision: "retenu",
    // ou le champ exact attendu par le backend l.201/428
  });
  return data;
}


export async function getRejectedTenders() {
  const { data } = await apiClient.get("/tenders/rejected");
  return data;
}


