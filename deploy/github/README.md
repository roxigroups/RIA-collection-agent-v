# GitHub Actions CI/CD & Auto-Deployment Setup

This repository includes an automated GitHub Actions pipeline in [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml).

---

## How It Works

1. **Pull Requests & Pushes**: Automatically runs unit tests on Python 3.11 (`tests/test_dates.py`).
2. **Push to `main`**: Automatically connects to your Google Cloud VM 1 over SSH, pulls the latest code, installs new requirements, applies database migrations, restarts `systemd` services, and verifies the `/health` endpoint.
3. **Frontend on Cloudflare**: Automatically triggered on git push via Cloudflare Pages' native Git integration.

---

## Step 1: Generate an SSH Key Pair for GitHub Actions

On your local machine or terminal, generate a dedicated deploy key:
```bash
ssh-keygen -t ed25519 -C "github-actions-ria" -f id_rsa_ria -N ""
```
This generates two files:
* `id_rsa_ria` (Private Key — goes into GitHub Secrets).
* `id_rsa_ria.pub` (Public Key — goes into your GCP VM).

---

## Step 2: Add Public Key to Your GCP VM

On your Google Cloud Console:
1. Go to **Compute Engine** > **VM instances** > Click on your **VM 1**.
2. Click **Edit** > Scroll to **SSH Keys** > Click **Add Item**.
3. Paste the contents of `id_rsa_ria.pub`. GCP will automatically assign it to the `ubuntu` user.
4. Save the VM configuration.

---

## Step 3: Add Secrets to Your GitHub Repository

In your GitHub repository, navigate to:
**Settings** > **Secrets and variables** > **Actions** > Click **New repository secret**.

Add the following 3 secrets:

| Secret Name | Value | Description |
| :--- | :--- | :--- |
| `GCP_VM1_HOST` | `34.xxx.xxx.xxx` | External IP address of your Google Cloud VM 1 |
| `GCP_VM1_USER` | `ubuntu` | The SSH user on the VM |
| `GCP_SSH_PRIVATE_KEY` | *(Contents of `id_rsa_ria`)* | The private SSH key generated in Step 1 |

---

## Step 4: Verification

Once the secrets are added:
1. Every time you push a change to `main`:
   ```bash
   git push origin main
   ```
2. Go to the **Actions** tab in GitHub.
3. You will see:
   * **Test Suite**: ✅ Passed.
   * **Deploy to Google Cloud VM 1**: ✅ Pulled code, updated dependencies, ran migrations, restarted services, and verified health check.
