
"""Dictionary, spelling correction, and Wikipedia API lookup."""

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

WIKIPEDIA_SEARCH_URL = (
    "https://en.wikipedia.org/w/api.php"
)

TIMEOUT = 15.0


def escape_text(text):
    """Escape text before inserting it into HTML."""
    return html.escape(str(text).strip())


def make_result(message):
    """Create a result without pronunciation."""
    return {
        "html": message,
        "phonetic": "",
        "audio_url": "",
    }


def extract_pronunciation(data):
    """Extract phonetic spelling and the best available audio URL."""

    phonetic = ""
    audio_url = ""

    for entry in data:
        if not phonetic:
            phonetic = entry.get("phonetic", "")

        for phonetic_item in entry.get("phonetics", []):
            if not phonetic:
                phonetic = phonetic_item.get("text", "")

            candidate = (
                phonetic_item.get("audio", "") or ""
            ).strip()

            if not candidate:
                continue

            if candidate.startswith("//"):
                candidate = "https:" + candidate

            parsed = urlparse(candidate)
            hostname = (parsed.hostname or "").lower()

            valid_host = (
                hostname == "dictionaryapi.dev"
                or hostname.endswith(".dictionaryapi.dev")
            )

            if parsed.scheme == "https" and valid_host:
                audio_url = candidate
                break

        if audio_url:
            break

    return phonetic, audio_url


def format_dictionary(data):
    """Format dictionary API response into antique-style HTML."""

    sections = []

    for entry in data[:2]:
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
    """Get a word definition and pronunciation."""

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
        phonetic, audio_url = extract_pronunciation(data)

        if not result:
            return None

        return {
            "html": result,
            "phonetic": phonetic,
            "audio_url": audio_url,
        }

    except (httpx.HTTPError, ValueError, TypeError):
        return None


async def wikipedia_search(client, term):
    """Search Wikipedia for relevant article titles."""

    response = await client.get(
        WIKIPEDIA_SEARCH_URL,
        params={
            "action": "query",
            "list": "search",
            "srsearch": term,
            "srlimit": 5,
            "format": "json",
            "formatversion": 2,
        },
    )

    response.raise_for_status()

    data = response.json()

    return [
        item.get("title", "")
        for item in data.get("query", {}).get("search", [])
        if item.get("title")
    ]



async def wikipedia_summary(client, title):
    """Retrieve a Wikipedia article summary using the Action API."""

    response = await client.get(
        WIKIPEDIA_SEARCH_URL,
        params={
            "action": "query",
            "prop": "extracts|info",
            "exintro": 1,
            "explaintext": 1,
            "inprop": "url",
            "redirects": 1,
            "titles": title,
            "format": "json",
            "formatversion": 2,
        },
    )

    response.raise_for_status()

    data = response.json()
    pages = data.get("query", {}).get("pages", [])

    if not pages:
        return None

    page = pages[0]
    extract = page.get("extract", "")

    if not extract:
        return None

    return make_result(
        format_wikipedia({
            "extract": extract,
            "content_urls": {
                "desktop": {
                    "page": page.get("fullurl", "")
                }
            },
        })
    )


def edit_distance(first, second):
    """Calculate edit distance, including adjacent letter swaps."""

    first = first.lower()
    second = second.lower()

    rows = len(first) + 1
    columns = len(second) + 1

    matrix = [
        [0] * columns
        for _ in range(rows)
    ]

    for i in range(rows):
        matrix[i][0] = i

    for j in range(columns):
        matrix[0][j] = j

    for i in range(1, rows):
        for j in range(1, columns):

            cost = 0 if first[i - 1] == second[j - 1] else 1

            matrix[i][j] = min(
                matrix[i - 1][j] + 1,
                matrix[i][j - 1] + 1,
                matrix[i - 1][j - 1] + cost,
            )

            # Handle adjacent swapped letters.
            if (
                i > 1
                and j > 1
                and first[i - 1] == second[j - 2]
                and first[i - 2] == second[j - 1]
            ):
                matrix[i][j] = min(
                    matrix[i][j],
                    matrix[i - 2][j - 2] + 1,
                )

    return matrix[-1][-1]


async def find_spelling_suggestion(client, word):
    """Find a likely spelling correction using Wikipedia search."""

    try:
        titles = await wikipedia_search(client, word)

    except (httpx.HTTPError, ValueError, TypeError):
        return None

    best_match = None
    best_distance = float("inf")

    for title in titles:

        # Ignore explanatory text such as "Python (programming language)".
        candidate = title.split(" (", 1)[0].strip()

        # We only want single-word dictionary corrections here.
        if not candidate or " " in candidate:
            continue

        if not candidate.replace("-", "").replace("'", "").isalpha():
            continue

        distance = edit_distance(word, candidate)
        longest = max(len(word), len(candidate))

        allowed_distance = 1 if longest <= 7 else 2

        if (
            distance <= allowed_distance
            and distance < best_distance
            and distance / longest <= 0.25
        ):
            best_match = candidate
            best_distance = distance

    if best_match and best_match.lower() != word.lower():
        return best_match

    return None



async def wikipedia_lookup(client, term):
    """Search Wikipedia and retrieve the best available summary."""

    try:
        # Give the programming-language article priority
        # when the user searches for Python.
        search_terms = [term]

        if term.lower() == "python":
            search_terms.insert(
                0,
                "Python programming language",
            )

        for search_term in search_terms:

            titles = await wikipedia_search(
                client,
                search_term,
            )

            for title in titles:

                result = await wikipedia_summary(
                    client,
                    title,
                )

                if result:
                    return result

        return make_result(
            '<p style="color:#913D32;">'
            'No matching Wikipedia article or summary was found.'
            '</p>'
        )

    except httpx.TimeoutException:
        return make_result(
            '<p style="color:#913D32;">'
            'The lookup timed out. Please try again.'
            '</p>'
        )

    except httpx.HTTPStatusError as error:
        return make_result(
            '<p style="color:#913D32;">'
            f'Wikipedia returned an HTTP error '
            f'({error.response.status_code}). Please try again later.'
            '</p>'
        )

    except httpx.HTTPError:
        return make_result(
            '<p style="color:#913D32;">'
            'Could not connect to Wikipedia. '
            'Please check your internet connection.'
            '</p>'
        )

    except (ValueError, TypeError, KeyError):
        return make_result(
            '<p style="color:#913D32;">'
            'Could not process the Wikipedia response.'
            '</p>'
        )


async def lookup_async(term):
    """Perform dictionary, spelling correction, and Wikipedia lookup."""

    term = re.sub(r"\s+", " ", term).strip()

    if not term:
        return make_result(
            "<p>No text selected.</p>"
        )

    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "LazyLex/0.1 "
                "(https://github.com/Joseph-mappila/LazyLex) "
                "httpx"
            )
        },
    ) as client:

        # Phrases are searched directly on Wikipedia.
        if len(term.split()) > 1:
            return await wikipedia_lookup(client, term)

        # First, try the exact dictionary spelling.
        result = await dictionary_lookup(client, term)

        if result:
            return result

        # If the word was not found, try to correct its spelling.
        suggestion = await find_spelling_suggestion(
            client,
            term,
        )

        if suggestion:

            corrected_result = await dictionary_lookup(
                client,
                suggestion,
            )

            if corrected_result:

                notice = (
                    '<p style="color:#315C58; font-size:13px;">'
                    f'Showing results for '
                    f'<b>{escape_text(suggestion)}</b> '
                    f'instead of '
                    f'<b>{escape_text(term)}</b>.'
                    '</p>'
                )

                corrected_result["html"] = (
                    notice + corrected_result["html"]
                )

                return corrected_result

        # If no dictionary correction worked, search Wikipedia.
        return await wikipedia_lookup(client, term)


def lookup(term):
    """Synchronous function for the background thread."""

    try:
        return asyncio.run(lookup_async(term))

    except Exception:
        return make_result(
            '<p style="color:#913D32;">'
            'An unexpected lookup error occurred. '
            'Please try again.'
            '</p>'
        )
