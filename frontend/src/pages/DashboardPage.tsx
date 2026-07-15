import { useState, useEffect, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { jiraApi } from "../api/jira";
import { ticketsApi } from "../api/tickets";
import { useApi } from "../hooks/useApi";
import type { JiraProject, Ticket } from "../types";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Textarea } from "../components/ui/Textarea";
import { Select } from "../components/ui/Select";
import { Button } from "../components/ui/Button";
import { Alert } from "../components/ui/Alert";
import { Spinner } from "../components/ui/Spinner";

function timeAgo(dateStr?: string): string {
  if (!dateStr) return "";
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const jiraConnected = user?.has_jira_credentials ?? false;

  const { data: projectsData, loading: loadingProjects } = useApi(
    () => (jiraConnected ? jiraApi.projects() : Promise.resolve({ projects: [] })),
    [jiraConnected]
  );
  const [siteUrl, setSiteUrl] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState("");
  const [summary, setSummary] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [ticketsUnavailable, setTicketsUnavailable] = useState(false);
  const [loadingTickets, setLoadingTickets] = useState(false);

  useEffect(() => {
    if (jiraConnected) {
      jiraApi.status().then((s) => setSiteUrl(s.site_url));
    }
  }, [jiraConnected]);

  const projects: JiraProject[] = projectsData?.projects ?? [];
  const projectOptions = projects.map((p) => ({
    value: p.key,
    label: `${p.key} — ${p.name}`,
  }));

  useEffect(() => {
    if (!selectedProject) return;
    setLoadingTickets(true);
    ticketsApi
      .list(selectedProject)
      .then((data) => {
        setTickets(data.tickets);
        setTicketsUnavailable(data.unavailable);
      })
      .catch(() => {
        setTickets([]);
        setTicketsUnavailable(false);
      })
      .finally(() => setLoadingTickets(false));
  }, [selectedProject]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedProject) return;
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      const ticket = await ticketsApi.create(selectedProject, summary, description);
      setSuccess(`Ticket ${ticket.jira_key} created successfully`);
      setSummary("");
      setDescription("");
      setLoadingTickets(true);
      ticketsApi
        .list(selectedProject)
        .then((data) => {
          setTickets(data.tickets);
          setTicketsUnavailable(data.unavailable);
        })
        .finally(() => setLoadingTickets(false));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create ticket");
    } finally {
      setSubmitting(false);
    }
  };

  if (!jiraConnected) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <Card>
          <div className="text-center py-8">
            <div className="text-4xl mb-4">🔗</div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Connect your Jira workspace
            </h3>
            <p className="text-sm text-gray-600 mb-6 max-w-md mx-auto">
              Link your Atlassian workspace in Settings to start creating and tracking NHI finding tickets.
            </p>
            <Button onClick={() => navigate("/settings")}>
              Go to Settings
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (loadingProjects) {
    return <Spinner size="lg" centered />;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>

      {projects.length === 0 ? (
        <Alert variant="info" message="No projects found in your Jira workspace." />
      ) : (
        <>
          <div className="max-w-xs">
            <Select
              label="Jira Project"
              options={projectOptions}
              placeholder="Select a project"
              value={selectedProject}
              onChange={setSelectedProject}
            />
          </div>

          {!selectedProject ? (
            <Card>
              <p className="text-sm text-gray-500 text-center py-4">
                Select a Jira project above to create tickets and view recent activity.
              </p>
            </Card>
          ) : (
            <>
              <Card title="Create NHI Finding Ticket">
                {error && (
                  <div className="mb-4">
                    <Alert variant="error" message={error} onDismiss={() => setError(null)} />
                  </div>
                )}
                {success && (
                  <div className="mb-4">
                    <Alert variant="success" message={success} onDismiss={() => setSuccess(null)} />
                  </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                  <Input
                    label="Title (Summary)"
                    placeholder="e.g., Stale Service Account: svc-deploy-prod"
                    value={summary}
                    onChange={(e) => setSummary(e.target.value)}
                    required
                  />
                  <Textarea
                    label="Description"
                    placeholder="Details about the NHI finding..."
                    rows={4}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                  <Button
                    type="submit"
                    loading={submitting}
                    disabled={!summary.trim()}
                  >
                    Create Ticket
                  </Button>
                </form>
              </Card>

              <Card title="Recent Tickets">
                {loadingTickets ? (
                  <Spinner centered />
                ) : ticketsUnavailable ? (
                  <Alert
                    variant="warning"
                    message="Jira is currently unavailable, so recent tickets can't be loaded. Try again shortly."
                  />
                ) : tickets.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    No tickets found for this project.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200">
                          <th className="text-left py-2 pr-4 font-medium text-gray-600">Key</th>
                          <th className="text-left py-2 pr-4 font-medium text-gray-600">Summary</th>
                          <th className="text-left py-2 font-medium text-gray-600">Created</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tickets.map((t) => (
                          <tr
                            key={t.jira_key}
                            className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                            onClick={() => {
                              if (siteUrl) {
                                window.open(`${siteUrl}/browse/${t.jira_key}`, "_blank");
                              }
                            }}
                          >
                            <td className="py-2 pr-4">
                              <span className="text-blue-600 font-medium">{t.jira_key}</span>
                            </td>
                            <td className="py-2 pr-4 text-gray-900">{t.summary}</td>
                            <td className="py-2 text-gray-500 whitespace-nowrap">
                              {timeAgo(t.created_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            </>
          )}
        </>
      )}
    </div>
  );
}
