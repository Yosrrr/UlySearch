// src/context/AuthContext.jsx
import { createContext, useContext, useState, useCallback } from "react";
import apiClient from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("sotradies_user");
    return raw ? JSON.parse(raw) : null;
  });

  const signIn = useCallback(async (email, password) => {
    try {
      const { data } = await apiClient.post("/auth/login", { email, password });
      localStorage.setItem("sotradies_token", data.access_token);
      localStorage.setItem("sotradies_user", JSON.stringify(data.user));
      setUser(data.user);
      return data;
    } catch (err) {
      // Le backend n'a pas encore de route /auth/login → mode démo temporaire.
      // À retirer dès que la vraie authentification est branchée côté FastAPI.
      console.warn("[démo] /auth/login indisponible — connexion de test utilisée.");
      const demoUser = { email, nom: "Utilisateur de test" };
      localStorage.setItem("sotradies_token", "demo-token");
      localStorage.setItem("sotradies_user", JSON.stringify(demoUser));
      setUser(demoUser);
      return { user: demoUser };
    }
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem("sotradies_token");
    localStorage.removeItem("sotradies_user");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, signIn, signOut, isAuthenticated: Boolean(user) }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans un <AuthProvider>");
  return ctx;
}