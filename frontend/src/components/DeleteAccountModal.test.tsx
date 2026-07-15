import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DeleteAccountModal } from "./DeleteAccountModal";
import { authApi } from "../api/auth";

vi.mock("../api/auth", () => ({
  authApi: { deleteAccount: vi.fn() },
}));

const EMAIL = "me@example.com";

function renderModal(overrides: Partial<React.ComponentProps<typeof DeleteAccountModal>> = {}) {
  return render(
    <DeleteAccountModal
      open
      onClose={() => {}}
      onDeleted={() => {}}
      userEmail={EMAIL}
      {...overrides}
    />
  );
}

describe("DeleteAccountModal", () => {
  beforeEach(() => vi.clearAllMocks());

  it("keeps the delete button disabled until the email matches", async () => {
    renderModal();
    const button = screen.getByRole("button", { name: "Delete Account" });
    expect(button).toBeDisabled();

    await userEvent.type(screen.getByPlaceholderText(EMAIL), "wrong@example.com");
    expect(button).toBeDisabled();
  });

  it("enables and deletes once the email matches exactly", async () => {
    vi.mocked(authApi.deleteAccount).mockResolvedValue({ message: "deleted" });
    const onDeleted = vi.fn();
    renderModal({ onDeleted });

    await userEvent.type(screen.getByPlaceholderText(EMAIL), EMAIL);
    const button = screen.getByRole("button", { name: "Delete Account" });
    expect(button).toBeEnabled();

    await userEvent.click(button);
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
    expect(authApi.deleteAccount).toHaveBeenCalledOnce();
  });

  it("surfaces an error and does not signal deletion when the API fails", async () => {
    vi.mocked(authApi.deleteAccount).mockRejectedValue(new Error("Something broke"));
    const onDeleted = vi.fn();
    renderModal({ onDeleted });

    await userEvent.type(screen.getByPlaceholderText(EMAIL), EMAIL);
    await userEvent.click(screen.getByRole("button", { name: "Delete Account" }));

    await waitFor(() =>
      expect(screen.getByText("Something broke")).toBeInTheDocument()
    );
    expect(onDeleted).not.toHaveBeenCalled();
  });
});
