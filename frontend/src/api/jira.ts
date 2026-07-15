import { api } from "./client";
import type { JiraProject } from "../types";

export const jiraApi = {
  connect: (siteUrl: string, email: string, apiToken: string) =>
    api.post<{ site_url: string; connected: boolean }>("/jira/credentials", {
      site_url: siteUrl,
      email,
      api_token: apiToken,
    }),
  status: () =>
    api.get<{ connected: boolean; site_url: string | null; email_masked: string | null }>("/jira/status"),
  disconnect: () => api.delete<{ message: string }>("/jira/credentials"),
  projects: () => api.get<{ projects: JiraProject[] }>("/jira/projects"),
};
