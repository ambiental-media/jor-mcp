<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Connecting to LLMs

To connect Claude Desktop (or other MCP-compliant agents) to the Ambiental Media Jor-MCP server, follow these simple, step-by-step instructions.

The connection process has been completely modernized and is now completed entirely through an interactive browser UI, ensuring a seamless experience for journalists and non-technical users.

---

## 1. Configure Claude Desktop

First, configure Claude Desktop to recognize the Jor-MCP server:

1. Open Claude Desktop.
2. Go to **Settings** > **Developer** > **Edit Config**.
3. Add the Jor-MCP server to your configuration file (`claude_desktop_config.json`):

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

4. Save the file and restart Claude Desktop.

---

## 2. Step-by-Step Browser-Based Authorization Walkthrough

The first time you interact with Jor-MCP tools in Claude, an interactive OAuth 2.1 authentication flow will trigger in your browser. Follow these steps:

### Step 1: Portal Redirection
Claude Desktop will automatically open a browser window redirecting you to the secure **Jor-MCP Consent Portal**.

![Step 1 - Accessing the Portal](/assets/how-to-connect-01.png)

### Step 2: Sign In with Google
Click the **"Sign in with Google"** button to authenticate your identity. Make sure to use your authorized corporate or registered email address.

![Step 2 - Google Login](/assets/how-to-connect-02.png)

### Step 3: Select Your Google Account
Select your registered Google account from the standard Google authentication window.

![Step 3 - Google Account Selection](/assets/how-to-connect-03.png)

### Step 4: Review Permissions Request
After signing in, the portal will display a clear consent card. This lists the exact permissions being requested (such as querying editorial databases) on behalf of the client (Claude Desktop).

![Step 4 - Reviewing Consent](/assets/how-to-connect-04.png)

### Step 5: Approve the Connection
Click the **"Authorize"** button to securely approve the connection.

![Step 5 - Granting Consent](/assets/how-to-connect-05.png)

### Step 6: Authorization Successful
The system will securely exchange authorization codes (using PKCE) and configure your session. A confirmation message will appear.

![Step 6 - Redirection Process](/assets/how-to-connect-06.png)

### Step 7: Ready to Use
You can now close the browser tab. The connection is fully established!

![Step 7 - Connection Finalized](/assets/how-to-connect-07.png)

Return to Claude Desktop. You can now run searches, fetch articles, and analyze data dynamically!

---

## 3. Persistent Authentication

Once the initial login is complete, your authentication is persistent. Claude Desktop automatically handles token renewal in the background using long-lived Refresh Tokens. You will not need to re-authenticate or manually re-configure your settings, even if you restart Claude Desktop daily.

---

## 4. Tier Upgrades (Paid Plans)

If you have negotiated a paid plan (`Pro` tier) with Ambiental Media:
1. Your account will be upgraded by our administrators via the **Jor-MCP Admin Console**.
2. No action is required on your part; the next time you use Jor-MCP, your request limits will automatically increase to the `Pro` tier quota.
