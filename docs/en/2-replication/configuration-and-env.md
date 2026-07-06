<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Configuration Guide

*(Placeholder: Deep dive into `.env` customization. Explaining `WORDPRESS_API_URL`, `MCP_GITHUB_TOKEN`, and limits for a specific newsroom's needs).*

## Database & State (Firestore)
Rate limiting relies strictly on Google Cloud Firestore. It automatically uses Google Application Default Credentials (ADC) and does not require explicit connection strings (like a `REDIS_URL`). Ensure your deployment service account has the `roles/datastore.user` IAM role.
