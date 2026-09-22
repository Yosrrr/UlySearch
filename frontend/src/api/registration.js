import apiClient from "./client";

export async function registerClient(payload) {
  const { data } = await apiClient.post("/register", payload, {
    timeout: 120000,
  });
  return data;
}

export async function suggestConfigurationPublic(description) {
  const { data } = await apiClient.post(
    "/admin/ai-suggest/public",
    { description },
    { timeout: 120000 }
  );
  return data;
}

