// src/api/audit.js
import apiClient from "./client";
import { downloadBlob } from "../utils/download";

export async function getAuditLog(filters = {}) {
  const { data } = await apiClient.get("/admin/audit", { params: filters });
  return data;
}

export async function exportAuditLog(filters, format) {
  const response = await apiClient.get("/admin/audit/export", {
    params: { ...filters, format },
    responseType: "blob",
  });
  downloadBlob(response.data, `audit-log-sotradies.${format}`);
}