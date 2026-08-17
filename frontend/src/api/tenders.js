// src/api/tenders.js
import apiClient from "./client";
import { downloadBlob } from "../utils/download";

export async function getTenders(filters = {}) {
  const { data } = await apiClient.get("/tenders", { params: filters });
  return data;
}

export async function updateTenderStatus(id, statut) {
  const { data } = await apiClient.patch(`/tenders/${id}`, { statut });
  return data;
}

export async function getTender(id) {
  const { data } = await apiClient.get(`/tenders/${id}`);
  return data;
}
export async function getRejectedTenders() {
  const { data } = await apiClient.get("/tenders/rejected");
  return data;
}
export async function exportTenders(filters, format) {
  const response = await apiClient.get("/tenders/export", {
    params: { ...filters, format },
    responseType: "blob",
  });
  downloadBlob(response.data, `marches-sotradies.${format}`);
}