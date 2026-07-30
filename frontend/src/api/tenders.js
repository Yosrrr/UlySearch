// src/api/tenders.js
import apiClient from "./client";

export async function getTenders(filters = {}) {
  const { data } = await apiClient.get("/tenders", { params: filters });
  return data;
}

export async function getTender(id) {
  const { data } = await apiClient.get(`/tenders/${id}`);
  return data;
}