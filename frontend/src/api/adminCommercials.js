// src/api/adminCommercials.js
import apiClient from "./client";

export const getCommercials = () =>
  apiClient.get("/admin/commercials").then((r) => r.data);

export const createCommercial = (payload) =>
  apiClient.post("/admin/commercials", payload).then((r) => r.data);

export const updateCommercial = (id, payload) =>
  apiClient.patch(`/admin/commercials/${id}`, payload).then((r) => r.data);