// ============================================================
// frontend/src/api/adminSources.js
// ============================================================

import apiClient from "./client";

export async function getSources() {
  const { data } = await apiClient.get("/admin/sources");
  return data;
}

export async function createSource(payload) {
  const { data } = await apiClient.post("/admin/sources", payload);
  return data;
}

export async function updateSource(id, payload) {
  const { data } = await apiClient.put(`/admin/sources/${id}`, payload);
  return data;
}

export async function deleteSource(id) {
  const { data } = await apiClient.delete(`/admin/sources/${id}`);
  return data;
}

export async function toggleSource(id) {
  const { data } = await apiClient.patch(`/admin/sources/${id}/toggle`);
  return data;
}

export async function testSource(id) {
  const { data } = await apiClient.post(`/admin/sources/${id}/test`);
  return data;
}