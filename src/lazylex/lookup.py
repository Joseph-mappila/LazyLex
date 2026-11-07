
"""Dictionary and Wikipedia API lookup."""

import asyncio
import html
import re
from urllib.parse import quote, urlparse

import httpx


DICTIONARY_URL = (
    "https://api.dictionaryapi.dev/api/v2/entries/en/"
)

WIKIPEDIA_URL = (
    "https://en.wikipedia.org/api/rest_v1/page/summary/"
)

TIMEOUT = 10.0


def escape_text(text):
    """Escape text before inserting it into HTML."""
    return html.escape(str(text).strip())



def format_dictionary(data):
    """Format dictionary API response into antique-style HTML."""

    sections = []

    for entry in data[:2]:

        phonetic = entry.get("phonetic", "")

        if phonetic:
            sections.append(
                f'<p style="color:#70583E; font-size:14px;">'
                f'{escape_text(phonetic)}</p>'
            )

        for meaning in entry.get("meanings", []):

            part = meaning.get("partOfSpeech", "Meaning")

            sections.append(
                f'<h3 style="color:#684323; font-size:17px;">'
                f'{escape_text(part.capitalize())}</h3>'
            )

            for definition in meaning.get("definitions", [])[:3]:

                text = definition.get("definition", "")

                if text:
                    sections.append(
                        f'<p style="color:#302317; '
                        f'font-size:15px;">'
                        f'{escape_text(text)}</p>'
                    )

                example = definition.get("example")

                if example:
                    sections.append(
                        f'<p style="color:#70583E; '
                        f'font-size:14px; font-style:italic;">'
                        f'"{escape_text(example)}"</p>'
                    )

            synonyms = meaning.get("synonyms", [])

            if synonyms:
                synonym_text = ", ".join(
                    escape_text(s) for s in synonyms[:8]
                )

                sections.append(
                    f'<p style="color:#315C58; font-size:14px;">'
                    f'<b>Synonyms:</b> {synonym_text}</p>'
                )

    return "".join(sections)



def format_wikipedia(data):
    """Format Wikipedia response into antique-style HTML."""

    extract = data.get("extract", "")

    if not extract:
        return (
            '<p style="color:#913D32;">'
            'No summary was found.</p>'
        )

    result = (
        f'<p style="color:#302317; font-size:15px;">'
        f'{escape_text(extract[:1500])}</p>'
    )

    page_url = (
        data.get("content_urls", {})
        .get("desktop", {})
        .get("page", "")
    )

    parsed = urlparse(page_url)

    if (
        parsed.scheme == "https"
        and parsed.hostname == "en.wikipedia.org"
    ):
        safe_url = html.escape(page_url, quote=True)

        result += (
            f'<p><a href="{safe_url}" '
            f'style="color:#315C58; font-weight:bold;">'
            f'Read more on Wikipedia</a></p>'
        )

    return result


async def dictionary_lookup(client, word):
    """Get a word definition from Dictionary API."""

    url = DICTIONARY_URL + quote(word, safe="")

    try:
        response = await client.get(url)

        if response.status_code == 404:
            return None

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            return None

        result = format_dictionary(data)

        return result or None

    except (httpx.HTTPError, ValueError, TypeError):
        return None


async def wikipedia_lookup(client, term):
    """Get a summary from Wikipedia."""

    url = WIKIPEDIA_URL + quote(term, safe="")

    try:
        response = await client.get(url)
        response.raise_for_status()

        return format_wikipedia(response.json())

    except (httpx.HTTPError, ValueError, TypeError):
        return (
            '<p style="color:#f38ba8;">'
            'Unable to retrieve a summary. '
            'Check your internet connection.</p>'
        )


async def lookup_async(term):
    """Perform the actual API lookup."""

    term = re.sub(r"\s+", " ", term).strip()

    if not term:
        return "<p>No text selected.</p>"

    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "LazyLex/0.1"},
    ) as client:

        # Multi-word phrases use Wikipedia.
        if len(term.split()) > 1:
            return await wikipedia_lookup(client, term)

        # Try Dictionary API first.
        result = await dictionary_lookup(client, term)

        if result:
            return result

        # Dictionary miss: try Wikipedia.
        return await wikipedia_lookup(client, term)


def lookup(term):
    """Synchronous function for the background thread."""

    try:
        return asyncio.run(lookup_async(term))

    except Exception:
        return (
            '<p style="color:#f38ba8;">'
            'An unexpected lookup error occurred.</p>'
        )
