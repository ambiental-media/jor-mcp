<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Relatório: Roles e Rate Limiting Baseado em Roles

**Data:** 2026-08-10
**Tipo:** Investigação (spike)
**Escopo:** `jor-mcp` (backend Python) e `jor-mcp-site` (portal Next.js)
**Status:** F1, F2, F3 e F5 resolvidos pela [SPEC-003](../specs/SPEC-003-adequacao-roles.md). F4 permanece como trabalho futuro.

---

## 1. Sumário Executivo

O rate limiting baseado em roles **está implementado no código, mas nunca é exercitado em produção**: a role (chamada de `tier` no código) é lida de uma *custom claim* do JWT do Firebase que **nenhum ponto do sistema jamais escreve**. Como consequência, todo usuário autenticado cai no valor padrão `"basic"` e recebe a cota de 500 requisições/mês, independentemente do que estiver registrado no Firestore.

Existem duas divergências relevantes em relação ao comportamento desejado:

1. Não há atribuição de role — nem manual, nem automática. O campo `tier` documentado na coleção `allowed_users` **é ignorado pelo código**.
2. Não há bloqueio para usuário sem role. A ausência de role resulta em *fallback* silencioso para `basic`, ou seja, o sistema é *fail-open* exatamente onde deveria ser *fail-closed*.

A adequação está especificada em **[SPEC-003: Adequação de Roles e Rate Limiting](../specs/SPEC-003-adequacao-roles.md)**.

---

## 2. Como as Roles Estão Modeladas Hoje

A nomenclatura "role" não existe no código. O conceito equivalente é **`tier`**, com dois valores previstos:

| Role (`tier`) | Cota mensal | Variável de ambiente |
| :--- | :--- | :--- |
| `basic` | 500 requisições | `RATE_LIMIT_BASIC_REQUESTS` |
| `pro` | 2000 requisições | `RATE_LIMIT_PRO_REQUESTS` |

Definição das cotas em [config.py:21-24](../../../../src/config.py#L21-L24) e mapeamento em [rate_limit.py:35-38](../../../../src/middleware/rate_limit.py#L35-L38).

O `tier` é declarado como campo do JWT decodificado em [auth.py:25-30](../../../../src/middleware/auth.py#L25-L30):

```python
class DecodedToken(BaseModel):
    uid: str
    email: str | None = None
    tier: str = "basic"
```

O valor default `"basic"` é o ponto central de todos os achados abaixo: como a claim nunca é emitida, **este default é o único valor que o sistema já produziu**.

---

## 3. Fluxo Real, do Cadastro à Requisição

| # | Etapa | Onde | O que acontece com a role |
| :--- | :--- | :--- | :--- |
| 1 | Admin cadastra o usuário | Console do Firebase → `allowed_users/{email}` | Grava `status: "active"` e, opcionalmente, `tier` |
| 2 | Usuário faz login Google no portal | [page.jsx:131-136](../../../../../jor-mcp-site/src/app/[locale]/authorize/page.jsx#L131-L136) | Lê apenas `status`; `tier` não é lido |
| 3 | Portal chama `/api/oauth/approve` | [oauth.py:342-346](../../../../src/api/oauth.py#L342-L346) | `_is_email_allowed()` valida apenas `status == "active"`; `tier` não é lido |
| 4 | Backend emite os tokens | [oauth.py:402](../../../../src/api/oauth.py#L402) | `auth.create_custom_token(uid)` — **sem `developer_claims`** |
| 5 | Cliente MCP chama `/mcp` | [auth.py:74-83](../../../../src/middleware/auth.py#L74-L83) | Token não contém `tier` → Pydantic aplica o default `"basic"` |
| 6 | Rate limiter aplica a cota | [rate_limit.py:76-77](../../../../src/middleware/rate_limit.py#L76-L77) | `_TIER_QUOTAS["basic"]` → 500 req/mês para todos |

Confirmação por varredura: **não existe nenhuma chamada a `set_custom_user_claims` / `setCustomUserClaims` em nenhum dos dois repositórios**, nem qualquer leitura do campo `tier` do Firestore.

---

## 4. Como o Rate Limit Consulta a Role

`RateLimitMiddleware` ([rate_limit.py](../../../../src/middleware/rate_limit.py)) roda logo após o `AuthMiddleware` e depende exclusivamente do que ele injetou no escopo ASGI:

```python
uid: str = user["uid"]
tier: str = user.get("tier", "basic")
max_requests: int = _TIER_QUOTAS.get(tier, RATE_LIMIT_BASIC)
```

- **Algoritmo:** janela fixa mensal no Firestore, documento `rate_limits/{uid}_YYYY-MM`, incrementado atomicamente com `firestore.Increment(1)`.
- **Origem da role:** `scope["user"]["tier"]`, populado apenas pelo `AuthMiddleware` a partir do JWT. **Nenhuma consulta ao Firestore é feita para descobrir a role.**
- **Role desconhecida:** `_TIER_QUOTAS.get(tier, RATE_LIMIT_BASIC)` rebaixa silenciosamente para a cota `basic` — comportamento coberto pelo teste `test_unknown_tier_falls_back_to_basic_limit` ([test_rate_limit_middleware.py:243](../../../../tests/test_rate_limit_middleware.py#L243)).
- **Escopo ausente:** se `scope["user"]` não existir, o middleware repassa a requisição sem contabilizar ([rate_limit.py:69-73](../../../../src/middleware/rate_limit.py#L69-L73)). Isso é seguro hoje porque o `AuthMiddleware` já rejeitou a requisição, mas transfere para ele toda a responsabilidade do bloqueio.
- **Falha do Firestore:** *fail-open* — a requisição passa e um `warning` é logado.

---

## 5. Achados

### F1 — A claim `tier` nunca é emitida (causa raiz)
`_mint_firebase_tokens()` chama `auth.create_custom_token(uid)` sem `developer_claims`, e nenhum código chama `set_custom_user_claims`. O ID token resultante não tem `tier`. **Todo usuário é `basic`.** O tier `pro` é código morto na prática.

### F2 — O campo `tier` do Firestore é decorativo
O [guia de implantação](../../2-replicacao/guia-de-implantacao.md) instrui o administrador a preencher `tier` em `allowed_users/{email}` afirmando que ele "determina a cota de limite de taxa mensal do usuário". Nenhuma linha de código lê esse campo. Um usuário marcado como `pro` no console continua limitado a 500 requisições/mês, sem qualquer sinal de erro.

### F3 — Usuário sem role não é bloqueado
Não existe validação que rejeite uma requisição por ausência de role. O caminho de ausência é um default (`"basic"`) somado a um fallback (`_TIER_QUOTAS.get(...)`), ambos *fail-open*. Isso é o oposto do comportamento desejado.

### F4 — O painel `/admin` previsto na ADR-006 não existe
A [ADR-006](../adrs/006-estrategia-implementacao-oauth2-1.md) descreve um painel B2B para promover usuários de `basic` para `pro`. Não há rota `/admin` no `jor-mcp-site` — a única superfície de administração é o console do Firebase, que hoje escreve em um campo ignorado (F2).

### F5 — Documentação e ADRs descrevem um estado que não existe
A [ADR-001](../adrs/001-autenticacao-e-seguranca.md) afirma que "o limitador de taxa do Firestore lê as claims de `tier` dos JWTs emitidos pelo Firebase para aplicar cotas diferenciadas". A leitura existe; a emissão das claims, não. Documentação, ADRs e código precisam ser reconciliados junto com a correção.

---

## 6. Gaps: Atual × Desejado

| Comportamento desejado | Estado atual | Gap |
| :--- | :--- | :--- |
| Role atribuída manualmente no console durante o cadastro | Admin preenche `tier` em `allowed_users`, mas o campo é ignorado | **Crítico** — a atribuição não produz efeito (F1, F2) |
| Usuário sem role não consegue chamar o sistema | Ausência de role → default `basic` → 500 req/mês liberadas | **Crítico** — *fail-open* onde deveria ser *fail-closed* (F3) |
| Rate limit diferenciado por role | Implementado, porém alimentado por uma claim inexistente | **Crítico** — `pro` inalcançável (F1) |
| Superfície administrativa para gerir roles | Apenas o console do Firebase | **Médio** — aceitável no curto prazo (F4) |

---

## 7. Encaminhamento

Todas as divergências acima foram consolidadas na tarefa de adequação **[SPEC-003: Adequação de Roles e Rate Limiting](../specs/SPEC-003-adequacao-roles.md)**, que define a fonte de verdade da role, o ponto de bloqueio *fail-closed* e a reconciliação documental.
