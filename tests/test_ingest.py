from app.ingest import chunks


def test_chunks_keeps_content_and_splits_long_text():
    text = "\n".join([f"Parágrafo número {i} com conteúdo técnico suficiente para indexação e consulta." for i in range(80)])
    result = chunks(text, size=500, overlap=50)
    assert len(result) > 2
    assert "Parágrafo número 0" in result[0]
    assert "Parágrafo número 79" in result[-1]


def test_chunks_ignores_tiny_navigation_lines():
    result = chunks("Home\nEste é um parágrafo técnico válido com mais de trinta caracteres para o teste.")
    assert len(result) == 1
    assert "Home" not in result[0]

