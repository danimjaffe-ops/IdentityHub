import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiKeyModal } from "./ApiKeyModal";

describe("ApiKeyModal", () => {
  it("shows the key and the one-time warning", () => {
    render(<ApiKeyModal open onClose={() => {}} apiKey="nhk_abc123" />);
    expect(screen.getByText("nhk_abc123")).toBeInTheDocument();
    expect(screen.getByText(/won't be shown again/i)).toBeInTheDocument();
  });

  it("copies the key to the clipboard and confirms", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(<ApiKeyModal open onClose={() => {}} apiKey="nhk_secret" />);
    await userEvent.click(screen.getByRole("button", { name: "Copy" }));

    expect(writeText).toHaveBeenCalledWith("nhk_secret");
    expect(screen.getByRole("button", { name: "Copied!" })).toBeInTheDocument();
  });

  it("renders nothing when closed", () => {
    render(<ApiKeyModal open={false} onClose={() => {}} apiKey="hidden" />);
    expect(screen.queryByText("hidden")).toBeNull();
  });
});
