import apiClient from "./client";

export async function getCompanies() {
  const { data } = await apiClient.get("/admin/companies");
  return data;
}