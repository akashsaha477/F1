# Hosting ApexLens

What the server needs: a Linux VM with **2–4 GB of RAM or more** (pandas + LightGBM with the whole dataset in
memory), a persistent disk for `data/` (the dataset, models and the prediction game's files), outbound internet
(F1DB, the FastF1 export, Open-Meteo, the Anthropic API) and inbound TCP 80/443. Free 512 MB tiers (Render,
Railway, Fly) are too small; the frontend alone is static and would run anywhere, but it needs the API.

Everything runs from one `docker compose` file ([docker-compose.prod.yml](docker-compose.prod.yml)):
the API, the dashboard (nginx, proxies `/api`), and Caddy, which obtains and renews a Let's Encrypt certificate
for `APEXLENS_DOMAIN`. Without a domain of your own the site is served on `<public-ip>.sslip.io`, which resolves
to the IP automatically and still gets a real certificate. [setup.sh](setup.sh) does the whole installation on a
fresh Ubuntu VM, including a daily cron job (`scripts/game.py settle-due --fetch`) that fetches the results of
finished races and scores the prediction game, so nobody has to press the button.

## Free options for students (checked November 2026)

| | Oracle Cloud "Always Free" | Azure for Students |
|---|---|---|
| Cost | Free, no time limit | $100 credit per year (renew yearly with student status) |
| Machine | `VM.Standard.A1.Flex` (Arm): up to **2 OCPU / 12 GB RAM** since 15 Jun 2026 (was 4 / 24), 200 GB block storage | e.g. `B2s` (2 vCPU / 4 GB), roughly 3–6 months of credit |
| Sign-up needs | Email, phone, a **card** for identity verification (not charged on Always Free resources) | Academic email (`@iitk.ac.in`) — **no card** |
| Catch | Indian regions are often "Out of capacity" for A1; retry at different times or pick another home region at sign-up (the home region cannot be changed later) | Credit runs out; the always-free `B1s` (1 GB) is too small |

Claim the [GitHub Student Developer Pack](https://education.github.com/pack) as well: it is the way into
Azure for Students, and includes GitHub Pro and other perks (the DigitalOcean credit it used to carry was
withdrawn in July 2026 — check the live list). Hugging Face Spaces are not an option: Docker Spaces need a paid
plan and persistent storage is paid separately.

**No card at all?** Azure for Students is the hosted option. The other card-free route is your own machine
(a desktop that stays on) plus a [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/):
run `docker compose up` locally and `cloudflared` publishes it on an HTTPS URL with no ports opened — it
works from a hostel network — but the site is down whenever the machine sleeps.

### Oracle Cloud

1. Sign up at cloud.oracle.com (choose the home region carefully — `ap-mumbai-1` or `ap-hyderabad-1`; A1
   capacity varies). Stay on the Always Free tier when the trial ends.
2. **Compute → Instances → Create**: image *Canonical Ubuntu 24.04 (aarch64)*, shape *Ampere → VM.Standard.A1.Flex*,
   2 OCPU / 12 GB, boot volume 100 GB, upload or download the SSH key.
3. **Networking → Virtual cloud networks → (the VCN) → Security lists → Default**: add ingress rules for
   source `0.0.0.0/0`, TCP, destination ports `80` and `443`.
4. `ssh ubuntu@<public-ip>`.

### Azure for Students

1. Apply at azure.microsoft.com/free/students with the academic email (after the GitHub pack is approved, the
   Azure offer appears among its benefits once the 72-hour wait is over).
2. Either run [azure-vm.sh](azure-vm.sh) with the Azure CLI (`az login`, then `bash deploy/azure-vm.sh`), or in
   the portal **Create a resource → Virtual machine**: Ubuntu Server 24.04 LTS, size `B2s`, region Central
   India, SSH public key, inbound ports 22, 80, 443. Standard HDD disk 64 GB is enough.
3. `ssh azureuser@<public-ip>`.

Credit arithmetic: a `B2s` costs about $30 a month, a `B1ms` (2 GB) about $15; `az vm deallocate` stops the
meter when the VM is off. Set a budget alert in the portal (Cost Management → Budgets) at $80.

## Install

On the VM:

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/akashsaha477/F1 && cd F1
bash deploy/setup.sh --anthropic-key sk-ant-...      # omit the key to run without the AI entrant
```

The script installs Docker, opens ports 80/443 in the VM's firewall, writes `.env` (domain, a random admin
token, the key), builds the images, **runs the data pipeline** (ingesting 2022–2026 with telemetry, features,
training, evaluation and reports takes a few hours on 2 Arm cores — it is a one-off, and safe to re-run),
starts the services and installs the daily settle job. It prints the URL and the admin token at the end.

Options: `--domain predictions.example.com` if you own a domain (point an A record at the VM first),
`--skip-pipeline` if `data/` was copied from elsewhere, `--seasons 2024-2026` for a smaller dataset.

Day to day:

```bash
cd F1
docker compose --project-directory . -f deploy/docker-compose.prod.yml logs -f api   # logs
git pull && docker compose --project-directory . -f deploy/docker-compose.prod.yml up -d --build   # update
docker compose --project-directory . -f deploy/docker-compose.prod.yml exec api python scripts/game.py leaderboard
tail deploy/settle.log                                                                 # the daily job
```

After a race the daily job (03:30 UTC) pulls F1DB and scores every entrant as soon as the results are
published; the dashboard's *Fetch results & score* button does the same on demand and asks for the admin token
(`APEXLENS_GAME_ADMIN_TOKEN` in `.env`). Predicting never needs the token. To make the race week planner show
"what happened" for new races, rebuild the features now and then:
`docker compose ... exec api python scripts/build_features.py`.
