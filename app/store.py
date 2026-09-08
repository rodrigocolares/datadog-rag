import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class SearchResult:
    text: str
    title: str
    url: str
    score: float


class VectorStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY,
                    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    UNIQUE(document_id, position)
                );
                PRAGMA foreign_keys = ON;
                """
            )

    def content_hash(self, url: str) -> str | None:
        with self.connect() as db:
            row = db.execute("SELECT content_hash FROM documents WHERE url = ?", (url,)).fetchone()
        return row["content_hash"] if row else None

    def replace_document(self, url: str, title: str, digest: str, chunks: list[str], embeddings: list[list[float]]) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM documents WHERE url = ?", (url,))
            cursor = db.execute(
                "INSERT INTO documents(url, title, content_hash) VALUES (?, ?, ?)",
                (url, title, digest),
            )
            document_id = cursor.lastrowid
            db.executemany(
                "INSERT INTO chunks(document_id, position, text, embedding) VALUES (?, ?, ?, ?)",
                [(document_id, i, text, json.dumps(vector)) for i, (text, vector) in enumerate(zip(chunks, embeddings))],
            )

    def search(self, query_embedding: list[float], limit: int, minimum: float) -> list[SearchResult]:
        query = np.asarray(query_embedding, dtype=np.float32)
        query_norm = float(np.linalg.norm(query)) or 1.0
        with self.connect() as db:
            rows = db.execute(
                "SELECT c.text, c.embedding, d.title, d.url FROM chunks c JOIN documents d ON d.id = c.document_id"
            ).fetchall()
        found: list[SearchResult] = []
        for row in rows:
            vector = np.asarray(json.loads(row["embedding"]), dtype=np.float32)
            denominator = query_norm * (float(np.linalg.norm(vector)) or 1.0)
            score = float(np.dot(query, vector) / denominator)
            if score >= minimum:
                found.append(SearchResult(row["text"], row["title"], row["url"], score))
        return sorted(found, key=lambda item: item.score, reverse=True)[:limit]

    def stats(self) -> dict[str, int | str | None]:
        with self.connect() as db:
            row = db.execute(
                "SELECT COUNT(DISTINCT d.id) pages, COUNT(c.id) chunks, MAX(d.indexed_at) updated_at FROM documents d LEFT JOIN chunks c ON c.document_id=d.id"
            ).fetchone()
        return dict(row)

