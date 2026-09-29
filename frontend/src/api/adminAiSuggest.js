import apiClient from "./client";

export async function suggestConfiguration(payload) {
  const body =
    typeof payload === "string"
      ? { description: payload }
      : payload;

  const { data } = await apiClient.post(
    "/admin/ai-suggest",
    body,
    {
      timeout: 900000,
    }
  );

  return data;
}