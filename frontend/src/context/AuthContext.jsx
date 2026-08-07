// src/context/AuthContext.jsx
import { createContext, useContext, useEffect, useState, useCallback } from "react";
import apiClient from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const token = localStorage.getItem("sotradies_token");
    if (!token) return null;
    const raw = localStorage.getItem("sotradies_user");
    return raw ? JSON.parse(raw) : null;
  });
  const [authReady, setAuthReady] = useState(() => !localStorage.getItem("sotradies_token"));

  useEffect(() => {
    const token = localStorage.getItem("sotradies_token");

    if (!token) {
      localStorage.removeItem("sotradies_user");
      return;
    }

    apiClient
      .get("/auth/me")
      .then(({ data }) => {
        localStorage.setItem("sotradies_user", JSON.stringify(data.user));
        setUser(data.user);
      })
      .catch(() => {
        localStorage.removeItem("sotradies_token");
        localStorage.removeItem("sotradies_user");
        setUser(null);
      })
      .finally(() => {
        setAuthReady(true);
      });
  }, []);

  const signIn = useCallback(async (email, password) => {
    const { data } = await apiClient.post("/auth/login", { email, password });
    localStorage.setItem("sotradies_token", data.access_token);
    localStorage.setItem("sotradies_user", JSON.stringify(data.user));
    setUser(data.user);
    return data;
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem("sotradies_token");
    localStorage.removeItem("sotradies_user");
    setUser(null);
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