import { useState } from "react";
import { Modal } from "./ui/Modal";
import { Button } from "./ui/Button";
import { Alert } from "./ui/Alert";

interface ApiKeyModalProps {
  open: boolean;
  onClose: () => void;
  apiKey: string;
}

export function ApiKeyModal({ open, onClose, apiKey }: ApiKeyModalProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleClose = () => {
    setCopied(false);
    onClose();
  };

  return (
    <Modal open={open} onClose={handleClose} title="New API Key">
      <div className="space-y-4">
        <Alert
          variant="warning"
          message="Save this key now — it won't be shown again."
        />
        <div className="flex items-center gap-2">
          <code className="flex-1 min-w-0 bg-gray-100 px-3 py-2 rounded text-sm font-mono whitespace-nowrap overflow-x-auto">
            {apiKey}
          </code>
          <Button size="sm" onClick={handleCopy} className="shrink-0 w-[5.5rem]">
            {copied ? "Copied!" : "Copy"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
