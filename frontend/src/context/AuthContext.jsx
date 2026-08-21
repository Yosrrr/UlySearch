// src/context/AuthContext.jsx
import { createContext, useContext, useEffect, useState, useCallback } from "react";
import apiClient from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // On garde uniquement les infos utilisateur (non sensibles) en localStorage
  // pour un affichage instantané. Le token, lui, vit dans un cookie httpOnly
  // que le JS ne peut pas lire — c'est le but de S8.
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("sotradies_user");
    return raw ? JSON.parse(raw) : null;
  });
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    // Valide la session au montage : le cookie httpOnly est envoyé
    // automatiquement grâce à withCredentials.
    apiClient
      .get("/auth/me")
      .then(({ data }) => {
        localStorage.setItem("sotradies_user", JSON.stringify(data.user));
        setUser(data.user);
      })
      .catch((error) => {
        // 401 = pas de session valide (cookie absent/expiré)
        if (error.response?.status === 401) {
          localStorage.removeItem("sotradies_user");
          setUser(null);
        }
        // Erreur réseau : on garde l'état local, on ne déconnecte pas
      })
      .finally(() => {
        setAuthReady(true);
      });
  }, []);

  const signIn = useCallback(async (email, password) => {
    const { data } = await apiClient.post("/auth/login", { email, password });
    // Plus de token à stocker : le serveur l'a posé en cookie httpOnly
    localStorage.setItem("sotradies_user", JSON.stringify(data.user));
    setUser(data.user);
    return data;
  }, []);

  const signOut = useCallback(async () => {
  try {
    await apiClient.post("/auth/logout");
  } catch {
    // même si l'appel échoue, on nettoie l'état local
  }
  localStorage.removeItem("sotradies_user");
  setUser(null);
  window.location.href = "/login";
}, []);

  return (
    <AuthContext.Provider value={{ user, signIn, signOut, isAuthenticated: Boolean(user), authReady }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans un <AuthProvider>");
  return ctx;
}