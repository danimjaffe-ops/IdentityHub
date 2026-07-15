"""End-to-end user journeys driven through a real browser against the full stack.

Each test registers its own unique user (the DB is shared across the session),
so tests stay independent despite the persistent database.
"""

import uuid

import pytest
from playwright.sync_api import Page, expect

PASSWORD = "password123"


def _unique_email():
    return f"e2e-{uuid.uuid4().hex[:12]}@example.com"


def register(page: Page, base_url: str, email: str) -> None:
    """Register a fresh account through the UI and land on the dashboard."""
    page.goto(f"{base_url}/login")
    page.get_by_role("button", name="Don't have an account? Register").click()
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_label("Confirm password").fill(PASSWORD)
    page.get_by_role("button", name="Create account").click()
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()


def connect_jira(page: Page, base_url: str) -> None:
    """Connect the (stubbed) Jira workspace via Settings."""
    page.goto(f"{base_url}/settings")
    page.get_by_role("button", name="Connect", exact=True).click()
    # exact=True avoids the "Help: <field>" tooltip buttons that share the label text.
    page.get_by_label("Jira Site URL", exact=True).fill("https://e2e.atlassian.net")
    page.get_by_label("Atlassian Email", exact=True).fill("jira@example.com")
    page.get_by_label("API Token", exact=True).fill("secret-token")
    page.get_by_role("button", name="Connect to Jira").click()
    # onConnected navigates back to the dashboard.
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()


def test_register_lands_on_dashboard_with_connect_prompt(page: Page, live_server: str):
    register(page, live_server, _unique_email())
    expect(page.get_by_text("Connect your Jira workspace")).to_be_visible()


def test_connect_jira_create_and_list_ticket(page: Page, live_server: str):
    register(page, live_server, _unique_email())
    connect_jira(page, live_server)

    # Pick the (stubbed) project; recent tickets load live from Jira.
    page.get_by_text("Select a project").click()
    page.get_by_role("button", name="NHI — NHI Findings").click()

    expect(page.get_by_text("NHI-1")).to_be_visible()
    expect(page.get_by_text("Stale service account: svc-deploy-prod")).to_be_visible()

    # Create a ticket and see the success confirmation.
    page.get_by_label("Title (Summary)").fill("New finding from E2E")
    page.get_by_role("button", name="Create Ticket").click()
    expect(page.get_by_text("Ticket NHI-1 created successfully")).to_be_visible()


def test_generate_and_revoke_api_key(page: Page, live_server: str):
    register(page, live_server, _unique_email())
    page.goto(f"{live_server}/settings")

    page.get_by_label("Label (optional)").fill("CI Pipeline Key")
    page.get_by_role("button", name="Generate New Key").click()

    # The one-time key modal shows the full key.
    expect(page.get_by_role("heading", name="New API Key")).to_be_visible()
    key_text = page.locator("code").inner_text()
    assert key_text.startswith("nhk_")

    page.get_by_role("button", name="Close").click()

    # The key appears in the table (by prefix), then revoking clears it.
    expect(page.get_by_text("CI Pipeline Key")).to_be_visible()
    page.get_by_role("button", name="Revoke").click()
    expect(page.get_by_text("No API keys generated yet.")).to_be_visible()


def test_unauthorized_redirects_to_login(page: Page, live_server: str):
    """The current branch's feature: a 401 (e.g. expired session) drops the
    logged-in-looking SPA to the login screen."""
    register(page, live_server, _unique_email())

    # Simulate the session going away, then hit a protected route.
    page.context.clear_cookies()
    page.goto(f"{live_server}/settings")

    expect(page).to_have_url(f"{live_server}/login")
    expect(page.get_by_text("Sign in to your account")).to_be_visible()


def test_delete_account_then_cannot_log_in(page: Page, live_server: str):
    email = _unique_email()
    register(page, live_server, email)

    page.goto(f"{live_server}/settings")
    page.get_by_role("button", name="Delete account", exact=True).click()
    # Confirm by typing the exact email.
    page.get_by_placeholder(email).fill(email)
    page.get_by_role("button", name="Delete Account", exact=True).click()
    expect(page).to_have_url(f"{live_server}/login")

    # The account is gone — logging back in fails.
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_text("Invalid email or password")).to_be_visible()
