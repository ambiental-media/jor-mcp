<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# SPEC-003: Adequação de Roles e Rate Limiting

**Origem:** [Relatório: Roles e Rate Limiting](../relatorios/roles-e-rate-limiting.md)
**Status:** Implementada

## 1. Objetivo

Fazer com que a role atribuída manualmente pelo administrador no console passe a governar de fato o acesso e a cota do usuário, e bloquear qualquer chamada de usuário sem role atribuída.

- [x] Um usuário com `tier: "pro"` no Firestore recebe a cota de 2000 requisições/mês.
- [x] Um usuário sem `tier` (ou com valor não reconhecido) recebe **HTTP 403** em `/mcp` e não consome cota.
- [x] Um usuário sem `tier` não conclui o consentimento em `/api/oauth/approve`.
- [x] Documentação e contratos de API refletem o comportamento implementado.

## 2. Decisões de Design

**Fonte de verdade da role:** o documento `allowed_users/{email}` no Firestore, gerido manualmente pela equipe da Ambiental Media via console. É o que o [guia de implantação](../../2-replicacao/guia-de-implantacao.md) já instrui, e o que o comportamento desejado descreve.

**Propagação para o JWT:** sincronizar o campo `tier` do Firestore para uma *custom claim* do usuário no Firebase Auth via `auth.set_custom_user_claims(uid, {"tier": ...})` durante `/api/oauth/approve`. Diferentemente de `create_custom_token(uid, developer_claims=...)`, a claim persiste no perfil do usuário e é reemitida em todo refresh de token, o que mantém o custo por requisição em zero — o `AuthMiddleware` continua lendo a role do JWT já validado, sem leitura extra no Firestore.

**Ponto de bloqueio:** `AuthMiddleware`. Ele já decodifica o token e é o único lugar onde a rejeição pode ocorrer antes de qualquer consumo de cota. `tier` deixa de ter default `"basic"` e passa a ser obrigatório e validado contra o conjunto de roles conhecidas; ausência ou valor inválido resulta em `403 Forbidden` (não `401`: o usuário está autenticado, mas não autorizado).

**Janela de propagação:** a claim é gravada no consentimento e reconferida em toda renovação, então uma role alterada no console alcança quem já está conectado em até uma hora — o tempo de vida do ID token — sem novo consentimento.

**Revogação:** o grant `refresh_token` reconsulta a allow-list antes de renovar e chama `revoke_refresh_tokens` para um usuário desativado ou sem role. Revogar, e não apenas negar, importa porque a troca já devolveu um refresh token novo ao chamador.

**Política de falha:** a verificação de role é *fail-closed* — ao contrário dos rate limiters, que permanecem *fail-open* por serem uma proteção de custo, não de acesso. Como a role vem do JWT já validado, uma indisponibilidade do Firestore não afeta requisições de usuários com token válido.

## 3. Escopo das Alterações

### `src/api/oauth.py`
- `_is_email_allowed()` passa a retornar também a role do documento (ou `None`), em vez de apenas um booleano.
- `oauth_approve()` rejeita com `access_denied` quando o usuário não tem role válida, e chama `set_custom_user_claims(uid, {"tier": <role>})` antes de emitir o código de autorização.
- `_handle_refresh_token()` reconsulta a allow-list e ressincroniza a claim antes de renovar; rejeita com `invalid_grant` e revoga os refresh tokens quando o usuário foi desativado ou perdeu a role. Falha ao consultar (Firestore/Firebase indisponível) nega a renovação sem revogar — indisponibilidade não é revogação.

### `src/middleware/auth.py`
- `DecodedToken.tier` perde o default `"basic"` e passa a ser obrigatório, validado contra as roles conhecidas.
- Token sem `tier` ou com role desconhecida → `403` com corpo JSON padronizado e log de `warning` contendo o `uid`.

### `src/config.py` e `src/middleware/rate_limit.py`
- O mapa de cotas sai do middleware e vira `TIER_QUOTAS` em `config.py`: passa a ser a definição única de quais roles existem, consumida pelo `AuthMiddleware`, pelo rate limiter e pelo roteador OAuth sem que `api/` precise depender de `middleware/`.
- O fallback `user.get("tier", "basic")` é removido: nesse ponto a role já é garantida.

### `jor-mcp-site`
- A tela `/authorize` passa a tratar o usuário sem role como acesso negado, exibindo a mesma mensagem já usada para `status` inativo (a verificação decisiva continua no backend; a do portal é apenas UX).

### Documentação
- `guia-de-implantacao.md`: `tier` deixa de ser "opcional" e passa a ser campo obrigatório, com a consequência explícita de que sua ausência bloqueia o acesso.
- ADR-001 e ADR-006: registrar como as claims passam a ser populadas e remover a referência ao painel `/admin` inexistente (ou reclassificá-la como trabalho futuro).

## 4. Estratégia de Testes

- `tests/test_auth_middleware.py`: token sem `tier` → 403; token com role desconhecida → 403; token com `basic`/`pro` → escopo populado corretamente.
- `tests/test_rate_limit_middleware.py`: cota de `pro` aplicada de fato (o teste `test_unknown_tier_falls_back_to_basic_limit` deixa de fazer sentido e é substituído pelo cenário de rejeição no `AuthMiddleware`).
- `tests/test_oauth_router.py`: approve sem role → 403; approve com role desconhecida → 403; approve com role → `set_custom_user_claims` chamado com o valor correto; refresh de usuário desativado → `invalid_grant` com revogação; refresh com role divergente → claim ressincronizada e token reemitido; Firestore ou Firebase indisponível → `502` sem revogar.
- `firebase_admin` permanece mockado; nenhum teste toca a rede.

## 5. Limites (Boundaries)

- **Sempre fazer:** manter o Firestore como fonte de verdade da role; manter a verificação de role *fail-closed*; manter os rate limiters *fail-open*.
- **Perguntar antes:** antes de introduzir novas roles além de `basic` e `pro`; antes de alterar o esquema da coleção `allowed_users`.
- **Nunca fazer:** nunca inferir role a partir de domínio de e-mail ou de qualquer heurística; nunca logar tokens ou claims completas.

## 6. Questões em Aberto

- **Usuários já ativos:** quem já está conectado tem credencial emitida antes desta mudança, que não carrega `tier`. É preciso **refazer o consentimento** para a claim ser gravada — ou a equipe roda um script único percorrendo `allowed_users` e chamando `set_custom_user_claims`. Definir qual caminho adotar antes do deploy.
