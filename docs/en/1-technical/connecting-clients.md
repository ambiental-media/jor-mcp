<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Connecting to LLMs

To connect Claude Desktop (or other MCP-compliant agents) to the Ambiental Media Jor-MCP server, follow these simple, step-by-step instructions.

The connection process has been completely modernized and is completed entirely through the Claude interactive UI and your browser, ensuring a seamless experience.

---

## Step-by-Step Browser-Based Authorization Walkthrough

Follow these steps with the corresponding interface screens to create your secure connection:

### Step 1: Open Customization Menu
In Claude Desktop, click on the **"Customize"** button in the lower left corner to open the settings and options menu.

![Step 1 - Claude Customization Menu](/assets/how-to-connect-01.png)

### Step 2: Add Custom Connector
In the customization sidebar, look for the **"Connectors"** section. Click on **"Add"**, and then select **"Add Custom Connector"**.

![Step 2 - Add Custom Connector](/assets/how-to-connect-02.png)

### Step 3: Enter Connector Details
Type `jor-mcp` as the **Connector Name** and enter `https://jormcp.ambiental.media/mcp/sse` as the **Connector URL**. Once both fields are filled, click the **"Add"** button.

![Step 3 - Enter Name and URL](/assets/how-to-connect-03.png)

### Step 4: Start Connection
On the newly created connector page, click the **"Connect"** button to initiate the authorization flow.

![Step 4 - Start Connection](/assets/how-to-connect-04.png)

### Step 5: Google SSO Sign In
Claude will redirect you to the secure **Jor-MCP Consent Portal** login screen. Click the Google button and choose or enter your authorized corporate/registered Google account credentials to log in.

![Step 5 - Google Sign In](/assets/how-to-connect-05.png)

### Step 6: Grant Consent
Once logged in, review the requested access permissions on the consent card, then click **"Allow Access"** (or **"Permitir Acesso"**) to securely authorize Claude Desktop to query the Jor-MCP database.

![Step 6 - Authorize Portal](/assets/how-to-connect-06.png)

### Step 7: Connection Finalized
Your authorization is verified, and the connection is securely established. You can now close the browser window.

![Step 7 - Ready to Use](/assets/how-to-connect-07.png)

Return to Claude Desktop. You are ready to run searches, fetch articles, and analyze datasets dynamically!

---

## Persistent Authentication

Once the initial login is complete, your authentication is persistent. Claude Desktop automatically handles token renewal in the background using long-lived Refresh Tokens. You will not need to re-authenticate or manually re-configure your settings, even if you restart Claude Desktop daily.

---

## Tier Upgrades (Paid Plans)

If you have negotiated a paid plan (`Pro` tier) with Ambiental Media:
1. Your account will be upgraded by our administrators via the **Jor-MCP Admin Console**.
2. No action is required on your part; the next time you use Jor-MCP, your request limits will automatically increase to the `Pro` tier quota.
