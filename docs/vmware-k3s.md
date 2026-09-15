# VMware Workstation lab

## 1. Prepare the VM

Create an Ubuntu Server Linux VM with 4 vCPU, 12 GB RAM if available, and a 40 GB disk. Use NAT for outbound downloads or a host-only interface plus NAT. Avoid bridged exposure unless you explicitly want other LAN machines to reach the VM. Install Docker Engine/Compose and Python 3.12 using their official platform instructions. Keep the repository and Docker volumes on the VM's Linux disk, not a Windows shared-folder mount.

Copy or clone this project into the VM and first run the Compose quick start from the README. Take a VM snapshot after the working Compose baseline. This gives you an easy learning checkpoint before Kubernetes.

To view the VM's loopback-only Compose UI from your Windows host, run an SSH tunnel:

```sh
ssh -L 8080:127.0.0.1:8080 -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 your-user@VM_IP
```

Then use localhost on Windows. Do not change Compose port bindings to `0.0.0.0` just to reach them from the host.

## 2. Install a single-node K3s lab

The [official K3s quick start](https://docs.k3s.io/quick-start) documents its installer and kubeconfig. Download the installer into the VM, inspect it, then run it:

```sh
curl -sfL https://get.k3s.io -o /tmp/install-k3s.sh
less /tmp/install-k3s.sh
sudo sh /tmp/install-k3s.sh
sudo k3s kubectl get nodes
mkdir -p "$PWD/.local-kube"
sudo cp /etc/rancher/k3s/k3s.yaml "$PWD/.local-kube/config"
sudo chown "$(id -u):$(id -g)" "$PWD/.local-kube/config"
chmod 600 "$PWD/.local-kube/config"
export KUBECONFIG="$PWD/.local-kube/config"
```

`.local-kube/` is gitignored. This guide targets one node with K3s's local storage provisioner. Multi-node scheduling, HA storage and backups are later exercises. Do not increase the API replica count.

## 3. Build and load images locally

Run these on the VM where K3s runs; no image registry or paid account is needed:

```sh
docker compose build api web
docker save paperlab-api:local paperlab-web:local -o /tmp/paperlab-images.tar
sudo k3s ctr images import /tmp/paperlab-images.tar
kubectl create namespace paperlab --dry-run=client -o yaml | kubectl apply -f -
python scripts/k8s_secret.py | kubectl apply -f -
kubectl apply -k infrastructure/k8s
kubectl -n paperlab rollout status deployment/api --timeout=300s
kubectl -n paperlab rollout status deployment/web --timeout=300s
kubectl -n paperlab exec deployment/ollama -- ollama pull qwen2.5:1.5b
```

The API may restart while PostgreSQL initializes on the first run; inspect logs if readiness does not settle. `Recreate` prevents competing engine replicas during updates. Services are internal ClusterIP; there is no Ingress, LoadBalancer or NodePort.

```sh
kubectl -n paperlab port-forward --address 127.0.0.1 service/web 8080:8080
```

Keep the port forward running, then use the SSH tunnel from step 1 to reach it on Windows. Stop the Compose web service first if it already uses port 8080.

## 4. Add Prometheus, Grafana and pod metrics

Install Helm 3 using its official distribution. This optional monitoring stack needs additional RAM. The [official kube-prometheus-stack chart](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack) includes kube-state-metrics, node exporter and Grafana. This part downloads the current chart; record the chart version in your lab notes and pin it for later reproducibility.

Create the local Grafana Secret without displaying or committing its password:

```sh
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
python scripts/monitoring_secret.py | kubectl apply -f -
helm upgrade --install monitoring oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack \
  --namespace monitoring -f infrastructure/k8s/monitoring-values.yaml
kubectl apply -f infrastructure/k8s/service-monitor.yaml
kubectl apply -f infrastructure/k8s/dashboard-configmap.yaml
kubectl -n monitoring port-forward --address 127.0.0.1 service/monitoring-grafana 3000:80
```

The values disable separate scheduler/controller-manager/etcd scrapes that are not exposed the same way on a default K3s node. App metrics are selected through the ServiceMonitor. The dashboard's datasource UID is `prometheus`, matching the chart configuration supplied here. Monitoring storage defaults are ephemeral for this lab; add PVCs if you want retained metrics across pod recreation.

## 5. Import private CSVs on K3s

For small catalog files, mount a ConfigMap; do not put private data into source control:

```sh
kubectl -n paperlab create configmap paperlab-imports --from-file=ksa.csv=data/imports/ksa.csv \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n paperlab patch deployment api --type strategic --patch-file infrastructure/k8s/imports-patch.yaml
```

For a replay CSV under the ConfigMap size limit, include it as another `--from-file` entry and set `REPLAY_FILE=data/imports/your-file.csv` on the deployment. Larger datasets require a PVC. The included patch mounts the ConfigMap read-only at `/app/data/imports`.

For live data, use `kubectl -n paperlab set env deployment/api DATA_MODE=live` after setting the Alpaca keys in `.env` and regenerating the application Secret. Reapply/restart after Secret changes; environment variables in existing pods do not update automatically. The next application of the base manifest restores `DATA_MODE=replay`, so record intentional configuration changes in a private overlay.

## 6. Practice operations

```sh
kubectl -n paperlab get pods,pvc,svc
kubectl -n paperlab logs deployment/api --tail=100
kubectl -n paperlab describe pod POD_NAME
kubectl -n paperlab rollout restart deployment/api
```

Exercises: stop Redis and observe degraded cache health; restart the API and inspect ledger persistence; block provider egress and observe stale-price order rejection; pause replay and inspect quote age; enable the kill switch during automatic paper trading. Take snapshots and restore deliberately. Do not delete PVCs when testing ordinary restarts.
