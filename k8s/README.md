# Cloud Scout Service — Docker + Kubernetes

The TFTwatch scout (Phase 0) also runs as a **containerized HTTP service deployed to
Kubernetes**. This is the "cloud brain" half of the project — it uses only public Riot
API data (no screen reading), so unlike the desktop coach it's safe to run as a stateless
service and scale horizontally.

This directory is a small but complete example of running a **stateful web service** on
Kubernetes: an API tier, a database with durable storage, config/secret management, and
ingress routing.

![TFTwatch Scout API — live 200 response through the cluster](../docs/scout-api.png)

---

## Architecture

```
                    ┌─────────────────────────────────────────────────────┐
                    │                   Kubernetes                          │
  browser  ──HTTP──▶│  Ingress (scout.localhost)                            │
                    │      │                                                 │
                    │      ▼                                                 │
                    │  Service(scout)  ──▶  scout pod ×2  ─┐   (stateless)   │
                    │                                       │                │
                    │                       Service(postgres)                │
                    │                                       │                │
                    │                                       ▼                │
                    │                       postgres pod ──▶ PersistentVolume │  (stateful)
                    │                                          (1Gi, durable) │
                    └─────────────────────────────────────────────────────┘
       config: ConfigMap(scout-config)   secrets: riot-api, postgres-auth
```

**The core idea: stateless workers vs. stateful data.**
- **scout pods** are cattle — identical, disposable, 2 replicas (or 20). Kill any of them;
  a new one is created automatically and nothing is lost.
- **postgres pod** is a pet — one instance, and its data lives on a PersistentVolume that
  survives the pod being deleted entirely.

---

## Components (`k8s/`)

| File | Object | Why it exists |
|------|--------|---------------|
| `deployment.yaml` | Deployment + Service | 2 self-healing scout replicas behind one stable in-cluster address; liveness/readiness probes on `/healthz` |
| `postgres.yaml` | PVC + Deployment + Service | Postgres for the match cache; its data lives on the PersistentVolumeClaim so it survives restarts |
| `configmap.yaml` | ConfigMap | Non-secret config (Riot platform/region, DB host/user/db) decoupled from the Deployment |
| `ingress.yaml` | Ingress | Routes `scout.localhost` → the scout Service (a real URL, not `port-forward`) |
| Secrets (created by hand) | Secret ×2 | `riot-api` (Riot key) and `postgres-auth` (DB password) — never committed |

The application code for the service:
- `tftwatch/api.py` — FastAPI wrapper over the existing `scout_riot_id()` logic
- `tftwatch/cache.py` — pluggable cache: `DiskMatchCache` (desktop) / `PostgresMatchCache` (cloud)
- `Dockerfile` + `requirements-api.txt` — a slim image with only the service's dependencies

---

## Run it locally

**Prerequisites:** Docker Desktop with Kubernetes enabled, and the ingress-nginx controller:

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/cloud/deploy.yaml
```

**Build, configure, deploy:**

```bash
# 1. Build the image (unique tag per build — see "mutable tags" below)
docker build -t tftwatch-scout:v2 .

# 2. Create the two secrets by hand (they are not in any file)
kubectl create secret generic riot-api      --from-literal=RIOT_API_KEY="RGAPI-your-key"
kubectl create secret generic postgres-auth --from-literal=POSTGRES_PASSWORD="devpassword"

# 3. Apply everything
kubectl apply -f k8s/

# 4. Use it
#    http://scout.localhost/docs   (Chrome/Edge resolve *.localhost automatically)
#    curl "http://scout.localhost/scout?riot_id=Name%23TAG"
```

**Watch it self-heal:**

```bash
kubectl get pods
kubectl delete pod <a-scout-pod>     # a replacement is created instantly
```

---

## The caching result

Match data is immutable once a game ends, so it's cached forever. Measured on the same
player, twice:

| | Match rows in DB | Latency |
|---|---|---|
| First scout (cache **miss** → hits Riot) | 0 → 15 | ~5.9 s |
| Second scout (cache **hit** → from Postgres) | 15 | ~0.8 s |

~**7.5× faster**, and — the point of the PersistentVolume — the cache survives deleting
**every** pod, scout and Postgres alike. The data lives in the volume, not the containers.

---

## Design decisions (the interesting part)

**Split the "cloud brain" from the desktop client.**
The live coach reads your screen and must run locally (and stay within Riot's third-party
policy). The scout uses only public API data, so it belongs as a stateless service. Deciding
what runs where — and keeping the container free of the desktop-only deps (mss, OpenCV, etc.) —
is the main architectural call here.

**In-cluster Postgres vs. managed RDS.**
Postgres runs *in* the cluster here because it's the clearest way to demonstrate
PersistentVolumes. In production on AWS you'd more likely use **managed RDS** and let the
cluster stay stateless — trading operational simplicity for a bit of cost and less control.
This repo deliberately takes the self-managed path to make the storage mechanics visible.

**Immutable image tags.**
An early bug: rebuilding `tftwatch-scout:dev` and redeploying kept serving *stale* code,
because `imagePullPolicy: IfNotPresent` sees an existing `:dev` tag and never checks whether
it changed. The fix — and the rule — is a **unique tag per build** (`:v2`, a git SHA, etc.)
so every deploy is a distinct image and you always know exactly what's running.

**Secrets vs. ConfigMap.**
Sensitive values (Riot key, DB password) are Kubernetes Secrets, created out-of-band and
never committed. Everything else (region, DB host/user/name) is a ConfigMap. Same mechanism,
deliberately separated by sensitivity.

**Scaling ≠ speed here.**
More scout replicas add throughput and resilience, but they don't make an individual scout
faster — and they don't help at all against the real bottleneck, which is **Riot's API rate
limit** (shared across all pods). The cache, not more pods, is what actually removes that
constraint. Finding the real bottleneck beats reaching for the obvious lever.

**Why no CI/CD (yet).**
This is a local, single-node learning deployment. A pipeline that builds an image and pushes
it to a registry only for the same laptop to pull it back is ceremony, not value. CI/CD earns
its place once there's a real remote deploy target (e.g. EKS); until then it's intentionally
omitted.
