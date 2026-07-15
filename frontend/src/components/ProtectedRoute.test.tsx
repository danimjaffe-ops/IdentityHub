import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AuthContext } from "../context/AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";
import type { User } from "../types";

const noop = async () => {};

function makeValue(overrides: Partial<React.ComponentProps<typeof AuthContext.Provider>["value"]>) {
  return {
    user: null as User | null,
    loading: false,
    login: noop,
    register: noop,
    logout: noop,
    clearSession: () => {},
    refreshUser: noop,
    ...overrides,
  };
}

function renderWith(value: ReturnType<typeof makeValue>) {
  return render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<div>protected content</div>} />
          </Route>
          <Route path="/login" element={<div>login page</div>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

const A_USER: User = {
  id: 1,
  email: "a@b.com",
  has_jira_credentials: false,
  created_at: "",
};

describe("ProtectedRoute", () => {
  it("shows a spinner while auth is loading", () => {
    const { container } = renderWith(makeValue({ loading: true }));
    expect(screen.queryByText("protected content")).toBeNull();
    expect(screen.queryByText("login page")).toBeNull();
    expect(container.querySelector(".animate-spin")).toBeTruthy();
  });

  it("redirects to /login when unauthenticated", () => {
    renderWith(makeValue({ user: null, loading: false }));
    expect(screen.getByText("login page")).toBeInTheDocument();
    expect(screen.queryByText("protected content")).toBeNull();
  });

  it("renders the protected outlet when authenticated", () => {
    renderWith(makeValue({ user: A_USER, loading: false }));
    expect(screen.getByText("protected content")).toBeInTheDocument();
  });
});
