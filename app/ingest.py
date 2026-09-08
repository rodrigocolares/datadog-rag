import argparse
import asyncio
import hashlib
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from openai import AsyncOpenAI

from app.config import settings
from app.store import VectorStore


HEADERS = {"User-Agent": "DatadogDocsRAG/1.0 (documentation indexer)"}


def allowed(url: str) -> bool:
    parsed = urlparse(url)
    base = urlparse(settings.datadog_docs_base_url)
    return parsed.scheme == "https" and parsed.netloc == base.netloc and parsed.path.startswith(settings.allowed_prefixes)


def chunks(text: str, size: int = 1300, overlap: int = 180) -> list[str]:
    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in text.split("\n")]
    paragraphs = [part for part in paragraphs if len(part) >= 30]
    output: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 1 > size:
            output.append(current)
            current = current[-overlap:] + " " + paragraph
        else:
            current = f"{current} {paragraph}".strip()
    if current:
        output.append(current)
    return output


async def sitemap_urls(client: httpx.AsyncClient) -> list[str]:
    pending = [urljoin(settings.datadog_docs_base_url, "/sitemap.xml")]
    pages: list[str] = []
    visited: set[str] = set()
    while pending:
        sitemap = pending.pop()
        if sitemap in visited:
            continue
        visited.add(sitemap)
        response = await client.get(sitemap)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        locations = [node.text.strip() for node in root.iter() if node.tag.endswith("loc") and node.text]
        pending.extend(url for url in locations if url.endswith(".xml"))
        pages.extend(url for url in locations if not url.endswith(".xml") and allowed(url))
        if len(pages) >= settings.max_pages:
            break
    return list(dict.fromkeys(pages))[: settings.max_pages]


def extract(html: str, url: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    main = soup.select_one("main") or soup.select_one("article") or soup.body
    if not main:
        return title, ""
    for element in main.select("nav, footer, script, style, svg, form, button"):
        element.decompose()
    lines = [line.strip() for line in main.get_text("\n").splitlines() if line.strip()]
    return title.replace(" | Datadog", ""), "\n".join(lines)


async def embed(client: AsyncOpenAI, texts: list[str]) -> list[list[float]]:
    response = await client.embeddings.create(model=settings.openai_embedding_model, input=texts)
    return [item.embedding for item in response.data]


async def run(force: bool = False) -> None:
    if not settings.openai_api_key:
        raise RuntimeError("Defina OPENAI_API_KEY no arquivo .env")
    store = VectorStore(settings.database_path)
    ai = AsyncOpenAI(api_key=settings.openai_api_key)
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=timeout) as web:
        urls = await sitemap_urls(web)
        print(f"Encontradas {len(urls)} páginas dentro do escopo.")
        indexed = unchanged = failed = 0
        for number, url in enumerate(urls, start=1):
            try:
                response = await web.get(url)
                response.raise_for_status()
                title, content = extract(response.text, url)
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                if not force and store.content_hash(url) == digest:
                    unchanged += 1
                    continue
                parts = chunks(content)
                if not parts:
                    continue
                vectors: list[list[float]] = []
                for start in range(0, len(parts), 64):
                    vectors.extend(await embed(ai, parts[start : start + 64]))
                store.replace_document(url, title, digest, parts, vectors)
                indexed += 1
                print(f"[{number}/{len(urls)}] {title}")
            except Exception as exc:
                failed += 1
                print(f"Falha em {url}: {exc}")
            await asyncio.sleep(settings.request_delay_seconds)
    print(f"Concluído: {indexed} atualizadas, {unchanged} sem alterações, {failed} falhas.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Reindexa páginas que não mudaram")
    args = parser.parse_args()
    asyncio.run(run(force=args.force))

