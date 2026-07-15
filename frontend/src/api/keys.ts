import { api } from "./client";
import type { ApiKeyInfo } from "../types";

export const keysApi = {
  generate: (label?: string) =>
    api.post<{ key: string } & ApiKeyInfo>("/keys", { label }),
  list: () => api.get<{ keys: ApiKeyInfo[] }>("/keys"),
  revoke: (id: number) => api.delete<{ message: string }>(`/keys/${id}`),
};
