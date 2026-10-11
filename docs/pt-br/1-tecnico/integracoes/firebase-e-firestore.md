<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Integração Firebase e Firestore

## Decisão Arquitetural: Por que Estado Serverless?
Contamos com o Firestore em vez de um cache em memória ou uma instância Redis provisionada para manter a ausência de estado (statelessness) nos contêineres do Cloud Run. Isso permite escalonamento horizontal a zero, maximizando a eficiência de FinOps enquanto evita burlar o limite de taxa durante picos de tráfego.

## Funções IAM de Execução para o Firebase Admin SDK
O servidor faz mais do que validar ID tokens. O `src/api/oauth.py` também emite tokens customizados, busca usuários e revoga refresh tokens, e cada uma dessas chamadas tem seu próprio requisito de IAM na conta de serviço de execução do Cloud Run:

| Operação | Chamada | Função necessária |
| :--- | :--- | :--- |
| Validar um ID token | `auth.verify_id_token` | Nenhuma — os certificados públicos de assinatura são obtidos via HTTPS. |
| Emitir um token customizado | `auth.create_custom_token` | `roles/iam.serviceAccountTokenCreator`, vinculada na própria conta de execução: no Cloud Run o Admin SDK assina pela API IAM `signBlob`. |
| Buscar um usuário | `auth.get_user` | `roles/firebaseauth.admin` |
| Revogar refresh tokens | `auth.revoke_refresh_tokens` | `roles/firebaseauth.admin` |

Veja o [guia de implantação, seção 2](../../2-replicacao/guia-de-implantacao.md) para a lista completa de funções de execução.
