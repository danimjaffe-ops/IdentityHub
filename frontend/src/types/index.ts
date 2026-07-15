export interface User {
  id: number;
  email: string;
  has_jira_credentials: boolean;
  created_at: string;
}

export interface JiraProject {
  key: string;
  name: string;
  id: string;
}

export interface Ticket {
  // Listed tickets come live from Jira and include id/created_at; the create
  // response echoes only what Jira returns, so those two are optional.
  id?: number;
  jira_key: string;
  jira_id: string;
  project_key: string;
  summary: string;
  description: string | null;
  source: string;
  created_at?: string;
}

export interface ApiKeyInfo {
  id: number;
  key_prefix: string;
  label: string | null;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
}

export interface ApiError {
  error: string;
  message: string;
  details?: Record<string, string[]>;
}
