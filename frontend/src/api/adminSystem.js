// src/api/adminSystem.js
import apiClient from "./client";

export async function getSystemStatus() {
  const { data } = await apiClient.get("/admin/system/status");
  return data;
}

export async function startWorker() {
  const { data } = await apiClient.post("/admin/system/worker/start");
  return data;
}
export async function stopWorker() {
  const { data } = await apiClient.post("/admin/system/worker/stop");
  return data;
}
export async function startBeat() {
  const { data } = await apiClient.post("/admin/system/beat/start");
  return data;
}
export async function stopBeat() {
  const { data } = await apiClient.post("/admin/system/beat/stop");
  return data;
}