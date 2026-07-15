import { api } from "./client";
import type { Ticket } from "../types";

export const ticketsApi = {
  create: (projectKey: string, summary: string, description: string) =>
    api.post<Ticket>("/tickets", { project_key: projectKey, summary, description }),
  list: (projectKey: string, limit = 10) =>
    api.get<{ tickets: Ticket[]; unavailable: boolean }>(
      `/tickets?project_key=${encodeURIComponent(projectKey)}&limit=${limit}`
    ),
};
