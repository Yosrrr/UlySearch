// src/api/client.js
import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  timeout: 120000,
  withCredentials: true, // S8 : envoie automatiquement le cookie httpOnly
});

// Plus d'interceptor de requête : le cookie httpOnly est géré par le navigateur,
// le JS n'a plus jamais accès au token (protection XSS).

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
   if (error.response?.status === 401) {
      localStorage.removeItem("veilleao_user");
      localStorage.removeItem("sotradies_user");
      if (
        !window.location.pathname.includes("/register") &&
        !window.location.pathname.includes("/login")
      ) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;