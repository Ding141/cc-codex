"""Screenshot a local page with a headless Chromium browser, outside Codex.

Codex's sandbox cannot start a browser on Windows (spawn EPERM, crashpad
access denied, crash dialogs), so UI evidence is produced here, as the user.
Each width is rendered through an iframe wrapper because headless windows
cannot be narrower than about 500px.
"""

import html
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

WIDTHS = (1440, 390)
VIEWPORT_HEIGHT = {1440: 900, 390: 844}  # desktop and phone first screens
SCHEMES = ("light", "dark")


def browser():
    override = os.environ.get("CC_CODEX_BROWSER")
    if override:
        if Path(override).is_file():
            return override
        raise ValueError(f"CC_CODEX_BROWSER does not point to a file: {override}")
    candidates = []
    if os.name == "nt":
        for base in filter(None, (os.environ.get("PROGRAMFILES"),
                                  os.environ.get("PROGRAMFILES(X86)"),
                                  os.environ.get("LOCALAPPDATA"))):
            candidates += [Path(base, "Google/Chrome/Application/chrome.exe"),
                           Path(base, "Microsoft/Edge/Application/msedge.exe")]
    elif sys.platform == "darwin":
        candidates += [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                       Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                       Path("/Applications/Chromium.app/Contents/MacOS/Chromium")]
    for path in candidates:
        if path.is_file():
            return str(path)
    for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    # Playwright's bundled Chromium, for machines without a system browser.
    for cache in (os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), Path.home() / ".cache/ms-playwright"):
        for found in sorted(Path(cache).glob("chromium-*/chrome-linux*/chrome")) if cache else ():
            if found.is_file():
                return str(found)
    raise ValueError("No Chrome, Edge or Chromium found. Set CC_CODEX_BROWSER to its executable.")


def target_url(root, target):
    if target.startswith(("http://", "https://", "file://")):
        return target
    path = Path(target)
    path = (path if path.is_absolute() else root / path).resolve()
    if not path.is_file():
        raise ValueError(f"Nothing to render at {path}")
    return path.as_uri()


def render(root, target, out_dir, widths=WIDTHS, schemes=SCHEMES, height=None):
    """Return [{"width", "scheme", "path"}] for every width x colour scheme.

    Without `height` each width gets a real first-screen viewport; pass one to
    capture a taller page.
    """
    program = browser()
    url = target_url(root, target)
    out_dir.mkdir(parents=True, exist_ok=True)
    shots = []
    with tempfile.TemporaryDirectory(prefix="cc-codex-render-") as work:
        work = Path(work)
        for width in widths:
            tall = height or VIEWPORT_HEIGHT.get(width, 900)
            wrapper = work / f"w{width}.html"
            wrapper.write_text(
                "<!doctype html><meta charset=\"utf-8\"><style>html,body{margin:0}"
                f"iframe{{border:0;display:block;width:{width}px;height:{tall}px}}</style>"
                f"<iframe src=\"{html.escape(url)}\"></iframe>", encoding="utf-8")
            for scheme in schemes:
                shot = out_dir / f"{width}-{scheme}.png"
                shot.unlink(missing_ok=True)
                args = [program, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                        "--force-device-scale-factor=1", "--allow-file-access-from-files",
                        "--user-data-dir=" + str(work / "profile"),
                        "--blink-settings=preferredColorScheme=" + ("0" if scheme == "dark" else "1"),
                        "--virtual-time-budget=2500", f"--window-size={width},{tall}",
                        "--screenshot=" + str(shot), wrapper.as_uri()]
                try:
                    subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=60)
                except subprocess.TimeoutExpired as exc:
                    raise ValueError(f"Browser timed out rendering {width}px {scheme}.") from exc
                if not shot.is_file():
                    raise ValueError(f"Browser produced no screenshot for {width}px {scheme}.")
                shots.append({"width": width, "scheme": scheme, "path": str(shot)})
    return shots
