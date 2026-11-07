# LazyLex — The Pocket Lexicon

LazyLex is a lightweight desktop dictionary and summary companion built with Python and PyQt6.

Select and copy a word or phrase, press a keyboard shortcut, and LazyLex displays its definition or a short summary in a floating window — without needing to open a browser.

## Features

- **Floating dictionary window** — Displays definitions in a compact desktop popup.
- **Dictionary API integration** — Retrieves definitions, phonetics, examples and synonyms.
- **Wikipedia fallback** — Retrieves summaries for phrases and words not found in the dictionary.
- **Antique dictionary UI** — A parchment-inspired interface with vintage typography and warm colours.
- **Scrollable content** — Read longer definitions and summaries inside the popup.
- **Bottom-right positioning** — Displays the popup near the bottom-right corner of the screen.
- **Keyboard shortcuts** — Supports desktop shortcut integration.
- **Background API requests** — Performs lookups without blocking the interface.
- **Clipboard integration** — Retrieves copied text for dictionary lookups.

## Preview

<!-- Add a screenshot of LazyLex here -->

## Requirements

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/)
- An internet connection

For Linux Wayland systems:

- `wl-clipboard`
- A compatible Wayland compositor
- Hyprland for the documented native shortcut configuration

## Installation

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd LazyLex
```

Replace `YOUR_GITHUB_REPOSITORY_URL` with your repository's actual URL.

### 2. Install dependencies

```bash
uv sync
```

This creates the virtual environment and installs the dependencies specified in the project.

### 3. Install Linux system dependencies

For Arch Linux and Arch-based distributions:

```bash
sudo pacman -S wl-clipboard
```

### 4. Run LazyLex

```bash
uv run lazylex
```

Keep the application running in the background while using its desktop shortcut.

## Usage

1. Start LazyLex.
2. Select a word or phrase in another application.
3. Copy the selected text using `Ctrl + C`.
4. Press your configured LazyLex shortcut.
5. Read the definition or summary in the floating window.

Press the shortcut again to toggle the popup.

Press `Escape` or use the close button to dismiss it.

## Keyboard Shortcuts

LazyLex supports native desktop shortcut integration.

The shortcut can be configured according to your desktop environment and personal preference.

### Hyprland Configuration

Open your Hyprland configuration file:

```bash
~/.config/hypr/hyprland.conf
```

Add a binding:

```ini
bind = SUPER SHIFT, D, exec, uv run --directory /absolute/path/to/LazyLex lazylex --toggle
```

Replace `/absolute/path/to/LazyLex` with the actual path to your LazyLex project directory.

For example:

```ini
bind = SUPER SHIFT, D, exec, uv run --directory /home/user/Documents/LazyLex lazylex --toggle
```

Reload Hyprland:

```bash
hyprctl reload
```

Start LazyLex once:

```bash
cd /absolute/path/to/LazyLex
uv run lazylex
```

Now press `SUPER + SHIFT + D` to toggle LazyLex.

**Note:** You can change `SUPER SHIFT, D` to any key combination supported by your Hyprland configuration.

## Development

### Activate the virtual environment

```bash
source .venv/bin/activate
```

### Run the application

```bash
uv run lazylex
```

### Run as a Python module

```bash
uv run python -m lazylex.main
```

### Deactivate the virtual environment

```bash
deactivate
```

## Dependencies

| Dependency | Purpose                             |
| ---------- | ----------------------------------- |
| PyQt6      | Graphical user interface            |
| HTTPX      | Asynchronous HTTP requests          |
| pynput     | Keyboard input and shortcut support |
| pyperclip  | Clipboard access                    |
| uv         | Dependency and project management   |

## APIs

### Dictionary API

Used for word definitions, phonetics, examples and synonyms.

https://api.dictionaryapi.dev/

### Wikipedia REST API

Used as a fallback for summaries and multi-word phrases.

https://en.wikipedia.org/api/rest_v1/

## Project Structure

```text
LazyLex/
├── pyproject.toml
├── uv.lock
├── README.md
└── src/
    └── lazylex/
        ├── __init__.py
        ├── main.py
        ├── selection.py
        ├── lookup.py
        └── overlay.py
```

## Platform Support

LazyLex is being developed with cross-platform compatibility in mind.

- **Linux:** Primary development and testing environment.
- **Windows:** Compatibility is a development goal.
- **macOS:** Compatibility is a development goal.

Keyboard shortcuts and selected-text capture may require platform-specific configuration.

## License

MIT License.

See the `LICENSE` file for details.
