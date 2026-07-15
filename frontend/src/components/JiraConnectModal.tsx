import { useState, type FormEvent } from "react";
import { useAuth } from "../hooks/useAuth";
import { jiraApi } from "../api/jira";
import { Modal } from "./ui/Modal";
import { Input } from "./ui/Input";
import { Button } from "./ui/Button";
import { Alert } from "./ui/Alert";

interface JiraConnectModalProps {
  open: boolean;
  onClose: () => void;
  onConnected: () => void;
}

export function JiraConnectModal({ open, onClose, onConnected }: JiraConnectModalProps) {
  const { refreshUser } = useAuth();
  const [siteUrl, setSiteUrl] = useState("");
  const [email, setEmail] = useState("");
  const [apiToken, setApiToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleConnect = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await jiraApi.connect(siteUrl, email, apiToken);
      await refreshUser();
      setSiteUrl("");
      setEmail("");
      setApiToken("");
      onConnected();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect to Jira");
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setError(null);
    setSiteUrl("");
    setEmail("");
    setApiToken("");
    onClose();
  };

  return (
    <Modal open={open} onClose={handleClose} title="Connect Jira Workspace">
      {error && (
        <div className="mb-4">
          <Alert variant="error" message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      <p className="text-sm text-gray-600 mb-4">
        Link your Atlassian workspace to create and track NHI finding tickets.
      </p>

      <form onSubmit={handleConnect} className="space-y-4">
        <Input
          label="Jira Site URL"
          type="url"
          placeholder="https://your-org.atlassian.net"
          value={siteUrl}
          onChange={(e) => setSiteUrl(e.target.value)}
          required
          tooltip="Log into Jira and copy the URL from your browser address bar. It looks like https://your-org.atlassian.net — not id.atlassian.com."
        />
        <Input
          label="Atlassian Email"
          type="email"
          placeholder="you@your-org.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          tooltip="The email address you use to sign in to your Atlassian account."
        />
        <Input
          label="API Token"
          type="password"
          placeholder="Paste your Atlassian API token"
          value={apiToken}
          onChange={(e) => setApiToken(e.target.value)}
          required
          tooltip="Go to id.atlassian.com → Security → API tokens → Create API token. Copy and paste the generated token here."
        />
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            Connect to Jira
          </Button>
        </div>
      </form>
    </Modal>
  );
}
