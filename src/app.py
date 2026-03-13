from fastmcp import FastMCP

mcp = FastMCP(
    "Jor-MCP",
    instructions=(
        "Servidor MCP da Ambiental Media para acesso a conteúdo jornalístico. "
        "Use search_ambiental para buscar artigos por palavra-chave, "
        "get_full_article para ler o conteúdo completo de um artigo pelo ID, "
        "e list_latest_news para ver as últimas notícias publicadas."
    ),
)
