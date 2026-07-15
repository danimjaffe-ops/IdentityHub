import { api } from "./client";
import type { User } from "../types";

export const authApi = {
  register: (email: string, password: string, confirmPassword: string) =>
    api.post<{ user: User }>("/auth/register", {
      email,
      password,
      confirm_password: confirmPassword,
    }),
  login: (email: string, password: string) =>
    api.post<{ user: User }>("/auth/login", { email, password }),
  logout: () => api.post<{ message: string }>("/auth/logout"),
  deleteAccount: () => api.delete<{ message: string }>("/auth/account"),
  me: () => api.get<User>("/auth/me"),
};
