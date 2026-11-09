
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
MAX_LOOKUP_LENGTH = 200


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
        f'<p style="color:#302317; '
        f'font-size:16px; '
        f'line-height:150%; '
        f'margin-bottom:14px;">'
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
    """Search Wikipedia and return article titles and snippets."""

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
        {
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
        }
        for item in data.get("query", {}).get("search", [])
        if item.get("title")
    ]

def normalize_search_words(text):
    """Normalize text into comparable search words."""

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.lower()

    words = re.findall(r"\b[a-z0-9]+\b", text)

    # Handle common plural forms.
    return {
        word[:-1] if word.endswith("s") and len(word) > 4 else word
        for word in words
    }


def get_wikipedia_search_terms(topic):
    """Generate useful alternative searches for a topic."""

    search_terms = [topic]

    normalized = topic.lower()

    # GitHub workflows are implemented using GitHub Actions.
    if re.search(r"\bgithub\s+workflows?\b", normalized):
        search_terms.insert(0, "GitHub Actions workflows")

    # Search the exact phrase as well.
    search_terms.append(f'"{topic}"')

    return list(dict.fromkeys(search_terms))


def score_wikipedia_article(title, snippet, extract, topic):
    """Score relevance using the actual article, not search snippets."""

    topic_words = normalize_search_words(topic)

    title_words = normalize_search_words(title)
    summary_words = normalize_search_words(extract)

    article_words = title_words | summary_words

    if not topic_words:
        return 0

    # Every important topic word must appear in the
    # article title or its actual summary.
    if not topic_words.issubset(article_words):
        return 0

    title_matches = len(topic_words & title_words)
    summary_matches = len(topic_words & summary_words)

    return (
        title_matches * 30
        + summary_matches * 20
        + len(topic_words) * 10
    )

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

def extract_search_topic(term):
    """Remove common question phrases and extract the main topic."""

    topic = re.sub(r"\s+", " ", term).strip()
    topic = topic.rstrip("?.!, ")

    prefixes = [
        r"^(?:what is|what are|who is|who are)\s+",
        r"^(?:what does|what do)\s+",
        r"^(?:how does|how do|how is|how are)\s+",
        r"^(?:why does|why do|why is|why are)\s+",
        r"^(?:explain|define|describe)\s+",
        r"^(?:tell me about)\s+",
        r"^(?:meaning of)\s+",
    ]

    for pattern in prefixes:
        topic = re.sub(pattern, "", topic, flags=re.IGNORECASE)
        if topic != term:
            break

    # Remove an article left after removing the question phrase.
    topic = re.sub(r"^(?:a|an|the)\s+", "", topic, flags=re.IGNORECASE)

    # Handle questions such as "how does garbage collection work?"
    topic = re.sub(r"\s+work$", "", topic, flags=re.IGNORECASE)

    return topic.strip()


def normalize_title(title):
    """Normalize a Wikipedia title for comparison."""

    title = title.lower()
    title = re.sub(r"\([^)]*\)", "", title)
    title = re.sub(r"[^a-z0-9]+", " ", title)

    return re.sub(r"\s+", " ", title).strip()


def score_wikipedia_title(title, topic):
    """Score how closely a Wikipedia title matches the search topic."""

    normalized_title = normalize_title(title)
    normalized_topic = normalize_title(topic)

    if not normalized_title or not normalized_topic:
        return 0

    if normalized_title == normalized_topic:
        return 1000

    title_words = set(normalized_title.split())
    topic_words = set(normalized_topic.split())

    common_words = title_words & topic_words

    if not common_words:
        return 0

    coverage = len(common_words) / len(topic_words)

    # Prefer informative titles over overly broad one-word titles.
    specificity_bonus = min(len(title_words), len(topic_words)) * 8

    missing_words_penalty = (
        len(topic_words - title_words) * 20
    )

    return (
        coverage * 100
        + specificity_bonus
        - missing_words_penalty
    )

async def wikipedia_lookup(client, term):
    """Search Wikipedia and select a genuinely relevant article."""

    try:
        topic = extract_search_topic(term)

        if not topic:
            topic = term

        search_terms = get_wikipedia_search_terms(topic)
        # GitHub workflows are created and managed using GitHub Actions.
        if re.search(r"\bgithub\s+workflows?\b", topic, re.IGNORECASE):

            result = await wikipedia_summary(
                client,
                "GitHub Actions",
            )

            if result:
                return result

        best_result = None
        best_score = 0

        searched_titles = set()

        for search_term in search_terms:

            articles = await wikipedia_search(
                client,
                search_term,
            )

            for article in articles:

                title = article["title"]

                if title.lower() in searched_titles:
                    continue

                searched_titles.add(title.lower())

                # Retrieve the article's actual summary.
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
                    continue

                page = pages[0]
                extract = page.get("extract", "")

                if not extract:
                    continue

                score = score_wikipedia_article(
                    page.get("title", title),
                    article.get("snippet", ""),
                    extract,
                    topic,
                )

                if score > best_score:

                    best_score = score

                    best_result = make_result(
                        format_wikipedia({
                            "extract": extract,
                            "content_urls": {
                                "desktop": {
                                    "page": page.get("fullurl", "")
                                }
                            },
                        })
                    )

        if best_result:
            return best_result

        return make_result(
            '<p style="color:#913D32;">'
            'No closely matching Wikipedia article was found. '
            'Try a more specific search phrase.'
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

    if len(term) > MAX_LOOKUP_LENGTH:
        return make_result(
            '<p style="color:#913D32;">'
            'Your search is too long. '
            'Please use 200 characters or fewer.'
            '</p>'
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
