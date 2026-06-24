# Spike Pré-POC: Fontes de Dados e Ferramentas

## 1. Objetivo
Analisar as "ferramentas" necessárias para o servidor Jor-MCP integrar várias fontes e formatos de conteúdo da Ambiental Media.

## 2. Contexto
A Ambiental Media publica jornalismo investigativo sobre meio ambiente, ciência e dados. O conteúdo é distribuído em várias plataformas: um site principal em WordPress, vários microsites baseados em WordPress e microsites Next.js hospedados em subdomínios personalizados. O servidor Jor-MCP atua como um orquestrador, fornecendo ferramentas de alto nível para um LLM acessar esse conteúdo de forma uniforme. A função principal é apenas leitura.

## 3. Fontes de Dados Identificadas
| Fonte de Dados | URL | Tecnologia |
| :--- | :--- | :--- |
| Site Principal | ambiental.media | WordPress |
| Aquazonia | aquazonia.ambiental.media | Next.js |
| Rio 60 | rio60.ambiental.media | Next.js |
| Cerrado | cerrado.ambiental.media | Next.js |
| Cortina de Fumaça | cortinadefumaca.ambiental.media | WordPress |
| Hiperdiversidade | hiperdiversidade.ambiental.media | WordPress |
| Floresta Silenciosa | florestasilenciosa.ambiental.media | WordPress |

### 3.1 Microsites Next.js
São aplicações Next.js 13+ seguindo um template padronizado, hospedadas em repositórios privados do GitHub sob a organização `ambiental-media`.

*   **Localização do Conteúdo:** O texto é centralizado em arquivos JSON (`messages/pt.json` e `messages/en.json`). Componentes React referenciam-nos via `useTranslations()`.
*   **Ativos (Assets):** Hospedados na pasta `public/`.

### 3.2 Sites WordPress
Quatro sites WordPress ativos foram confirmados, todos utilizando um banco de dados MariaDB e expondo uma API REST funcional.

*   **Site Principal (ambiental.media):** Usa Posts padrão, um Custom Post Type para "Projetos" e Páginas. Construído fortemente com Elementor.
*   **Microsites:** Estruturalmente mais simples, dependendo principalmente de Páginas estáticas e plugins de apresentação (Portfólios, Galerias). Eles não usam ativamente Posts padrão ou Custom Post Types.

**Testes da API REST:** Os endpoints `/wp-json/wp/v2/` para posts, projetos, categorias e páginas foram testados com sucesso, suportando consultas de busca e paginação.

## 4. Estratégia de Integração

O orquestrador Jor-MCP delegará o acesso com base na tecnologia de origem.

### 4.1 Integração Next.js (GitHub)
Duas opções foram avaliadas para acessar os repositórios privados do GitHub:
1.  **Via Servidor GitHub MCP:** Reutiliza infraestrutura existente, mas introduz uma dependência externa, maior latência e implantação complexa.
2.  **Via API REST Direta do GitHub:** Requisições HTTP diretas para buscar arquivos JSON. Oferece controle total, menor latência, implantação mais simples e evita a sobrecarga de comunicação entre processos.
*   **Decisão:** Prosseguir com a **API REST Direta do GitHub** para o MVP devido à sua simplicidade e menor latência. A autenticação usará um Token de Acesso Pessoal (PAT).

### 4.2 Integração WordPress
*   **Decisão:** Utilizar a **API REST do WordPress**. Ela atende totalmente às necessidades do MVP (busca de texto, custom post types, filtragem, paginação) e abstrai complexidades do banco de dados. Consultas SQL diretas são reservadas para necessidades futuras se consultas altamente complexas surgirem.

## 5. Ferramentas Propostas (Interface Abstrata)

As ferramentas são definidas por sua operação semântica, unificando as fontes de dados subjacentes.

*   **`search_content`**: Busca unificada através dos JSONs do Next.js e APIs REST do WordPress.
*   **`get_full_article`**: Recupera texto completo e limpo de um post/página do WordPress.
*   **`list_latest_news`**: Recupera publicações recentes para contexto temporal.
