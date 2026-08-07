// src/api/adminUsers.js
import apiClient from "./client";

export async function getUsers() {
  const { data } = await apiClient.get("/admin/users");
  return data;
}

export async function createUser(payload) {
  const { data } = await apiClient.post("/admin/users", payload);
  return data;
}

export async function updateUser(id, payload) {
  const { data } = await apiClient.put(`/admin/users/${id}`, payload);
  return data;
}

export async function deleteUser(id) {
  await apiClient.delete(`/admin/users/${id}`);
}