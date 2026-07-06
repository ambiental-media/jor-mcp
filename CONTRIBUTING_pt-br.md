<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Contribuindo para o jor-mcp

Antes de mais nada, muito obrigado por considerar contribuir para o `jor-mcp`! São pessoas como você que tornam as ferramentas de código aberto para o jornalismo cada vez melhores.

Este documento fornece diretrizes e instruções para contribuir com este projeto.

## Tabela de Conteúdos
- [Código de Conduta](#código-de-conduta)
- [Pré-requisitos](#pré-requisitos)
- [Como Começar](#como-começar)
- [Padrões de Desenvolvimento](#padrões-de-desenvolvimento)
  - [Ambiente e Dependências](#ambiente-e-dependências)
  - [Linting e Formatação](#linting-e-formatação)
  - [Verificação de Tipos](#verificação-de-tipos)
  - [Docstrings e Comentários](#docstrings-e-comentários)
  - [Testes](#testes)
- [Enviando Alterações](#enviando-alterações)
- [Integração Contínua (CI)](#integração-contínua-ci)
- [Análise de Segurança](#segurança-sast-e-análise-de-dependências)
- [Relatando Bugs](#relatando-bugs)
- [Diretrizes de Formatação de Documentação](#diretrizes-de-formatação-de-documentação)

---

## Código de Conduta

Este projeto é dedicado a fornecer uma comunidade acolhedora, diversa e segura. Espera-se que os colaboradores ajam com integridade, respeito e profissionalismo. Vamos tornar as ferramentas de código aberto para o jornalismo melhores juntos!

---

## Pré-requisitos

Antes de contribuir para o `jor-mcp`, certifique-se de ter o seguinte instalado em sua máquina de desenvolvimento local:

*   **Python:** Versão `3.12` ou superior é necessária.
*   **uv:** Usamos o `uv` como nosso gerenciador de pacotes e projetos extremamente rápido. Siga as [instruções de instalação aqui](https://docs.astral.sh/uv/getting-started/installation/).
*   **Docker / Container Runtime:** (Opcional, mas recomendado) Útil para executar instâncias locais de teste de dependências ou iniciar o servidor em um ambiente conteinerizado. Você pode usar Docker Desktop, Docker Community Edition ou alternativas de código aberto como [Colima](https://github.com/abiosoft/colima) ou [Podman](https://podman.io/).
*   **Trivy:** Necessário para rodar a suíte completa de validação local (`make check` e `make check-container`). Siga as [instruções de instalação aqui](https://aquasecurity.github.io/trivy/latest/getting-started/installation/).

---

## Como Começar

Para começar a contribuir com o `jor-mcp`:
1.  **Fork e Clone:** Faça um fork do repositório no GitHub e clone-o localmente.
2.  **Configuração do Ambiente:** Inicialize as dependências usando `uv sync` para configurar seu ambiente virtual Python isolado.
3.  **Verificações Locais:** Execute `make check` para garantir que seu ambiente local passa na formatação, linting, tipagem e testes.
4.  **Execução Local:** Configure suas variáveis de ambiente no arquivo `.env` usando o modelo `.env.example` como base e execute `make run` para iniciar o serviço local.

---

## Padrões de Desenvolvimento

### 🌐 Idioma Padrão: Inglês

Embora este projeto tenha se originado no Brasil e suporte ferramentas em português, **o inglês é o idioma padrão estrito para todas as contribuições técnicas** devido ao nosso público e financiamento globais.

Toda informação destinada a usuários e desenvolvedores deve estar em inglês. Isso inclui explicitamente:
*   Descrições de Pull Requests e comunicações gerais
*   Mensagens de commit
*   Comentários de código e nomes de variáveis
*   Documentação do repositório (como este arquivo)
*   Documentação técnica/arquitetura

*(Nota: A única exceção é o parâmetro `description` dentro dos decoradores `@mcp.tool()`, que atualmente visam contextos de LLM brasileiros, conforme observado na seção de Docstrings abaixo).*

Este projeto utiliza Python moderno (>= 3.12) e depende fortemente de programação assíncrona. Para entender o design de alto nível do sistema e especificidades de integração antes de contribuir, revise nossa **[Documentação Técnica](docs/pt-br/1-tecnico/)**.

Para manter alta qualidade de código e consistência, aplicamos rigorosamente os seguintes padrões. Certifique-se de que seu código adere a eles antes de enviar um Pull Request.

*(Nota: Agentes de IA que contribuem para este projeto devem adicionalmente aderir às regras definidas em `AGENTS.md`)*.

### Ambiente e Dependências

Usamos o [`uv`](https://github.com/astral-sh/uv) como nosso gerenciador de dependências padrão. **Não use o `pip` padrão ou `requirements.txt`.**

*   **Instalar dependências:** `uv sync`
*   **Adicionar uma nova dependência:** `uv add <pacote>`
*   **Executar um comando no ambiente isolado:** `uv run <command>`

### 🛠️ Utilitários Rápidos (Makefile)

Para agilizar o desenvolvimento local, este projeto fornece um `Makefile` com comandos agrupados:

*   **`make check`**: Executa toda a suíte de validação de uma vez. Isso inclui linting (`ruff`), verificação estrita de formatação, verificação de tipo estática (`mypy`), testes com imposição de 90% de cobertura mínima, SAST (`bandit`), auditoria de dependências (`pip-audit`) e uma varredura de vulnerabilidades de contêiner (`trivy`). **Você deve executar este comando antes de abrir um Pull Request.**
*   **`make check-sast`**: Executa testes de segurança estáticos de aplicação no código-fonte usando `bandit`.
*   **`make check-deps`**: Audita as dependências do projeto para vulnerabilidades conhecidas usando `pip-audit`.
*   **`make check-container`**: Constrói a imagem Docker e a escaneia para vulnerabilidades críticas usando `trivy`.
*   **`make run`**: Constrói a imagem Docker localmente e inicia o contêiner na porta 8080, lendo as configurações do seu arquivo `.env`.

### Linting e Formatação

Usamos o **Ruff** para todo o linting e formatação de código.

*   **Verificar o código (Lint):** `uv run ruff check .`
*   **Corrigir erros de lint seguros automaticamente:** `uv run ruff check . --fix`
*   **Formatar código:** `uv run ruff format .`

*As importações devem ser sempre absolutas (ancoradas em `src`) e ordenadas corretamente (imposto pelo Ruff).*

### Verificação de Tipos e Validação de Dados

Empregamos uma estratégia dupla para segurança de tipos para garantir um código robusto:

1.  **Verificação Estática de Tipos (Interna):** Todas as funções, métodos e variáveis devem ser totalmente anotados com dicas de tipo usando a sintaxe moderna do Python 3.12+ (ex: `list[dict[str, Any]]`, `str | None`). Não utilize importações com letras maiúsculas do módulo `typing` como `List`, `Dict` ou `Optional`.
    *   **Executar verificador de tipos:** `uv run mypy .`
2.  **Validação em Tempo de Execução (Fronteiras):** Usamos o **Pydantic (v2)** para validar todos os dados que entram no sistema a partir de fontes externas. Sempre que você estiver analisando respostas de APIs externas (como os JSONs do WordPress/GitHub), arquivos de configuração ou entradas de usuário, deve definir e usar um `BaseModel` do Pydantic para garantir que os dados correspondam ao esquema esperado antes de entrarem na lógica interna da aplicação.

### Logs
Dependemos da auto-instrumentação do OpenTelemetry. Não importe ou use SDKs do OpenTelemetry manualmente no código da aplicação.
Use o módulo de `logging` padrão do Python (`logger = logging.getLogger(__name__)`). Ao registrar dados de contexto, não use interpolação de strings; em vez disso, passe as variáveis usando o dicionário `extra={}` (ex: `logger.info("Solicitação bem-sucedida", extra={"target_url": url})`). Isso permite que o OpenTelemetry indexe as variáveis como atributos pesquisáveis.

### Docstrings e Comentários

*   **Padrão:** Use o **Formato de Docstring do Google (Google Style)** para todos os módulos, classes e funções complexas.
*   **Ferramentas MCP:** Se estiver escrevendo uma nova ferramenta do Model Context Protocol (usando o decorador `@mcp.tool()`), a string do parâmetro `description` **deve ser altamente detalhada e escrita em português**, pois o público-alvo é o jornalismo brasileiro. Isso é crítico para o contexto do LLM.
*   **Comentários:** Adicione comentários em linha com moderação. Concentre-se em explicar *por que* uma lógica complexa foi escrita de determinada maneira, em vez de *o que* ela faz.

### Testes

Usamos o **pytest** (junto com `pytest-asyncio` para nosso código assíncrono) para garantir a funcionalidade. Cada nova funcionalidade ou correção de bug deve incluir testes correspondentes no diretório `tests/`.

**Exigimos uma cobertura de código mínima de 90%.** Pull Requests que reduzam a cobertura abaixo desse limite não serão aceitos.

*   **Executar todos os testes:** `uv run pytest`
*   **Executar um arquivo de teste específico:** `uv run pytest tests/test_tools.py`
*   **Executar testes com relatório de cobertura:** `uv run pytest --cov=src --cov-fail-under=90`

---

## Enviando Alterações

Quando você estiver pronto para enviar um Pull Request, certifique-se de que suas contribuições estejam alinhadas com nossas automações de versionamento e padrões de documentação.

### Requisitos de Revisão de Documentação

Antes que qualquer alteração proposta possa ser integrada ao ramo `main`, você **deve** revisar o diretório `docs/` para garantir que toda a documentação relevante esteja atualizada com as alterações de seu código.

*   **Novas Funcionalidades/Ferramentas:** Atualize a [Referência Técnica](docs/pt-br/1-tecnico/).
*   **Alterações de Arquitetura/Lógica:** Atualize a [Referência Técnica](docs/pt-br/1-tecnico/).
*   **Novas Variáveis de Ambiente/Dependências:** Atualize os [Guias de Replicação](docs/pt-br/2-replicacao/).

Pull Requests que introduzirem alterações sem as atualizações de documentação correspondentes serão bloqueados.

### Estratégia de Ramificação (Branching) e Nomenclatura

Este repositório usa estritamente a estratégia de **[Trunk-Based Development com Branches de Funcionalidades Curtas](https://trunkbaseddevelopment.com/short-lived-feature-branches/)**. Certifique-se de que suas branches sejam pequenas, focadas e mescladas com frequência.

Os nomes das branches devem seguir a **[Especificação Convencional de Branches](https://conventional-branch.github.io/)**.

**Para Colaboradores Internos (Ambiental Media):**
Se você é um colaborador interno, é **obrigatório** incluir o ID do problema (Issue ID) relevante na declaração de sua branch usando o seguinte formato:
`<tipo>/<id-da-issue>-<descricao-curta>`

*Exemplo:* `feature/0fr4hyt6-wordpress-tool`

### Commits Convencionais

Usamos estritamente **[Commits Convencionais (v1.0.0)](https://www.conventionalcommits.org/en/v1.0.0/)** para nossas mensagens de commit.

Temos automações configuradas que analisam os Pull Requests mesclados para incrementar automaticamente as versões do projeto de acordo com a especificação de **[Versionamento Semântico 2.0.0 (SemVer)](https://semver.org/)**, além de preencher as tags e notas de lançamento (releases) do GitHub.

**As Regras:**
1. **Requisito Mínimo:** Pelo menos **um commit** no escopo do seu Pull Request deve respeitar estritamente o formato de Commits Convencionais (ex: `feat: add new search parameter`, `fix: resolve JWT validation error`).
2. **Incremento de Versão (Precedência):** Se o seu Pull Request contiver múltiplos commits convencionais, o incremento de versão automatizado (`MAJOR.MINOR.PATCH`) será determinado pelo commit de **maior precedência**. For exemplo, um `feat` dispara um incremento `MINOR`, tendo precedência sobre um `fix` (que dispara um incremento `PATCH`). Um `BREAKING CHANGE` dispara um incremento `MAJOR` e anula todos os outros.
3. **Notas de Lançamento:** Embora apenas o commit de maior precedência dite a alteração do número de versão, **todas** as informações fornecidas por todos os commits convencionais no Pull Request serão agregadas e usadas para preencher as notas de lançamento no GitHub.

---

## Integração Contínua (CI)

Todo Pull Request dispara automaticamente o pipeline de CI configurado em `.github/workflows/ci.yml`. O pipeline é dividido em dois jobs que devem passar antes que qualquer código possa ser mesclado.

### Job: `check`

Executa todas as validações de qualidade de código e segurança. Este job espelha o comando local `make check`, mas executa cada etapa individualmente para evitar qualquer desvio por meio de modificações no Makefile local.

| Etapa | Ferramenta | Comportamento |
|---|---|---|
| Lint | `ruff check .` | Relata problemas, nunca corrige automaticamente |
| Verificação de Formato | `ruff format --check .` | Relata problemas, nunca faz correções |
| Verificação de Tipagem | `mypy .` | Falha o job em caso de qualquer erro de tipo |
| Testes e Cobertura | `pytest --cov=src --cov-fail-under=90` | Falha se a cobertura cair abaixo de 90% |
| SAST | `bandit -c pyproject.toml -r src/` | Falha em descobertas de severidade média ou alta |
| Auditoria de Deps | `pip-audit` | Falha em caso de vulnerabilidades conhecidas |

### Job: `build-and-push`

Só é executado se o job `check` for concluído com sucesso. Constrói a imagem Docker, escaneia vulnerabilidades com o Trivy e envia para o Artifact Registry com a tag `:pr-<NUMERO_DO_PR>` (ex: `:pr-44`). Esta tag por PR é o que o pipeline de lançamento promove posteriormente para uma tag versionada (consulte [Lançamento e Versionamento](#lancamento-e-versionamento)).

| Etapa | Detalhe |
|---|---|
| Build | Imagem Docker construída a partir do `Dockerfile` do projeto |
| Varredura de Segurança | Trivy escaneia a imagem — falha se encontrar vulnerabilidades `CRITICAL` ou `HIGH` em bibliotecas |
| Push | Imagem enviada para o Artifact Registry com a tag `:pr-<NUMERO_DO_PR>` |

### Job: `commitlint`

Executa em paralelo com os outros jobs em cada Pull Request. Ele verifica se **pelo menos um commit** no intervalo do PR segue o formato de Commits Convencionais. Se nenhum commit corresponder, o job falha e o PR é bloqueado.

Esta é a barreira que possibilita o versionamento automatizado: o pipeline de lançamento (abaixo) lê esses commits convencionais para decidir o próximo número de versão. Consulte a seção de [Commits Convencionais](#commits-convencionais) para obter as regras.

### Lançamento e Versionamento

O versionamento é totalmente automatizado e reside em um workflow separado, `.github/workflows/release.yml`, que é executado **quando um Pull Request é mesclado na branch `main`** (não em cada push). Ele usa o [`python-semantic-release`](https://python-semantic-release.readthedocs.io/) para:

1. Analisar os Commits Convencionais no PR mesclado e calcular a próxima versão SemVer (`fix` → PATCH, `feat` → MINOR, `BREAKING CHANGE` → MAJOR).
2. Incrementar a `version` em `pyproject.toml`, enviar a tag git `vX.Y.Z` e publicar uma Release no GitHub com notas geradas automaticamente.
3. Promover a imagem: a imagem `:pr-<N>` construída durante o CI é renomeada no Artifact Registry para `:vX.Y.Z` e `:latest` — sem reconstrução, o mesmo digest é promovido.

A implantação em si é **manual**: o workflow `.github/workflows/cd.yml` é disparado sob demanda (`workflow_dispatch`) com a tag de imagem que você deseja implantar no Cloud Run. Mesclar um PR produz uma imagem versionada, mas **não** a implanta.

O workflow de implantação:
1. Verifica se a tag solicitada realmente existe no Artifact Registry (caso contrário, falha rapidamente).
2. Renderiza o `service.yaml` com o `envsubst`, substituindo apenas uma lista explícita de variáveis permitidas.
3. Implanta a imagem selecionada no Cloud Run via `gcloud run services replace`.

Como a implantação consome uma imagem existente por tag, ela é totalmente desacoplada do versionamento: você escolhe exatamente qual build chega à produção, e a etapa de deploy nunca altera a versão do projeto.

### Segredos do GitHub Necessários

Para que o job `build-and-push` se autentique no Google Cloud, o seguinte segredo deve ser configurado nas configurações do repositório por um mantenedor:

| Segredo | Descrição |
|---|---|
| `GCP_SA_KEY` | Chave JSON de uma Conta de Serviço do GCP com permissão de gravação (`roles/artifactregistry.writer`) |

### Interpretando Falhas no CI

*   **Falha de Lint/Formato:** Execute `uv run ruff check .` e `uv run ruff format --check .` localmente para ver os problemas relatados.
*   **Falha de Verificação de Tipagem:** Execute `uv run mypy .` localmente e corrija todos os erros de tipagem.
*   **Falha de Teste/Cobertura:** Execute `uv run pytest --cov=src --cov-fail-under=90` localmente. Garanta que o código novo possua testes correspondentes.
*   **Falha de SAST/Dependências:** Execute `make check-sast` ou `make check-deps` localmente para inspecionar os problemas.
*   **Falha de Varredura de Contêiner:** Uma vulnerabilidade crítica foi encontrada na imagem Docker. Revise o relatório do Trivy nos logs do CI e atualize a dependência ou imagem base afetada.

---

## Segurança SAST e Análise de Dependências

Este projeto integra três ferramentas de análise de segurança de código aberto para mitigar vulnerabilidades antes que qualquer código seja publicado. Todas as três ferramentas são executadas automaticamente no pipeline do CI, e duas delas (`bandit` e `pip-audit`) podem ser executadas localmente via o `Makefile`.

### Ferramentas

*   **Bandit** — Análise Estática de Segurança de Aplicação (SAST). Analisa o código-fonte Python em `src/` em busca de problemas comuns de segurança, como credenciais codificadas diretamente, chamadas de função inseguras e riscos de injeção.

*   **pip-audit** — Análise de Composição de Software (SCA). Audita todas as dependências do projeto (incluindo as dependências de desenvolvimento) contra bancos de dados de vulnerabilidades conhecidos (PyPA Advisory Database e OSV) para detectar pacotes com CVEs publicados.

*   **Trivy** — Varredor de vulnerabilidades de contêiner. Escaneia a imagem Docker construída em busca de vulnerabilidades críticas em pacotes de sistema operacional e dependências de aplicação. O Trivy é executado no pipeline de CI e **também deve ser instalado localmente** para executar `make check` e `make check-container` na sua máquina.

### Executando Localmente
```bash
# Apenas SAST (Bandit)
make check-sast

# Apenas Auditoria de Dependências (pip-audit)
make check-deps

# Apenas Varredura de Contêiner (requer Docker e Trivy instalados localmente)
make check-container

# Suíte completa de verificação (incluindo segurança)
make check
```

### Instalando o Trivy Localmente

O Trivy é a única ferramenta de segurança que requer uma instalação local separada (o Bandit e o pip-audit são instalados automaticamente via `uv sync`). Siga o [guia oficial de instalação do Trivy](https://aquasecurity.github.io/trivy/latest/getting-started/installation/) para o seu sistema operacional.

### Política de Severidade

O pipeline de CI falha a compilação em caso de:
- **Trivy:** Vulnerabilidades de biblioteca com severidade `CRITICAL` e `HIGH` (`--severity CRITICAL,HIGH`).
- **Bandit:** Descobertas de severidade `MEDIUM` e `HIGH`. A escala de severidade do Bandit é `LOW`/`MEDIUM`/`HIGH` (não há nível crítico), e a flag `-ll` no `ci.yml` define o limite como médio ou superior.

Descobertas abaixo desses limites são relatadas nos logs para conscientização, mas não bloqueiam o pipeline. Esses limites podem ser ajustados no arquivo de workflow `ci.yml` e no `pyproject.toml` (`[tool.bandit]`).

---

## Relatando Bugs

Por favor, relate qualquer bug, vulnerabilidade de segurança ou problemas de execução abrindo uma issue no GitHub. Inclua:
*   Um título claro e descritivo.
*   Passos para reproduzir o problema.
*   O comportamento esperado versus o comportamento real observado.
*   Logs relevantes, saídas de terminal ou referências a capturas de tela.

---

## Diretrizes de Formatação de Documentação

Esta seção define as regras estritas que todos os colaboradores humanos e IAs devem seguir ao criar ou modificar arquivos markdown no repositório `jor-mcp`.

### 1. Estrutura e Nomenclatura de Arquivos
*   **Apenas kebab-case:** Todos os arquivos markdown devem ser nomeados usando letras minúsculas e hífens (ex: `api-contracts.md`).
*   **Paridade Bilíngue:** Todos os arquivos em `docs/en/` devem ter uma tradução correspondente em `docs/pt-br/`.
*   **Sem espaços em caminhos:** Os nomes de diretórios devem seguir o padrão `kebab-case`.

### 2. Formatação Markdown
*   **Títulos:** Comece cada arquivo com um único `# Título 1` (Título). Use `##` e `###` para as seções subsequentes.
*   **Listas:** Sempre use hífens (`-`) para listas não ordenadas.
*   **Blocos de Código:** Sempre especifique a linguagem (ex: `python`, `bash`, `json`, `http`). Use `mermaid` para todos os diagramas.
*   **Diagramas:** Use Mermaid.js. Inclua `%%{init: {'theme': 'dark'}}%%` no topo.

### 3. Linguagem e Tom
*   **Tom:** Profissional, conciso e direto.
*   **Inglês Primeiro:** O inglês é a fonte da verdade para documentação técnica. Termos técnicos (ex: "Rate Limiting", "Middleware") devem permanecer em inglês tanto nas versões em EN quanto em PT-BR.
*   **Voz:** Prefira a voz ativa.

### 4. Referências Cruzadas
*   **Links Relativos:** Use apenas links relativos (ex: `[Ver Arquitetura](../1-tecnico/arquitetura.md)`). Nunca use URLs absolutas do GitHub.
