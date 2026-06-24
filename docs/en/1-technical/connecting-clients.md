# Connecting to LLMs

To connect Claude Desktop (or other MCP-compliant agents) to the Ambiental Media Jor-MCP server, follow these simple, non-technical steps:

### 1. Configure Claude Desktop
1. Open Claude Desktop and go to **Settings** > **Developer** > **Edit Config**.
2. Add the Jor-MCP server to your configuration file (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "jor-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/inspector",
        "https://jormcp.ambiental.media/mcp/sse"
      ]
    }
  }
}
```
3. Save the file and restart Claude Desktop.

### 2. Interactive Authentication
The first time you interact with the Jor-MCP tools in Claude, you will be prompted to authenticate:
1. Claude will automatically trigger a browser popup window.
2. The browser will navigate to the **Jor-MCP Portal** login screen.
3. Log in with your Ambiental Media account credentials.
4. Once logged in, click **"Authorize"** to grant Claude access to your account.
5. The browser will redirect back to Claude, completing the connection securely.

### 3. Persistent Authentication
Once the initial login is complete, your authentication is persistent. Claude Desktop automatically handles token renewal in the background using long-lived Refresh Tokens. You will not need to re-authenticate or manually re-configure your settings, even if you restart Claude Desktop daily.

### 4. Tier Upgrades (Paid Plans)
If you have negotiated a paid plan (`Pro` tier) with Ambiental Media:
1. Your account will be upgraded by our administrators via the **Jor-MCP Admin Console**.
2. No action is required on your part; the next time you use Jor-MCP, your request limits will automatically increase to the `Pro` tier quota.