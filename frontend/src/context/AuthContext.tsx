import { createContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { authApi } from "../api/auth";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, confirmPassword: string) => Promise<void>;
  logout: () => Promise<void>;
  clearSession: () => void;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const u = await authApi.me();
      setUser(u);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    refreshUser().finally(() => setLoading(false));
  }, [refreshUser]);

  // Drop client-side auth state whenever any request comes back 401 (e.g. the
  // absolute session timeout has elapsed), so ProtectedRoute sends the user to
  // the login screen instead of leaving a dead, logged-in-looking UI.
  useEffect(() => {
    const handleUnauthorized = () => setUser(null);
    window.addEventListener("auth:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("auth:unauthorized", handleUnauthorized);
  }, []);

  const login = async (email: string, password: string) => {
    const { user: u } = await authApi.login(email, password);
    setUser(u);
  };

  const register = async (email: string, password: string, confirmPassword: string) => {
    const { user: u } = await authApi.register(email, password, confirmPassword);
    setUser(u);
  };

  const logout = async () => {
    await authApi.logout();
    setUser(null);
  };

  const clearSession = useCallback(() => {
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, clearSession, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}
