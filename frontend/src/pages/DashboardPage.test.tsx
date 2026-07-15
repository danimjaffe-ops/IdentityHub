import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "./DashboardPage";
import { useAuth } from "../hooks/useAuth";
import { jiraApi } from "../api/jira";
import { ticketsApi } from "../api/tickets";
import type { User } from "../types";

vi.mock("../hooks/useAuth", () => ({ useAuth: vi.fn() }));
vi.mock("../api/jira", () => ({
  jiraApi: { projects: vi.fn(), status: vi.fn() },
}));
vi.mock("../api/tickets", () => ({
  ticketsApi: { list: vi.fn(), create: vi.fn() },
}));

function userWith(jira: boolean): User {
  return { id: 1, email: "me@example.com", has_jira_credentials: jira, created_at: "" };
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>
  );
}

async function selectProject(label: string) {
  // The project list loads asynchronously (spinner first), so wait for the
  // Select trigger before opening it.
  await userEvent.click(await screen.findByText("Select a project"));
  await userEvent.click(await screen.findByText(label));
}

describe("DashboardPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("prompts to connect Jira when no workspace is linked", () => {
    vi.mocked(useAuth).mockReturnValue({ user: userWith(false) } as ReturnType<typeof useAuth>);
    renderDashboard();
    expect(screen.getByText("Connect your Jira workspace")).toBeInTheDocument();
  });

  describe("when Jira is connected", () => {
    beforeEach(() => {
      vi.mocked(useAuth).mockReturnValue({ user: userWith(true) } as ReturnType<typeof useAuth>);
      vi.mocked(jiraApi.projects).mockResolvedValue({
        projects: [{ key: "TEST", name: "Test Project", id: "1" }],
      });
      vi.mocked(jiraApi.status).mockResolvedValue({
        connected: true,
        site_url: "https://x.atlassian.net",
        email_masked: "m***@example.com",
      });
    });

    it("renders recent tickets from Jira for the selected project", async () => {
      vi.mocked(ticketsApi.list).mockResolvedValue({
        unavailable: false,
        tickets: [
          {
            jira_key: "TEST-1",
            jira_id: "10001",
            project_key: "TEST",
            summary: "A live ticket",
            description: null,
            source: "jira",
            created_at: new Date().toISOString(),
          },
        ],
      });

      renderDashboard();
      await selectProject("TEST — Test Project");

      expect(await screen.findByText("TEST-1")).toBeInTheDocument();
      expect(screen.getByText("A live ticket")).toBeInTheDocument();
      // Fetched scoped to the selected project.
      expect(ticketsApi.list).toHaveBeenCalledWith("TEST");
    });

    it("shows the unavailable warning when Jira is down", async () => {
      vi.mocked(ticketsApi.list).mockResolvedValue({ unavailable: true, tickets: [] });

      renderDashboard();
      await selectProject("TEST — Test Project");

      expect(await screen.findByText(/Jira is currently unavailable/i)).toBeInTheDocument();
    });

    it("shows an empty state when the project has no tickets", async () => {
      vi.mocked(ticketsApi.list).mockResolvedValue({ unavailable: false, tickets: [] });

      renderDashboard();
      await selectProject("TEST — Test Project");

      expect(await screen.findByText("No tickets found for this project.")).toBeInTheDocument();
    });
  });
});
