import click
from flask.cli import with_appcontext


@click.command("nhi-digest")
@click.option("--user-email", required=True, help="Email of the IdentityHub user whose Jira credentials to use")
@click.option("--project-key", required=True, help="Jira project key for the new ticket")
@click.option("--dry-run", is_flag=True, default=False, help="Print the summary without creating a Jira ticket")
@with_appcontext
def nhi_digest(user_email, project_key, dry_run):
    """Fetch the latest NHI blog post, summarize with AI, and create a Jira ticket."""
    from ..models.user import User
    from ..services.jira_service import JiraService
    from ..services.nhi_digest import scrape_latest_post, summarize_with_claude

    user = User.query.filter_by(email=user_email).first()
    if not user:
        click.echo(f"Error: user '{user_email}' not found", err=True)
        raise SystemExit(1)
    if not user.jira_credential:
        click.echo(f"Error: user '{user_email}' has no Jira credentials configured", err=True)
        raise SystemExit(1)

    click.echo("Fetching latest blog post from oasis.security/blog...")
    post = scrape_latest_post()
    click.echo(f"Found: {post['title']}")
    if post["url"]:
        click.echo(f"URL: {post['url']}")

    click.echo("\nGenerating AI summary...")
    summary = summarize_with_claude(post["title"], post["body_text"])
    click.echo(f"\nSummary:\n{summary}\n")

    if dry_run:
        click.echo("[Dry run] Skipping Jira ticket creation.")
        return

    click.echo("Creating Jira ticket...")
    service = JiraService(user.jira_credential)
    ticket_summary = f"NHI Digest: {post['title'][:200]}"
    description = f"Source: {post['url']}\n\n---\n\n{summary}"
    result = service.create_issue(project_key, ticket_summary, description)

    # Jira is the single source of truth — no local copy is persisted.
    click.echo(f"Created ticket: {result['key']}")
