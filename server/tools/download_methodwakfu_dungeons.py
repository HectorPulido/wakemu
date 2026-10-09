#!/usr/bin/env python3
"""Archive dungeon guides and article images for later, sourced JSON extraction."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

INDEX = "https://methodwakfu.com/donjons/"


def fetch(url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and (
        target.name == "page.html" or target.parent.name == "images"
    ):
        return hashlib.sha256(target.read_bytes()).hexdigest()
    temporary = target.with_suffix(target.suffix + ".part")
    result = subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--retry",
            "2",
            "--retry-delay",
            "2",
            "--max-time",
            "60",
            "--user-agent",
            "Mozilla/5.0",
            "--silent",
            "--show-error",
            "--output",
            str(temporary),
            url,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(result.stderr.strip()[:300])
    temporary.replace(target)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def guide_urls(html, base):
    soup = BeautifulSoup(html, "html.parser")
    urls = set()
    for link in soup.select("a[href]"):
        parsed = urlsplit(urljoin(base, link["href"]))
        parts = parsed.path.strip("/").split("/")
        if (
            parsed.hostname == "methodwakfu.com"
            and len(parts) >= 3
            and parts[0] == "pvm"
            and (parts[1].startswith("donjons") or parts[1] == "boss-ultimes")
        ):
            urls.add(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")))
    return urls


def download_guide(url, root):
    slug = "-".join(urlsplit(url).path.strip("/").split("/")[1:])
    directory = root / "guides" / slug
    row = {"url": url, "directory": str(directory), "status": "pending"}
    try:
        row["sha256"] = fetch(url, directory / "page.html")
        html = (directory / "page.html").read_text(errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        canonical = soup.select_one('link[rel="canonical"]')
        row["canonical_url"] = canonical.get("href", url) if canonical else url
        article = soup.select_one("article")
        if article is None:
            raise ValueError("No article found; refusing to archive a challenge page")
        title = article.select_one("h1") or soup.select_one("h1")
        row["title"] = title.get_text(" ", strip=True) if title else slug
        for unwanted in article.select("script, style, .comments, #comments"):
            unwanted.decompose()
        (directory / "article.txt").write_text(article.get_text("\n", strip=True))
        (directory / "article.html").write_text(str(article))
        images = {}
        for tag in article.select("img"):
            source = tag.get("data-src") or tag.get("src")
            if source and not source.startswith("data:"):
                image_url = urljoin(url, source.strip())
                images.setdefault(
                    image_url, {"url": image_url, "alt": tag.get("alt", "")}
                )
        row["images"] = list(images.values())
        row["discovered_guides"] = sorted(guide_urls(html, url))
        row["status"] = "downloaded"
    except Exception as error:
        row.update(status="failed", error=str(error))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path(".runtime/local/methodwakfu-dungeons")
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 12:
        parser.error("workers must be between 1 and 12")
    root = args.output.resolve()
    fetch(INDEX, root / "index.html")
    pending = guide_urls((root / "index.html").read_text(errors="replace"), INDEX)
    discovery = root / "discovery-extra.json"
    if discovery.is_file():
        extra = json.loads(discovery.read_text())
        pending.update(extra.get("dungeon_urls", []))
        pending.update(extra.get("ultimate_boss_urls", []))
    visited, rows = set(), []
    while pending:
        batch = sorted(pending - visited)
        if not batch:
            break
        visited.update(batch)
        pending = set()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for task in as_completed(
                [pool.submit(download_guide, url, root) for url in batch]
            ):
                row = task.result()
                rows.append(row)
                pending.update(row.pop("discovered_guides", []))
                print(row["status"], row["url"], flush=True)
    images = {}
    for row in rows:
        for image in row.get("images", []):
            images.setdefault(image["url"], image)

    def download_image(image):
        url = image["url"]
        suffix = Path(urlsplit(url).path).suffix or ".bin"
        path = (
            root / "images" / (hashlib.sha256(url.encode()).hexdigest()[:20] + suffix)
        )
        try:
            image.update(path=str(path), sha256=fetch(url, path), status="downloaded")
        except Exception as error:
            image.update(status="failed", error=str(error))
        return image

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        downloaded_images = list(pool.map(download_image, images.values()))
    manifest = {
        "index_url": INDEX,
        "fetched_at_unix": time.time(),
        "workers": args.workers,
        "guides": sorted(rows, key=lambda row: row["url"]),
        "images": downloaded_images,
        "composition_extraction_status": "pending; no composition inferred",
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "guides": len(rows),
                "guide_failures": sum(r["status"] == "failed" for r in rows),
                "images": len(images),
                "image_failures": sum(
                    r["status"] == "failed" for r in downloaded_images
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
