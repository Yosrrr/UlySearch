import apiClient from "./client";

export async function suggestConfiguration(description) {
  const { data } = await apiClient.post("/admin/ai-suggest", { description });
  return data;
}