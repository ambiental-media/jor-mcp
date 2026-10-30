<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Prerequisites

## GCP project with billing enabled

- [Create projects](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
- [Create a Cloud Billing account](https://docs.cloud.google.com/billing/docs/how-to/create-billing-account)
- [Enable billing for a project](https://docs.cloud.google.com/billing/docs/how-to/modify-project)
- [Verify the billing status of your projects](https://docs.cloud.google.com/billing/docs/how-to/verify-billing-enabled)

## Permissions

`Owner` role on the project, or `Editor` + `Project IAM Admin` (`roles/resourcemanager.projectIamAdmin`). `Editor` alone cannot grant IAM roles.

## Tools

- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install), authenticated with `gcloud auth login`
- [Firebase CLI](https://firebase.google.com/docs/cli)
- [Docker](https://docs.docker.com/get-started/get-docker/)
- [`envsubst`](https://www.gnu.org/software/gettext/manual/html_node/envsubst-Invocation.html) (`gettext` package)
- `curl` and `openssl`

## Other

- A fork of [ambiental-media/jor-mcp](https://github.com/ambiental-media/jor-mcp), cloned locally.
- A domain or subdomain whose DNS you can configure.
- A GitHub Personal Access Token with read access to the editorial repositories ([how to create one](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)).
