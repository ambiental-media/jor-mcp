<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Bot Blocking (Optional)

> **Optional guidance.** Jor-MCP works whether or not the newsroom's public website blocks crawlers. Blocking AI crawlers is an editorial and business decision, not a deployment requirement. This page explains the moving parts and points to authoritative sources; it is not a how-to and not legal advice.

## 1. Two different access paths

| Path | Initiated by | Reaches |
| :--- | :--- | :--- |
| Public website crawling | Search engines, AI crawlers, scrapers | The HTML pages of the newsroom site |
| Authorized MCP access | `jor-mcp` on Cloud Run | The WordPress REST API (`/wp-json/...`) |

Crawler policy governs the public HTML surface. Jor-MCP reads content server-side through the REST API, so the two are independent in principle.

They are not independent in practice: a rule that blocks all non-browser user agents, all datacenter IP ranges, or all traffic outside a country will also block the MCP server. Any policy needs to keep the MCP outbound path reachable. See the Cloud Run egress references below.

## 2. Control layers

Each layer has a different enforcement model.

**`robots.txt`** — a voluntary signal defined by RFC 9309. Compliant crawlers honor it; others may ignore it. It is a declaration of preference, not access control. A CDN or WAF rule overrides it in both directions: an `Allow` in `robots.txt` does not bypass a firewall block.

**CDN and WAF bot controls** — enforced at the edge, before the request reaches WordPress. Vendors model AI traffic in categories such as training, search and agent, and each category can be allowed or blocked separately. Category definitions and defaults are vendor-specific and change over time.

**Application and plugin rules** — enforced by WordPress or a security plugin. This is the last resort: it is the easiest place to break legitimate integrations, including REST clients that look nothing like a browser.

## 3. Decision factors

There is no default recommendation here. The trade-offs differ per newsroom:

- **Purpose of access.** Training, AI search retrieval and agent access are different uses; a policy can separate them.
- **Licensing and business model.** Blocking public crawling does not prevent authorized, licensed access through Jor-MCP.
- **Search visibility.** Blocks aimed at AI crawlers can also affect search indexing if applied too broadly.
- **Operational dependencies.** Monitoring, feeds, SEO tooling and the MCP server itself all consume the site as non-browser clients.
- **Maintenance cost.** User-agent lists and IP ranges change; vendor-managed categories and published standards age better than hand-written rules.

## 4. References

| Topic | Sources |
| :--- | :--- |
| Robots exclusion standard | [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) · [Google: robots.txt introduction](https://developers.google.com/search/docs/crawling-indexing/robots/intro) · [Google: robots.txt specification](https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt) |
| AI crawler controls, vendor documentation | [OpenAI bots](https://platform.openai.com/docs/bots) · [Anthropic crawler article](https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler) · [Google crawlers and Google-Extended](https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers) · [Common Crawl CCBot](https://commoncrawl.org/ccbot) · [Apple Applebot-Extended](https://support.apple.com/en-us/119829) |
| Emerging preference signals | [IETF AI Preferences (aipref) working group](https://datatracker.ietf.org/wg/aipref/about/) |
| CDN and WAF bot controls | [Cloudflare bot solutions](https://developers.cloudflare.com/bots/) · [Cloudflare AI bot policies](https://developers.cloudflare.com/bots/additional-configurations/block-ai-bots/) · [Cloudflare managed robots.txt](https://developers.cloudflare.com/bots/additional-configurations/managed-robots-txt/) · [AWS WAF Bot Control](https://docs.aws.amazon.com/waf/latest/developerguide/aws-waf-bot-control.html) |
| Application layer | [WordPress REST API handbook](https://developer.wordpress.org/rest-api/) · The documentation of whichever security or bot-management plugin the site already uses |
| Keeping MCP reachable | [Cloud Run static outbound IP](https://cloud.google.com/run/docs/configuring/static-outbound-ip) · [Serverless VPC Access](https://cloud.google.com/vpc/docs/serverless-vpc-access) · [Cloud NAT overview](https://cloud.google.com/nat/docs/overview) |

Vendor documentation is authoritative for current user-agent names, categories and defaults. Those change; this page deliberately does not reproduce them.

## 5. Related documentation

- [WordPress integration](../1-technical/integrations/wordpress.md) — how Jor-MCP reads content through the REST API.
- [Deployment guide](deployment-guide.md) — environment variables and runtime configuration.
