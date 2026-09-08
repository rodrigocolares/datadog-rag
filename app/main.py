from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import ROOT, settings
from app.store import VectorStore


app = FastAPI(title="Datadog Docs RAG", version="1.0.0")
store = VectorStore(settings.database_path)


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


SYSTEM = """Você é um assistente técnico especializado em Datadog.
Responda em português do Brasil usando somente o CONTEXTO fornecido.
Se o contexto não contiver a resposta, diga claramente que não encontrou base suficiente na documentação indexada.
Não invente configurações, comandos, parâmetros ou recursos. Seja objetivo e preserve blocos de código úteis.
Ao apoiar uma afirmação, cite as fontes como [1], [2] etc., usando a numeração do contexto."""


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", **store.stats()}


@app.post("/api/chat")
async def chat(payload: Question) -> dict:
    if not settings.openai_api_key:
        raise HTTPException(503, "OPENAI_API_KEY não configurada")
    if store.stats()["chunks"] == 0:
        raise HTTPException(409, "O índice está vazio. Execute a ingestão primeiro.")
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    embedded = await client.embeddings.create(model=settings.openai_embedding_model, input=payload.question)
    results = store.search(embedded.data[0].embedding, settings.top_k, settings.min_similarity)
    if not results:
        return {"answer": "Não encontrei base suficiente na documentação indexada para responder a essa pergunta.", "sources": []}
    context = "\n\n".join(
        f"FONTE [{i}]\nTítulo: {item.title}\nURL: {item.url}\nTrecho: {item.text}"
        for i, item in enumerate(results, start=1)
    )
    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"PERGUNTA:\n{payload.question}\n\nCONTEXTO:\n{context}"},
        ],
    )
    return {
        "answer": response.choices[0].message.content,
        "sources": [
            {"number": i, "title": item.title, "url": item.url, "score": round(item.score, 3)}
            for i, item in enumerate(results, start=1)
        ],
    }

