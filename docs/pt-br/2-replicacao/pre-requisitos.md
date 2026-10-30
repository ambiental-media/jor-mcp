<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Pré-requisitos

## Projeto GCP com faturamento ativo

- [Criar projetos](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
- [Criar uma conta do Cloud Billing](https://docs.cloud.google.com/billing/docs/how-to/create-billing-account)
- [Ativar o faturamento de um projeto](https://docs.cloud.google.com/billing/docs/how-to/modify-project)
- [Verificar o status de faturamento](https://docs.cloud.google.com/billing/docs/how-to/verify-billing-enabled)

## Permissões

Papel `Owner` no projeto, ou `Editor` + `Project IAM Admin` (`roles/resourcemanager.projectIamAdmin`). Somente `Editor` não permite conceder papéis de IAM.

## Ferramentas

- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install), autenticado com `gcloud auth login`
- [Firebase CLI](https://firebase.google.com/docs/cli)
- [Docker](https://docs.docker.com/get-started/get-docker/)
- [`envsubst`](https://www.gnu.org/software/gettext/manual/html_node/envsubst-Invocation.html) (pacote `gettext`)
- `curl` e `openssl`

## Outros

- Fork do repositório [ambiental-media/jor-mcp](https://github.com/ambiental-media/jor-mcp), clonado localmente.
- Domínio ou subdomínio com acesso à configuração de DNS.
- GitHub Personal Access Token com leitura dos repositórios editoriais ([como criar](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)).
