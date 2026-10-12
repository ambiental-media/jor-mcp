<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# SPEC-004: Avaliação de Migração para o MCP 2026-07-28

**Origem:** ClickUp — [Ticket 012: Spike de Investigação — Oportunidades MCP 2026-07-28](https://app.clickup.com/t/86ak1gr4m)
**Status:** Rascunho — Investigação

## 1. Objetivo

Avaliar o impacto da especificação MCP `2026-07-28` no servidor `jor-mcp` atual e produzir uma lista priorizada de oportunidades de migração.

- [ ] Impacto do core stateless no servidor atual documentado.
- [ ] Oportunidades de simplificação de infraestrutura mapeadas (cache de listas, roteamento por cabeçalhos).
- [ ] Mudanças de autorização versus o proxy OAuth 2.1 atual documentadas.
- [ ] Breaking changes e a janela de deprecação de 12 meses enumeradas.
- [ ] Oportunidades priorizadas (impacto × esforço) e próximos passos recomendados produzidos.

## 2. Contexto

O MCP `2026-07-28` é a maior revisão do protocolo: o core bidirecional com estado torna-se um protocolo stateless de requisição/resposta. Destaques:

- **Core stateless** — cada requisição é autodescritiva; `initialize`/`initialized` e `Mcp-Session-Id` foram retirados.
- **Roteamento por cabeçalhos** — `Mcp-Method` / `Mcp-Name` agora são obrigatórios em POSTs do Streamable HTTP.
- **Listas cacheáveis** — `ttlMs` + `cacheScope` nos resultados de listagem/leitura.
- **Endurecimento de autorização** — RFC 9207 `iss`, CIMD substituindo o DCR.
- **Framework de extensões** — Tasks, MCP Apps, Enterprise Managed Authorization (EMA).
- **Política de deprecação de 12 meses** formalizada.

## 3. Panorama da Arquitetura Atual

| Camada | Estado atual | Exposição ao `2026-07-28` |
|---|---|---|
| Framework | `fastmcp 3.4.4`, `mcp 1.29.1` (`uv.lock`) | FastMCP `4.0.0b1` é o primeiro a suportar a nova spec |
| Transporte | FastMCP `http_app()`, montado em `/`; cliente conecta em `/mcp/sse` | `/mcp/sse` = **transporte HTTP+SSE legado (deprecado)** |
| Estado da aplicação | Externalizado — Firestore (rate limits), custom claim `tier` do Firebase | Já stateless na camada de aplicação |
| Autorização | Proxy OAuth 2.1 customizado → Firebase Auth; DCR + PKCE + refresh; descoberta RFC 8414/9728 | **DCR deprecado → CIMD**; RFC 9207 `iss` ausente |
| Rate limiting | Janela fixa no Firestore (mensal por usuário + janela curta por IP) | Não afetado |
| Deploy | Cloud Run (min 0 / max 5) + GCLB (roteamento por path) + Cloud CDN (portal) | Sessões de transporte amarram as réplicas |

> **Nota sobre "gateway":** este projeto não possui um gateway que inspeciona corpo de requisição. No [ADR-004](../adrs/004-resultados-poc.md), o "gateway remoto e stateless" *é* o próprio servidor FastMCP. O GCLB realiza apenas roteamento por path. O item de roteamento por cabeçalhos (§5.2) é, portanto, um habilitador futuro, e não a remoção de um componente existente.

## 4. Achados

### 4.1 Migração stateless

A camada de aplicação já é stateless (o estado vive no Firestore e nas custom claims do Firebase); restam apenas **sessões de transporte**, herdadas do FastMCP 3.x / SDK v1.

- O `2026-07-28` retira o handshake `initialize`/`initialized` e o cabeçalho `Mcp-Session-Id`; cada requisição carrega sua versão de protocolo e capacidades do cliente em `_meta`.
- Uma nova RPC `server/discover` (implementação **OBRIGATÓRIA** para servidores) anuncia versões suportadas, capacidades e identidade.
- Caminho de migração: FastMCP 4 + MCP Python SDK v2, com negociação `mode="auto"` no cliente, de modo que um único deployment atenda clientes da era handshake e da era moderna.
- **Opção interina disponível hoje:** o FastMCP 3.4.4 suporta `http_app(stateless_http=True)` (ou a variável de ambiente `FASTMCP_STATELESS_HTTP=true`), o que remove a necessidade de afinidade de sessão antes do upgrade para 4.0.

### 4.2 Simplificação de infraestrutura

- **Cache de listas.** `ttlMs` e `cacheScope` agora são obrigatórios em `tools/list`, `prompts/list`, `resources/list`, `resources/read` e `resources/templates/list`. O FastMCP 4 expõe `FastMCP(cache_ttl=..., cache_scope=...)`. Isso reduz re-buscas e estabiliza caches de prompt a montante.
- **Ordenação determinística.** Servidores **DEVEM** (SHOULD) retornar `tools/list` em ordem estável para melhorar o cache no cliente e de prompt.
- **Roteamento por cabeçalhos.** `Mcp-Method`, `Mcp-Name` (e `Mcp-Param-*`) são obrigatórios em POSTs, permitindo que um load balancer, WAF ou gateway roteie, meça e autorize **sem parsear o corpo JSON**. O FastMCP não remove esses cabeçalhos.
- **Não há deep packet inspection a remover hoje** — o GCLB roteia por path; não existe componente que inspecione o corpo na stack atual.

### 4.3 Autorização

Implementação atual: um proxy OAuth 2.1 customizado na frente do Firebase Auth (Google Identity Platform).

| Mudança no `2026-07-28` | `jor-mcp` atual | Lacuna |
|---|---|---|
| CIMD preferido; DCR deprecado | `/api/oauth/register` implementa DCR | Adotar CIMD (manter fallback de DCR) |
| RFC 9207 `iss` nas respostas de autorização; clientes validam | Não emitido pelo redirect de consentimento | Portal deve acrescentar `iss` |
| SEP-837 `application_type` no DCR | Ignorado por `ClientRegistrationRequest` | Adicionar validação |
| SEP-2352 credenciais vinculadas ao issuer | Concern do lado do cliente | Nenhuma no servidor |

Escopo acordado para esta spike: **apenas CIMD + RFC 9207** (sem migração para IdP enterprise / EMA).

### 4.4 Breaking changes e deprecações

**Retirados (breaking):**

- Handshake `initialize` / `notifications/initialized`.
- Cabeçalho `Mcp-Session-Id`; sessões no nível de protocolo.
- `ping`, `logging/setLevel`, `notifications/roots/list_changed`.
- Endpoint HTTP GET e `resources/subscribe` / `resources/unsubscribe` → substituídos por `subscriptions/listen`.
- Ressumabilidade do stream SSE (`Last-Event-ID`, IDs de evento).

**Novos requisitos:**

- `server/discover` (servidores DEVEM implementar).
- `resultType` em todo resultado (`"complete"` | `"input_required"`).
- Campo `extensions` nas capacidades.
- `CacheableResult` (`ttlMs`, `cacheScope`).
- Cabeçalhos `Mcp-Method` / `Mcp-Name` nos POSTs.

**Alterados:**

- Código de erro de recurso não encontrado `-32002` → `-32602`.
- Tasks movidas para a extensão `io.modelcontextprotocol/tasks` (poll via `tasks/get`, `tasks/update`).
- Multi Round-Trip Requests (MRTR) substituem requisições iniciadas pelo servidor (`sampling`/`elicitation`/`roots`).

**Deprecados (janela de 12 meses):** Roots, Sampling, Logging; o transporte HTTP+SSE; o DCR; os valores de `includeContext` `"thisServer"` / `"allServers"`.

**Nossa exposição:** o transporte `/mcp/sse` e o DCR. Não usamos sampling, roots nem logging.

### 4.5 Outras observações

- O `2026-07-28` documenta a propagação de contexto de trace do OpenTelemetry em `_meta` (`traceparent`, `tracestate`, `baggage`) — já usamos auto-instrumentação OTel.
- A extensão Tasks é candidata para ingestão de longa duração no futuro.
- MCP Apps e MCP tunnels estão fora do escopo desta avaliação.

## 5. Oportunidades Priorizadas

| # | Oportunidade | Impacto | Esforço | Notas |
|---|---|---|---|---|
| 1 | Habilitar `stateless_http=True` (funciona no 3.4.4 hoje) | Alto | XS | Remove afinidade de sessão antes do 4.0 |
| 2 | Adicionar `ttlMs` / `cacheScope` (`FastMCP(cache_ttl=, cache_scope=)`) | Médio | XS | Catálogo de ferramentas cacheável |
| 3 | Ordenação determinística em `tools/list` | Médio | S | Taxa de acerto do cache de prompt |
| 4 | Mover a URL do cliente de `/mcp/sse` → Streamable HTTP | Alto | S | Transporte SSE deprecado |
| 5 | Upgrade FastMCP 3.4.4 → 4.0 + MCP SDK v2 | Alto | M | `mode="auto"` atende as duas eras |
| 6 | Suporte a CIMD no proxy (mantendo fallback de DCR) | Médio | M | Registro padrão da spec |
| 7 | RFC 9207 `iss` (portal) + SEP-837 `application_type` | Baixo | S | Conformidade de auth |
| 8 | Metadados de roteamento por cabeçalhos para LB/gateway | Baixo agora | S | Habilita medição futura sem DPI |
| 9 | Propagação de trace OTel em `_meta` | Baixo | S | Documentado na spec |
| 10 | Extensão Tasks (ingestão de longa duração) | Futuro | L | Somente se houver trabalho assíncrono |

## 6. Próximos Passos Recomendados

1. Aplicar os ganhos rápidos #1–#4 no `fastmcp 3.4.4` (sem upgrade major).
2. Prototipar o #5 em uma branch; validar as duas eras de protocolo contra o Claude.
3. Implementar #6–#7 como tarefas de follow-up com escopo definido.
4. Acompanhar a janela de deprecação de `/mcp/sse` e do DCR.
5. Reavaliar o #10 (Tasks) quando a ingestão assíncrona for necessária.

## 7. Fora de Escopo

- Migração para IdP enterprise (Entra/Okta) e Enterprise Managed Authorization (EMA).
- Extensão MCP Apps.
- MCP tunnels.

## 8. Questões Abertas

- Data-alvo para retirar o `/mcp/sse` e mover os clientes para o Streamable HTTP.
- Se o CIMD deve se tornar o único mecanismo de registro quando o DCR for removido.
- Se o Tasks será necessário no roadmap de ingestão.

## 9. Fontes

- Especificação MCP `2026-07-28` — https://modelcontextprotocol.io/specification/2026-07-28
- Principais mudanças / changelog do MCP `2026-07-28` — https://modelcontextprotocol.io/specification/2026-07-28/changelog
- "The 2026-07-28 Specification" — https://blog.modelcontextprotocol.io/posts/2026-07-28/
- "Bringing MCP 2026-07-28 to Claude" — https://claude.com/resources/articles/bringing-mcp-2026-07-28-to-claude
- Documentação do FastMCP — https://gofastmcp.com (modo stateless, CIMD, cache de respostas, guia de upgrade)
