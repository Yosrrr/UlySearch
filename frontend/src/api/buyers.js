// src/api/buyers.js
import apiClient from "./client";

export async function getBuyers() {
  const { data } = await apiClient.get("/buyers");
  return data;
}

export async function createBuyer(payload) {
  const { data } = await apiClient.post("/buyers", payload);
  return data;
}

export async function importBuyersFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post("/buyers/import", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function updateBuyer(id, payload) {
  const { data } = await apiClient.patch(`/buyers/${id}`, payload);
  return data;
}
export async function importBuyersScan(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post("/buyers/import-scan", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}