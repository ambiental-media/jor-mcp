<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Diretrizes de Formatação de Documentação

Este documento define as regras estritas que todos os colaboradores humanos e IAs devem seguir ao criar ou modificar arquivos markdown no repositório `jor-mcp`.

## 1. Estrutura e Nomenclatura de Arquivos
- **Apenas kebab-case:** Todos os arquivos markdown devem ser nomeados usando letras minúsculas e hífens (ex: `api-contracts.md`).
- **Paridade Bilíngue:** Todos os arquivos em `docs/en/` devem ter uma tradução correspondente em `docs/pt-br/`.
- **Sem espaços em caminhos:** Os nomes de diretórios devem seguir o padrão `kebab-case`.

## 2. Formatação Markdown
- **Títulos:** Comece cada arquivo com um único `# Título 1` (Título). Use `##` e `###` para as seções subsequentes.
- **Listas:** Sempre use hífens (`-`) para listas não ordenadas.
- **Blocos de Código:** Sempre especifique a linguagem (ex: `python`, `bash`, `json`, `http`). Use `mermaid` para todos os diagramas.
- **Diagramas:** Use Mermaid.js. Inclua `%%{init: {'theme': 'dark'}}%%` no topo.

## 3. Linguagem e Tom
- **Tom:** Profissional, conciso e direto.
- **Inglês Primeiro:** O inglês é a fonte da verdade. Termos técnicos (ex: "Rate Limiting", "Middleware") devem permanecer em inglês tanto nas versões em EN quanto em PT-BR.
- **Voz:** Prefira a voz ativa.

## 4. Referências Cruzadas
- **Links Relativos:** Use apenas links relativos (ex: `[Ver Arquitetura](../1-tecnico/architecture.md)`). Nunca use URLs absolutas do GitHub.
