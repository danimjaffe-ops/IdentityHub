import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { JiraConnectModal } from "./JiraConnectModal";
import { jiraApi } from "../api/jira";

vi.mock("../api/jira", () => ({
  jiraApi: { connect: vi.fn() },
}));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({ refreshUser: vi.fn().mockResolvedValue(undefined) }),
}));

async function fillForm() {
  await userEvent.type(screen.getByLabelText("Jira Site URL"), "https://x.atlassian.net");
  await userEvent.type(screen.getByLabelText("Atlassian Email"), "me@x.com");
  await userEvent.type(screen.getByLabelText("API Token"), "tok123");
}

describe("JiraConnectModal", () => {
  beforeEach(() => vi.clearAllMocks());

  it("submits the entered credentials and signals connection", async () => {
    vi.mocked(jiraApi.connect).mockResolvedValue({ connected: true, site_url: "https://x.atlassian.net" });
    const onConnected = vi.fn();
    render(<JiraConnectModal open onClose={() => {}} onConnected={onConnected} />);

    await fillForm();
    await userEvent.click(screen.getByRole("button", { name: "Connect to Jira" }));

    await waitFor(() => expect(onConnected).toHaveBeenCalled());
    expect(jiraApi.connect).toHaveBeenCalledWith(
      "https://x.atlassian.net",
      "me@x.com",
      "tok123"
    );
  });

  it("shows the error message when the connection fails", async () => {
    vi.mocked(jiraApi.connect).mockRejectedValue(new Error("Jira authentication failed"));
    const onConnected = vi.fn();
    render(<JiraConnectModal open onClose={() => {}} onConnected={onConnected} />);

    await fillForm();
    await userEvent.click(screen.getByRole("button", { name: "Connect to Jira" }));

    await waitFor(() =>
      expect(screen.getByText("Jira authentication failed")).toBeInTheDocument()
    );
    expect(onConnected).not.toHaveBeenCalled();
  });
});
