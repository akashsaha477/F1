#!/usr/bin/env bash
# Creates the Azure VM for ApexLens with the Azure CLI (Azure for Students: no card needed).
#   az login                                  # once; pick the "Azure for Students" subscription if asked
#   bash deploy/azure-vm.sh [size] [region]   # default Standard_B2s (2 vCPU / 4 GB) in centralindia
# Then: ssh azureuser@<ip> and follow deploy/README.md ("Install"). Delete everything with:
#   az group delete --name apexlens --yes
set -euo pipefail
SIZE="${1:-Standard_B2s}"
REGION="${2:-centralindia}"
GROUP="apexlens"
NAME="apexlens"
# your SSH public key: APEXLENS_SSH_KEY, else ~/.ssh/id_ed25519.pub, else ~/.ssh/id_rsa.pub (generated if missing)
KEY="${APEXLENS_SSH_KEY:-}"
[ -n "$KEY" ] || for k in ~/.ssh/id_ed25519.pub ~/.ssh/id_rsa.pub; do [ -f "$k" ] && KEY="$k" && break; done
if [ -n "$KEY" ]; then KEYARG=(--ssh-key-values "$KEY"); else KEYARG=(--generate-ssh-keys); fi

az group create --name "$GROUP" --location "$REGION" --output none
# Standard HDD (cheapest), Ubuntu 24.04 LTS
az vm create --resource-group "$GROUP" --name "$NAME" --image Ubuntu2404 --size "$SIZE" \
  --admin-username azureuser "${KEYARG[@]}" --public-ip-sku Standard \
  --storage-sku Standard_LRS --os-disk-size-gb 64 --output table
az vm open-port --resource-group "$GROUP" --name "$NAME" --port 80,443 --priority 1001 --output none
IP="$(az vm show --resource-group "$GROUP" --name "$NAME" --show-details --query publicIps -o tsv)"
echo
echo "VM ready: ssh azureuser@${IP}"
echo "If the size is not available in ${REGION} for a student subscription, try: bash deploy/azure-vm.sh Standard_B2s southindia"
echo "Stop paying while it is off:  az vm deallocate -g ${GROUP} -n ${NAME}   (start again: az vm start ...)"
