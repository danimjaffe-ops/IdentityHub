import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { jiraApi } from "../api/jira";
import { keysApi } from "../api/keys";
import type { ApiKeyInfo } from "../types";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Spinner } from "../components/ui/Spinner";
import { JiraConnectModal } from "../components/JiraConnectModal";
import { DeleteAccountModal } from "../components/DeleteAccountModal";
import { ApiKeyModal } from "../components/ApiKeyModal";

export function SettingsPage() {
  const { user, clearSession, refreshUser } = useAuth();
  const navigate = useNavigate();

  const [keys, setKeys] = useState<ApiKeyInfo[]>([]);
  const [loadingKeys, setLoadingKeys] = useState(true);
  const [newKeyLabel, setNewKeyLabel] = useState("");
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [keyError, setKeyError] = useState<string | null>(null);

  const [jiraStatus, setJiraStatus] = useState<{
    connected: boolean;
    site_url: string | null;
    email_masked: string | null;
  } | null>(null);
  const [jiraModalOpen, setJiraModalOpen] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [jiraError, setJiraError] = useState<string | null>(null);

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  useEffect(() => {
    keysApi
      .list()
      .then((data) => setKeys(data.keys))
      .catch(() => setKeys([]))
      .finally(() => setLoadingKeys(false));
    jiraApi.status().then(setJiraStatus);
  }, []);

  const handleGenerate = async () => {
    setKeyError(null);
    setGeneratedKey(null);
    setGenerating(true);
    try {
      const result = await keysApi.generate(newKeyLabel || undefined);
      setGeneratedKey(result.key);
      setNewKeyLabel("");
      const updated = await keysApi.list();
      setKeys(updated.keys);
    } catch (err) {
      setKeyError(err instanceof Error ? err.message : "Failed to generate key");
    } finally {
      setGenerating(false);
    }
  };

  const handleRevoke = async (id: number) => {
    try {
      await keysApi.revoke(id);
      const updated = await keysApi.list();
      setKeys(updated.keys);
    } catch (err) {
      setKeyError(err instanceof Error ? err.message : "Failed to revoke key");
    }
  };

  const handleDisconnect = async () => {
    setJiraError(null);
    setDisconnecting(true);
    try {
      await jiraApi.disconnect();
      await refreshUser();
      setJiraStatus({ connected: false, site_url: null, email_masked: null });
    } catch (err) {
      setJiraError(err instanceof Error ? err.message : "Failed to disconnect");
    } finally {
      setDisconnecting(false);
    }
  };

  const handleJiraConnected = () => {
    setJiraModalOpen(false);
    jiraApi.status().then(setJiraStatus);
    navigate("/");
  };

  const handleAccountDeleted = () => {
    clearSession();
    navigate("/login");
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Settings</h2>

      {/* Account & Integrations */}
      <Card title="Account & Integrations">
        <div>
          <p className="text-sm font-medium text-gray-900">{user?.email}</p>
          <p className="text-xs text-gray-500">
            Member since {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
          </p>
        </div>

        <hr className="my-5 border-gray-200" />

        {jiraError && (
          <div className="mb-4">
            <Alert variant="error" message={jiraError} onDismiss={() => setJiraError(null)} />
          </div>
        )}
        {jiraStatus ? (
          <div>
            <p className="text-sm font-medium text-gray-900 mb-3">Jira Connection</p>
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Badge variant={jiraStatus.connected ? "success" : "warning"}>
                    {jiraStatus.connected ? "Connected" : "Not Connected"}
                  </Badge>
                </div>
                {jiraStatus.connected && (
                  <>
                    <p className="mt-1 text-sm text-gray-600">{jiraStatus.site_url}</p>
                    <p className="text-sm text-gray-500">{jiraStatus.email_masked}</p>
                  </>
                )}
              </div>
              <div className="flex items-center gap-2">
                {jiraStatus.connected && (
                  <Button
                    variant="ghost"
                    onClick={handleDisconnect}
                    loading={disconnecting}
                  >
                    Disconnect
                  </Button>
                )}
                <Button
                  variant={jiraStatus.connected ? "secondary" : "primary"}
                  onClick={() => setJiraModalOpen(true)}
                >
                  {jiraStatus.connected ? "Update" : "Connect"}
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <Spinner />
        )}

        <hr className="my-5 border-gray-200" />

        <div className="flex justify-end">
          <Button variant="ghost" onClick={() => setDeleteModalOpen(true)}>
            Delete account
          </Button>
        </div>
      </Card>

      <JiraConnectModal
        open={jiraModalOpen}
        onClose={() => setJiraModalOpen(false)}
        onConnected={handleJiraConnected}
      />

      <DeleteAccountModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        onDeleted={handleAccountDeleted}
        userEmail={user?.email || ""}
      />

      <ApiKeyModal
        open={generatedKey !== null}
        onClose={() => setGeneratedKey(null)}
        apiKey={generatedKey || ""}
      />

      {/* Developer */}
      <Card title="Developer">
        {keyError && (
          <div className="mb-4">
            <Alert variant="error" message={keyError} onDismiss={() => setKeyError(null)} />
          </div>
        )}

        <div className="flex items-end gap-3 mb-4">
          <div className="flex-1">
            <Input
              label="Label (optional)"
              placeholder="e.g., CI Pipeline Key"
              value={newKeyLabel}
              onChange={(e) => setNewKeyLabel(e.target.value)}
            />
          </div>
          <Button onClick={handleGenerate} loading={generating}>
            Generate New Key
          </Button>
        </div>

        {loadingKeys ? (
          <Spinner centered />
        ) : keys.length === 0 ? (
          <p className="text-sm text-gray-500">No API keys generated yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 pr-4 font-medium text-gray-600">Prefix</th>
                  <th className="text-left py-2 pr-4 font-medium text-gray-600">Label</th>
                  <th className="text-left py-2 pr-4 font-medium text-gray-600">Created</th>
                  <th className="text-right py-2 font-medium text-gray-600"></th>
                </tr>
              </thead>
              <tbody>
                {keys.map((k) => (
                  <tr key={k.id} className="border-b border-gray-100">
                    <td className="py-2 pr-4 font-mono text-gray-900">{k.key_prefix}...</td>
                    <td className="py-2 pr-4 text-gray-600">{k.label || "—"}</td>
                    <td className="py-2 pr-4 text-gray-500">
                      {new Date(k.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-2 text-right">
                      <Button
                        variant="destructive"
                        onClick={() => handleRevoke(k.id)}
                      >
                        Revoke
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <hr className="my-5 border-gray-200" />

        <p className="text-sm font-medium text-gray-900 mb-3">REST API Usage</p>
        <p className="text-sm text-gray-600 mb-3">
          Use your API key to create tickets programmatically:
        </p>
        <pre className="bg-gray-50 rounded-lg p-4 text-xs overflow-x-auto text-gray-800">
{`curl -X POST http://localhost:5000/api/tickets \\
  -H "X-API-Key: YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"project_key":"KEY","summary":"Finding title","description":"Details"}'`}
        </pre>
        <p className="mt-4 text-sm text-gray-600">
          Explore every endpoint in the{" "}
          <a
            href="/api/docs/"
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-blue-600 hover:text-blue-500"
          >
            interactive API reference →
          </a>
        </p>
      </Card>
    </div>
  );
}
