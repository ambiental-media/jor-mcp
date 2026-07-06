<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Prompting Best Practices

This document provides guidelines and example prompts to ensure AI assistants (like Claude) make optimal, efficient, and cost-effective use of the Jor-MCP server's tools.

---

## 1. Core Principles for AI Assistants

When a user asks a question about Ambiental Media's journalism, stories, or datasets:
1.  **Search First:** Always execute a unified query via `search_content` before attempting to answer from pre-trained knowledge or external web searches.
2.  **Read the Full Text:** Do not rely on short search excerpts or excerpts returned from previous lists if you need to summarize or quote. Fetch the full, cleaned plain text of any matching articles via `get_full_article` using the post's canonical URL or ID.
3.  **Provide Accurate Citations:** After reading and answering, always include the article's exact title, date of publication, and canonical link as the citation source.

---

## 2. Recommended Prompt Patterns (Good vs. Bad)

Below are examples of how to interact with the AI assistant to trigger the correct Jor-MCP tools:

### Scenario A: Researching a Topic or Beat

*   ❌ **Bad Prompt:** *"What has Ambiental Media published about the Pantanal wetland?"*
    *(While this works, it might leave the AI to summarize based only on the short excerpts returned by the search tool).*
*    can you fetch the full text of the most relevant 2 articles so we can do a comprehensive summary?"*

### Scenario B: Getting Latest Editorial Context

*   ❌ **Bad Prompt:** *"Tell me what's new on the website."*
    *(A bit too general, and might result in the AI asking for clarification).*
*   ✔️ **Good Prompt:** *"What are the latest 5 articles published by Ambiental Media? Use `list_latest_news` and give me a brief summary of each with their respective links."*

### Scenario C: Deep Diving into an Article

*   ❌ **Bad Prompt:** *"I saw article ID 1255 in the list. Summarize it for me based on the search excerpt."*
    *(Excerpts are only 300 characters long and miss critical context).*
*   ✔️ **Good Prompt:** *"Retrieve the full text of article ID 1255 using `get_full_article`. Once fetched, write a 3-paragraph summary detailing the main methodology and findings, and cite the canonical link."*

---

## 3. Example Client System Prompt / Instruction

If you are configuring a custom agent or system prompt in a platform like Claude Enterprise or a Custom GPT, you can append the following instructions to ensure the model behaves correctly:

```text
You have access to the Jor-MCP server, which exposes tools to query Ambiental Media's journalism database (WordPress and GitHub).

STRICT DIRECTIVES:
1. For any question regarding Ambiental Media's coverage, investigations, or datasets, you MUST call 'search_content' first.
2. Once search results are returned, never hallucinate or assume content. If you need to summarize or quote an article, you MUST call 'get_full_article' with the matching 'id' or 'link'.
3. Always cite your sources by appending the exact title, date, and canonical link of the articles used at the bottom of your response.
```
