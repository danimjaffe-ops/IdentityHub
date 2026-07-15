import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./AuthContext";
import { useAuth } from "../hooks/useAuth";
import { authApi } from "../api/auth";
import type { User } from "../types";

vi.mock("../api/auth", () => ({
  authApi: {
    me: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
    deleteAccount: vi.fn(),
  },
}));

const USER: User = {
  id: 1,
  email: "me@example.com",
  has_jira_credentials: false,
  created_at: "2026-07-15T00:00:00Z",
};

function Consumer() {
  const { user, loading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="status">
        {loading ? "loading" : user ? user.email : "anon"}
      </span>
      <button onClick={() => login("a@b.com", "pw")}>login</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

function renderProvider() {
  return render(
    <AuthProvider>
      <Consumer />
    </AuthProvider>
  );
}

describe("AuthContext", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads the current user on mount", async () => {
    vi.mocked(authApi.me).mockResolvedValue(USER);
    renderProvider();
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("me@example.com")
    );
  });

  it("stays anonymous when /me fails", async () => {
    vi.mocked(authApi.me).mockRejectedValue(new Error("401"));
    renderProvider();
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("anon")
    );
  });

  it("clears the user when an auth:unauthorized event fires", async () => {
    vi.mocked(authApi.me).mockResolvedValue(USER);
    renderProvider();
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("me@example.com")
    );

    act(() => {
      window.dispatchEvent(new CustomEvent("auth:unauthorized", { detail: "session_expired" }));
    });

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("anon")
    );
  });

  it("login sets the user", async () => {
    vi.mocked(authApi.me).mockRejectedValue(new Error("401"));
    vi.mocked(authApi.login).mockResolvedValue({ user: USER });
    renderProvider();
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("anon")
    );

    await userEvent.click(screen.getByText("login"));
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("me@example.com")
    );
  });

  it("logout clears the user", async () => {
    vi.mocked(authApi.me).mockResolvedValue(USER);
    vi.mocked(authApi.logout).mockResolvedValue({ message: "ok" });
    renderProvider();
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("me@example.com")
    );

    await userEvent.click(screen.getByText("logout"));
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("anon")
    );
  });
});
