# Integração Firebase e Firestore

*(Placeholder: Detalhes sobre a implementação OAuth 2.1, validação de JWT do Firebase Auth e transações atômicas do Firestore para limitação de taxa).*

## Decisão Arquitetural: Por que Estado Serverless?
Contamos com o Firestore em vez de um cache em memória ou uma instância Redis provisionada para manter a ausência de estado (statelessness) nos contêineres do Cloud Run. Isso permite escalonamento horizontal a zero, maximizando a eficiência de FinOps enquanto evita burlar o limite de taxa durante picos de tráfego.