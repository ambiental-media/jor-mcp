<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Métricas Técnicas

Relatório operacional pós-lançamento do servidor Jor-MCP, construído exclusivamente a partir da telemetria já existente no momento do snapshot. Nenhuma instrumentação, configuração ou tráfego sintético foi adicionado para produzir este relatório.

| Campo | Valor |
|---|---|
| Data do snapshot | 2026-10-25 |
| Janela de medição | 2026-09-25T20:28:36Z → 2026-10-25 (30 dias, retenção total dos logs) |
| Serviço | `jor-mcp-server` |
| Revisão | `jor-mcp-server-00018-dxn` (imagem `v0.13.1`) |
| Projeto GCP | `jor-mcp`, região `us-central1` |
| Runtime | Cloud Run, 1 vCPU / 1 GiB, concorrência 80, timeout 300 s, mínimo de instâncias 0, máximo 5 |

## 1. Resumo Executivo

| # | Indicador | Meta | Medido | Veredito |
|---|---|---|---|---|
| 1 | Tempo de resposta | Média < 10 s | Média **1,03 s**, p95 **0,90 s**, p99 **12,42 s** | **Aprovado** na média; cauda e cold start em risco |
| 2 | Disponibilidade | ≥ 95% | Infra **99,64%**, tráfego legítimo **98,30%**; 2 dias abaixo de 95% | **Aprovado** em 30 dias; **reprovado** em 2 dias isolados |
| 3 | Integração com assistentes | ≥ 2 assistentes | Claude (580 chamadas) + conector ChatGPT (22 chamadas); Gemini ausente | **Aprovado** |
| 4 | Precisão das consultas | ≥ 90% relevante | 35,7% das buscas sem resultado; sem rótulos de relevância | **Não demonstrado** |
| 5 | Atualizações em tempo real | Sem reindexação | Sem cache, sem índice; sonda ao vivo mostrou 0 de defasagem | **Aprovado** por design; evidência pontual |

## 2. Fontes de Dados e Método

Todos os dados são telemetria armazenada, lida com escopos somente-leitura por meio da impersonação de `mcp-viewer@jor-mcp.iam.gserviceaccount.com`.

| Fonte | Conteúdo utilizado |
|---|---|
| Cloud Monitoring | `run.googleapis.com/request_count`, `request_latencies`, `container/startup_latencies`, `container/cpu/utilizations`, `container/memory/utilizations`, `container/instance_count` |
| Cloud Logging `run.googleapis.com/requests` | Status, latência, URL, método, user agent e trace ID por requisição |
| Cloud Logging `run.googleapis.com/stdout` | Logs estruturados em JSON: queries de busca, contagem de resultados, eventos de autenticação, erros de ferramenta |
| Especificação da revisão Cloud Run | Variáveis de ambiente, escalonamento e timeouts implantados |

### 2.1 Service Level Indicators

- **Disponibilidade de infraestrutura** = `1 − (5xx / todas as requisições)`. Inclui ruído de scanners da internet.
- **Disponibilidade de tráfego legítimo** = `1 − (5xx / requisições para /mcp* e /api/oauth*)`. Exclui caminhos de scanner (`/`, `/.env`, `/wp-*`, `/ws`, `/socket.io`, `/raw`) que nunca chegam à aplicação MCP.
- **Tempo de resposta** = latência de `POST /mcp` com status `200`/`202`, lida dos request logs.
- **Excluído do tempo de resposta:** sessões SSE de `GET /mcp`. São streams longos mantidos abertos até o timeout de 300 s (p95 observado de 310 s), portanto sua duração mede o tempo de vida da sessão, não a latência da consulta.

### 2.2 Estado da Instrumentação no Snapshot

- O tracing da aplicação existe mas não era exportado: `OTEL_EXPORTER_OTLP_ENDPOINT` aponta para `http://localhost:4318` e `OTEL_TRACES_EXPORTER` está ausente, então o exportador resolve para `none`. Nenhum span chega ao Cloud Trace.
- Não havia dashboards, uptime checks, políticas de alerta ou métricas baseadas em log no Cloud Monitoring.
- Os logs da aplicação carregam `trace_id`/`span_id`, permitindo correlacionar request logs e logs de aplicação (ver Seção 8).

## 3. Tempo de Resposta (Indicador 1)

Fonte: 1.326 requisições `POST /mcp` bem-sucedidas (status 200/202), janela de 30 dias.

| Métrica | Valor |
|---|---|
| Requisições | 1.326 |
| Média | **1,03 s** |
| p50 | 0,15 s |
| p90 | 0,61 s |
| p95 | 0,90 s |
| p99 | 12,42 s |
| Máximo | 301,00 s |
| Requisições > 10 s | 21 (1,58%) |
| Dentro da meta | **98,42%** |

### 3.1 Por Cliente

| Cliente (família de user agent) | Chamadas | Média | p95 | Primeira vez | Última vez |
|---|---|---|---|---|---|
| `Claude-User` | 580 | 1,27 s | 0,56 s | 2026-09-25 | 2026-10-24 |
| `codex-mcp-client` | 382 | 0,17 s | 0,74 s | 2026-10-20 | 2026-10-20 |
| `opencode` | 188 | 0,22 s | 0,49 s | 2026-09-27 | 2026-10-25 |
| `python-httpx` | 106 | 2,81 s | 12,42 s | 2026-09-25 | 2026-10-24 |
| `openai-connectors-oauth` | 18 | 1,96 s | 13,08 s | 2026-10-20 | 2026-10-25 |
| `braintrust-mcp-client` | 18 | 9,59 s | 58,05 s | 2026-10-21 | 2026-10-22 |
| `Mozilla` (testes manuais) | 13 | 0,44 s | 0,65 s | 2026-10-11 | 2026-10-22 |
| `undici` | 6 | 0,13 s | 0,21 s | 2026-10-21 | 2026-10-21 |
| `openai-mcp` | 4 | 0,81 s | 2,76 s | 2026-10-20 | 2026-10-20 |

### 3.2 Ressalva de Cold Start

O mínimo de instâncias é `0`, então a primeira requisição após um período ocioso espera pela inicialização do container. O p95 de `run.googleapis.com/container/startup_latencies` foi de **24,03 s** na janela. Esse tempo não entra na latência de requisição do Cloud Run, mas entra na espera percebida pelo usuário, portanto uma requisição a frio pode ultrapassar a meta de 10 s mesmo com média reportada de 1,03 s.

**Veredito:** meta cumprida na média. Latência de cauda (p99 = 12,42 s) e cold start (p95 = 24,03 s) são os dois riscos que devem acompanhar o número médio.

## 4. Disponibilidade (Indicador 2)

Fonte: 25.408 entradas de request log em 30 dias.

| SLI | Numerador | Denominador | Resultado |
|---|---|---|---|
| Disponibilidade de infraestrutura | 25.317 sem 5xx | 25.408 | **99,64%** |
| Disponibilidade de tráfego legítimo | 4.101 sem 5xx | 4.172 requisições legítimas | **98,30%** |

Distribuição de status (30 dias):

| Status | Contagem | Participação |
|---|---|---|
| 401 | 22.262 | 87,6% |
| 200 | 2.033 | 8,0% |
| 404 | 416 | 1,6% |
| 202 | 261 | 1,0% |
| 400 | 247 | 1,0% |
| 502 | 71 | 0,28% |
| 429 | 68 | 0,27% |
| 201 | 26 | 0,10% |
| 500 | 20 | 0,08% |
| 409 | 4 | 0,02% |

A maioria de 401 é varredura da internet: requisições para `/.env`, `/wp-login.php`, `/socket.io/`, caminhos raiz e user agents de crawler como `libredtail-http`, `l9explore`, `zgrab` e `WP-Safe-Scanner`. Essas tentativas nunca chegam à aplicação MCP, por isso a razão bruta de 2xx (8,0%) não serve como medida de disponibilidade.

### 4.1 Decomposição dos 5xx

| Status | Caminho | Contagem | Causa |
|---|---|---|---|
| 502 | `/api/oauth/token` | 54 | Falha do upstream do proxy de token OAuth, concentrada em 2026-10-12 → 2026-10-16 |
| 502 | `/api/oauth/approve` | 17 | Falha do upstream do proxy de consentimento OAuth, mesmo período |
| 500 | `/ws`, `/socket.io/`, `/raw`, `/` | 20 | Tráfego de scanner em rotas não suportadas |

Nenhum 5xx foi registrado no próprio `/mcp`.

### 4.2 Série Diária

| Data | Requisições | 5xx | Disponibilidade de infra | Disponibilidade legítima |
|---|---|---|---|---|
| 2026-09-25 | 49 | 0 | 100,00% | 100,00% |
| 2026-09-26 | 498 | 0 | 100,00% | 100,00% |
| 2026-09-27 | 1.074 | 4 | 99,63% | 100,00% |
| 2026-09-28 | 734 | 0 | 100,00% | 100,00% |
| 2026-09-29 | 431 | 0 | 100,00% | 100,00% |
| 2026-09-30 | 692 | 0 | 100,00% | 100,00% |
| 2026-10-01 | 285 | 0 | 100,00% | 100,00% |
| 2026-10-02 | 828 | 0 | 100,00% | 100,00% |
| 2026-10-03 | 721 | 0 | 100,00% | 100,00% |
| 2026-10-04 | 395 | 0 | 100,00% | 100,00% |
| 2026-10-05 | 1.239 | 0 | 100,00% | 100,00% |
| 2026-10-06 | 285 | 4 | 98,60% | 100,00% |
| 2026-10-07 | 1.298 | 0 | 100,00% | 100,00% |
| 2026-10-08 | 949 | 0 | 100,00% | 100,00% |
| 2026-10-09 | 468 | 0 | 100,00% | 100,00% |
| 2026-10-10 | 625 | 0 | 100,00% | 100,00% |
| 2026-10-11 | 1.036 | 0 | 100,00% | 100,00% |
| 2026-10-12 | 476 | 4 | 99,16% | 95,65% |
| 2026-10-13 | 1.767 | 19 | 98,92% | 97,47% |
| 2026-10-14 | 1.316 | 36 | 97,26% | **94,04%** |
| 2026-10-15 | 1.862 | 8 | 99,57% | 97,52% |
| 2026-10-16 | 739 | 6 | 99,19% | **72,73%** |
| 2026-10-17 | 522 | 0 | 100,00% | 100,00% |
| 2026-10-18 | 316 | 0 | 100,00% | 100,00% |
| 2026-10-19 | 1.308 | 2 | 99,85% | 95,00% |
| 2026-10-20 | 1.734 | 0 | 100,00% | 100,00% |
| 2026-10-21 | 1.434 | 0 | 100,00% | 100,00% |
| 2026-10-22 | 1.005 | 0 | 100,00% | 100,00% |
| 2026-10-23 | 239 | 4 | 98,33% | 100,00% |
| 2026-10-24 | 454 | 0 | 100,00% | 100,00% |
| 2026-10-25 | 629 | 4 | 99,36% | 100,00% |

Dois dias ficam abaixo da meta de 95%: 2026-10-14 (94,04%) e 2026-10-16 (72,73%). O valor de 2026-10-16 vem de um denominador pequeno (11 requisições legítimas, 3 falhas), então uma chamada OAuth com falha desloca a taxa diária em nove pontos.

**Veredito:** o agregado de 30 dias cumpre a meta nas duas definições. A série diária não cumpre, e a causa é integralmente o proxy OAuth, não o endpoint MCP.

## 5. Integração com Assistentes de IA (Indicador 3)

Fonte: user agents em requisições `POST /mcp` bem-sucedidas, cruzados com logs de autenticação da aplicação.

| Assistente / cliente | Família | Chamadas | Evidência |
|---|---|---|---|
| Claude Desktop | `Claude-User` | 580 | Ativo de 2026-09-25 a 2026-10-24 |
| Conector ChatGPT | `openai-connectors-oauth`, `openai-mcp` | 22 | Primeira ocorrência em 2026-10-20, ativo até 2026-10-25 |
| OpenAI Codex CLI | `codex-mcp-client` | 382 | Execução de um único dia, 2026-10-20 |
| OpenCode | `opencode` | 188 | 2026-09-27 → 2026-10-25 |
| Cliente de avaliação Braintrust | `braintrust-mcp-client` | 18 | 2026-10-21 → 2026-10-22 |
| Gemini | — | 0 | **Nenhuma requisição na janela** |

Evidência de autenticação: 1.493 eventos `Authenticated request` nos logs da aplicação, incluindo metadados de tier (`tier: pro`) emitidos pelo fluxo OAuth.

**Veredito:** a meta de dois assistentes é cumprida (Claude e ChatGPT). A integração com Gemini não é comprovada pelos dados.

## 6. Eficácia das Consultas (Indicador 4)

Apenas medição Tier A foi autorizada: estatísticas derivadas das queries já registradas, sem replay de consultas e sem julgamento de relevância. Esta seção reporta proxies, não precisão.

Fonte: 28 buscas registradas, 23 queries distintas.

| Métrica | WordPress | GitHub |
|---|---|---|
| Buscas | 28 | 28 |
| Média de resultados | 2,29 | **0,00** |
| Mediana de resultados | 1 | 0 |
| Máximo de resultados | 7 | 0 |
| Buscas sem resultado | 10 (35,7%) | 28 (100%) |
| Falhas de upstream | 0 | 0 |
| Resultados malformados descartados | 0 | 0 |

Atividade relacionada: 18 eventos `WordPress article fetched`, 0 erros de busca de artigo e 10 eventos `Error calling tool 'search_content'`. A ferramenta lança `ToolError` exatamente quando o conjunto merged de resultados está vazio, então esses 10 erros correspondem às 10 buscas sem resultado.

Queries sem resultado observadas:

- `Formoso do Rio Preto`
- `Operação Faroeste`
- `Cerrado Amazon water cycle rivers water`
- `rios voadores`
- `Cerrado Amazônia rios voadores`
- `Cerrado Amazônia bacias hidrográficas rios voadores`
- `Cerrado Amazônia chuvas rios voadores`
- `Jor-MCP` (repetida)

Dois achados limitam qualquer afirmação de precisão:

1. **A fonte GitHub retornou zero resultados em todas as buscas observadas.** Ou o corpus i18n não contém os termos consultados, ou o matcher em memória não está alcançando esse conteúdo. Com 28 de 28 vazios, a fonte não contribui para a eficácia da busca.
2. **Mais de um terço das buscas termina sem resposta alguma.** Uma resposta vazia não é uma resposta errada, mas do ponto de vista da intenção do usuário continua sendo uma consulta frustrada.

**Veredito:** a meta de 90% de precisão não pode ser afirmada com a telemetria existente. Não há rótulos de relevância, identificadores de resultado ou feedback de usuário nos logs, e o caminho de busca é por palavra-chave (parâmetro `search` do WordPress mais substring sobre JSON do GitHub), não semântico.

## 7. Atualizações em Tempo Real (Indicador 5)

A atualidade aqui é uma propriedade arquitetural, não um pipeline: não existe índice nem camada de cache.

- `src/services/wordpress.py` busca cada matéria diretamente na REST API do WordPress (`_fetch_post_by_id`, `_fetch_post_by_slug`, `fetch_latest_posts`).
- `src/services/github.py` lê os arquivos do repositório a cada chamada (`_fetch_repo_files`, `fetch_github_i18n_content`).
- `pyproject.toml` não declara dependência de cache, e o `httpx.AsyncClient` compartilhado em `src/http_client.py` configura apenas pooling e timeouts.

Sonda ao vivo em 2026-10-25:

| Verificação | Resultado |
|---|---|
| Último post do WordPress | id `4229`, publicado em `2026-10-14T16:10:04`, modificado em `2026-10-15T17:33:47` |
| REST API do WordPress no momento da sonda | Mesmos valores de `id`, `date` e `modified` |
| Caminho de dados do Jor-MCP | Chama o mesmo endpoint REST em toda requisição |

Defasagem medida no momento da sonda: **0**. Mudanças editoriais ficam visíveis na consulta seguinte; não há etapa de reindexação a esperar.

**Veredito:** meta cumprida por design. A evidência é uma sonda pontual mais inspeção de código, porque não existe série histórica de atualidade na telemetria armazenada.

## 8. Evidências

Todos os comandos foram executados em modo somente-leitura contra o projeto `jor-mcp`, com impersonação de `mcp-viewer@jor-mcp.iam.gserviceaccount.com`. Endereços IP e identificadores de usuário estão redigidos.

### 8.1 Volume e Status das Requisições

```bash
gcloud logging read \
  'logName="projects/jor-mcp/logs/run.googleapis.com%2Frequests"
   AND timestamp>="2026-09-25T00:00:00Z"' \
  --limit=100000 --format=json
```

Exemplo de request log, sanitizado:

```json
{
  "httpRequest": {
    "latency": "0.131298442s",
    "requestMethod": "POST",
    "requestUrl": "https://jormcp.ambiental.media/mcp?codemode=false",
    "status": 200,
    "userAgent": "opencode/latest/2.1.2/cli"
  },
  "resource": {
    "type": "cloud_run_revision",
    "labels": {
      "service_name": "jor-mcp-server",
      "revision_name": "jor-mcp-server-00018-dxn"
    }
  },
  "timestamp": "2026-10-25T19:40:44.725319Z",
  "trace": "projects/jor-mcp/traces/46e1ade1a6b3e5af783cec2a96dfe671"
}
```

Recorte de tempo de resposta:

```bash
gcloud logging read \
  'logName="projects/jor-mcp/logs/run.googleapis.com%2Frequests"
   AND httpRequest.requestMethod="POST"
   AND httpRequest.status=200' \
  --limit=100000 --format=json
```

### 8.2 Correlação de Trace

Duas entradas de log da aplicação que compartilham o trace acima, sanitizadas (`uid` substituído):

```json
{"timestamp": "2026-10-25T19:40:44.733335Z",
 "jsonPayload": {"logger": "src.middleware.auth",
                 "message": "Authenticated request",
                 "extra": {"tier": "pro", "uid": "<redacted>"}}}
{"timestamp": "2026-10-25T19:40:44.857615Z",
 "jsonPayload": {"logger": "uvicorn.access",
                 "message": "POST /mcp?codemode=false HTTP/1.1 200"}}
```

Essa correlação é o que permite ligar a latência de uma requisição à autenticação e à atividade da ferramenta, mesmo sem backend de traces.

### 8.3 Atividade de Busca

```bash
gcloud logging read \
  'logName="projects/jor-mcp/logs/run.googleapis.com%2Fstdout"
   AND jsonPayload.message="WordPress search completed"' \
  --limit=20000 --format=json
```

Entrada representativa:

```json
{
  "jsonPayload": {
    "logger": "src.tools",
    "message": "WordPress search completed",
    "extra": {"query": "grilagem Bahia", "result_count": 2}
  },
  "timestamp": "2026-10-22T19:52:37.343019Z"
}
```

### 8.4 Consultas ao Cloud Monitoring

```bash
# Volume de requisições por classe de status (30d)
gcloud monitoring time-series list \
  --project=jor-mcp \
  --filter='metric.type="run.googleapis.com/request_count"
            AND resource.labels.service_name="jor-mcp-server"'

# Percentis de latência de requisição (30d)
gcloud monitoring time-series list \
  --project=jor-mcp \
  --filter='metric.type="run.googleapis.com/request_latencies"
            AND resource.labels.service_name="jor-mcp-server"'

# Latência de cold start (30d)
gcloud monitoring time-series list \
  --project=jor-mcp \
  --filter='metric.type="run.googleapis.com/container/startup_latencies"
            AND resource.labels.service_name="jor-mcp-server"'
```

Agregação utilizada: período de alinhamento de 30 dias, `ALIGN_PERCENTILE_95` com `REDUCE_PERCENTILE_95` para distribuições, `ALIGN_SUM` com `REDUCE_SUM` para contadores.

### 8.5 Utilização de Recursos

| Métrica | Valor em 30 dias |
|---|---|
| Latência de startup do container p95 | 24,03 s |
| Utilização de CPU p95 | 2,0% do vCPU alocado |
| Utilização de memória p95 | 30,0% de 1 GiB |
| Máximo de instâncias observado | 5 (teto configurado) |

### 8.6 Sonda Pública de Saúde

```bash
curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' \
  https://jormcp.ambiental.media/api/oauth/health
# 200 0.804140s
```

`/health` retorna 404 pelo load balancer porque apenas `/mcp*` e `/api/oauth*` são roteados para o Cloud Run; `/api/oauth/health` é o endpoint de saúde alcançável.

## 9. Limitações

- **Teto de 30 dias.** A retenção do Cloud Logging limita a janela; não existe baseline anterior a setembro na telemetria armazenada.
- **Sem traces exportados.** `OTEL_TRACES_EXPORTER` está ausente na revisão implantada, então dados de span não estão disponíveis. Todos os números de latência vêm dos request logs.
- **Sem tempo por ferramenta.** Os logs registram texto da query e contagem de resultados, mas não a duração da ferramenta, portanto não é possível separar o tempo de WordPress e GitHub do tempo total da requisição.
- **Amostra de busca pequena.** 28 buscas em 30 dias bastam para proxies, não para um percentual de precisão. A maior parte do tráfego é handshake e listagem, não consulta substantiva.
- **Disponibilidade sem histórico de sonda.** Nunca houve uptime check configurado, então a disponibilidade é reconstruída dos request logs; um período sem tráfego apareceria como 100% de disponibilidade por ausência de falhas, não por evidência de saúde.
- **Cauda dominada por scanners.** 87,6% das requisições são sondagem não autenticada. Qualquer métrica calculada sobre contagem bruta deve declarar se inclui scanners.
- **Cold start fora da latência de requisição.** O p95 de startup de 24,03 s é reportado separadamente e não faz parte da média de 1,03 s.
- **Contagens são um recorte pontual.** O serviço continua recebendo tráfego durante a análise, então os totais podem variar em poucas requisições entre consultas.

## 10. Próximos Passos Recomendados de Medição

Nenhuma implementação foi realizada para este relatório. Caso os indicadores se tornem contratuais, as lacunas acima definem o trabalho mínimo de instrumentação:

| Lacuna | Mudança mínima |
|---|---|
| Latência e erro por ferramenta | Emitir os campos `duration_ms` e `tool` nos logs de ferramenta e derivar métricas baseadas em log |
| Visibilidade de traces | Definir `OTEL_TRACES_EXPORTER=otlp` com um coletor alcançável |
| Histórico de disponibilidade | Configurar uptime check em `/api/oauth/health` e política de alerta sobre a razão de 5xx |
| Precisão | Construir um conjunto golden de queries com julgamentos de relevância, avaliado offline |
| Atualidade | Registrar o timestamp `modified` do WordPress na busca e compará-lo com o timestamp da resposta |
