import { useState } from "react";
import { authApi } from "../api/auth";
import { Modal } from "./ui/Modal";
import { Input } from "./ui/Input";
import { Button } from "./ui/Button";
import { Alert } from "./ui/Alert";

interface DeleteAccountModalProps {
  open: boolean;
  onClose: () => void;
  onDeleted: () => void;
  userEmail: string;
}

export function DeleteAccountModal({
  open,
  onClose,
  onDeleted,
  userEmail,
}: DeleteAccountModalProps) {
  const [confirmation, setConfirmation] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirmed = confirmation === userEmail;

  const handleDelete = async () => {
    if (!confirmed) return;
    setError(null);
    setDeleting(true);
    try {
      await authApi.deleteAccount();
      onDeleted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete account");
      setDeleting(false);
    }
  };

  const handleClose = () => {
    setConfirmation("");
    setError(null);
    onClose();
  };

  return (
    <Modal open={open} onClose={handleClose} title="Delete Account">
      <div className="space-y-4">
        {error && <Alert variant="error" message={error} />}
        <p className="text-sm text-gray-600">
          This will permanently delete your account and all associated data
          including Jira credentials and API keys. This action cannot be undone.
        </p>
        <p className="text-sm text-gray-700">
          Type <span className="font-semibold">{userEmail}</span> to confirm:
        </p>
        <Input
          placeholder={userEmail}
          value={confirmation}
          onChange={(e) => setConfirmation(e.target.value)}
        />
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={!confirmed}
            loading={deleting}
          >
            Delete Account
          </Button>
        </div>
      </div>
    </Modal>
  );
}
