import os

import anthropic
import requests
from bs4 import BeautifulSoup


def scrape_latest_post():
    resp = requests.get("https://oasis.security/blog", timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    article = soup.find("article") or soup.find("a", href=lambda h: h and "/blog/" in h)
    if not article:
        links = soup.find_all("a", href=lambda h: h and "/blog/" in h)
        if not links:
            raise RuntimeError("Could not find any blog post links on oasis.security/blog")
        link = links[0]
        title = link.get_text(strip=True) or "Untitled"
        href = link["href"]
    else:
        link = article.find("a", href=True) if article.name != "a" else article
        title = article.get_text(strip=True)[:200] or "Untitled"
        href = link["href"] if link else ""

    if href and not href.startswith("http"):
        href = f"https://oasis.security{href}"

    body_text = title
    if href:
        try:
            post_resp = requests.get(href, timeout=15)
            post_resp.raise_for_status()
            post_soup = BeautifulSoup(post_resp.text, "lxml")
            main = post_soup.find("article") or post_soup.find("main") or post_soup.find("body")
            if main:
                for tag in main.find_all(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                body_text = main.get_text(separator="\n", strip=True)
        except requests.RequestException:
            pass

    return {"title": title, "url": href, "body_text": body_text}


def summarize_with_claude(title, body_text):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is required")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    "Summarize this blog post about Non-Human Identity security "
                    "in 2-3 concise paragraphs. Focus on key findings and practical "
                    f"implications.\n\nTitle: {title}\n\n{body_text[:8000]}"
                ),
            }
        ],
    )
    return message.content[0].text
