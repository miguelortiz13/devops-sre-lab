# Roadmap

Orden pensado para que cada proyecto se apoye en el anterior. Tiempos
estimados dedicando ~8–10 h por semana. Cada proyecto se cierra con un
README que muestre **evidencia** (capturas, GIFs, enlaces a runs de
Actions) — eso es lo que ve un reclutador.

```
P0 ─► P1 ─► P2 ─► P3 ─► P4 ─► P5
                    │      └──► P7
                    └──► P6         P8 (al final, opcional)
```

---

## Fase 1 — Fundamentos (semanas 1–5)

### P0 · `local-k8s-lab` — Entorno local reproducible (1 semana)
Objetivo: cualquiera clona el repo y con un comando tiene el sistema corriendo.
- Cluster local con **kind** (config multi-nodo en YAML).
- `Makefile` con `make up`, `make deploy`, `make down`, `make doctor` (verifica herramientas).
- Despliegue de Online Boutique con su Helm chart; acceso por port-forward.
- Script de instalación de herramientas (kubectl, helm, kind, k9s) con versiones fijadas.

**Terminado cuando:** `make up && make deploy` deja la tienda abierta en el navegador desde un clon limpio.

### P1 · `infra-azure-terraform` — Infraestructura como código (2–3 semanas)
- Estado remoto en Azure Storage con bloqueo; bootstrap separado.
- Módulos propios: `network` (VNet, subnets, NSG), `aks`, `acr`, `keyvault`, `monitoring`.
- Entornos `dev` y `prod` que reutilizan los módulos con variables distintas.
- Pipeline en GitHub Actions: `fmt` → `validate` → `tflint` → `checkov` → `plan` comentado en el PR → `apply` manual con aprobación.
- Autenticación **GitHub → Azure por OIDC** (federated credentials), sin secretos de larga vida.
- `infracost` en el PR y alerta de presupuesto (Azure Budget) por correo.

**Terminado cuando:** un PR muestra el plan y el costo estimado; al aprobar se crea el AKS; `terraform destroy` lo borra sin residuos.

### P2 · `online-boutique-ci` — CI de contenedores (1–2 semanas)
Fork de Online Boutique.
- Workflow que construye **solo los servicios modificados** (matriz por carpeta).
- Tests unitarios existentes + lint de Dockerfiles (hadolint).
- Escaneo de vulnerabilidades con **Trivy** (falla en CRITICAL), SBOM con **Syft**, firma con **cosign** (keyless).
- Push a ACR con tag = SHA corto + versión semántica en releases.
- Al final, abre un PR automático en `platform-gitops` actualizando el tag de imagen.

**Terminado cuando:** cambiar un servicio produce una imagen firmada en ACR y un PR en el repo GitOps.

---

## Fase 2 — Plataforma (semanas 6–10)

### P3 · `platform-gitops` — GitOps y entrega progresiva (2–3 semanas)
- **Argo CD** con patrón app-of-apps; todo el cluster declarado en Git.
- Kustomize con overlays `dev` / `prod`.
- Tráfico de entrada con **Gateway API** (Envoy Gateway) + **cert-manager** (Let's Encrypt).
- **External Secrets Operator** leyendo de Key Vault con Workload Identity.
- **Argo Rollouts**: canary del `frontend` con análisis automático sobre métricas (se conecta en P4).

**Terminado cuando:** borrar el namespace de la app y ver que Argo CD lo reconstruye solo; un despliegue canary se revierte automáticamente al inyectar errores.

### P4 · `observability-stack` — Observabilidad (2 semanas)
- **kube-prometheus-stack** (Prometheus, Alertmanager, Grafana), **Loki** para logs, **Tempo** para trazas.
- **OpenTelemetry Collector** recibiendo trazas/métricas de los servicios.
- Dashboards como código (JSON versionado / Grafana provisioning), método **RED** por servicio y **USE** para nodos.
- Alertas enviadas a Discord o Slack.

**Terminado cuando:** desde una alerta se llega al dashboard, de ahí a la traza lenta y de la traza a sus logs (correlación por trace_id).

---

## Fase 3 — Confiabilidad y seguridad (semanas 11–16)

### P5 · `sre-reliability-lab` — Prácticas SRE (3 semanas) ⭐ el más importante del portafolio
Usa **OpenTelemetry Demo** en AKS.
- Definir SLIs/SLOs (disponibilidad y latencia de checkout) con **Sloth** o **Pyrra**.
- Alertas multi-ventana por **burn rate** del error budget.
- Pruebas de carga con **k6** (baseline, estrés, soak) y reporte de capacidad.
- Experimentos de caos con **Chaos Mesh**: caída de pods, latencia de red, falla de nodo.
- Activar las fallas de flagd (p. ej. `paymentFailure`, `adServiceHighCpu`) como incidentes simulados.
- Por cada incidente: **runbook** + **postmortem blameless** (línea de tiempo, causa raíz, acciones).

**Terminado cuando:** existen ≥3 postmortems reales del laboratorio y un informe de error budget de un periodo.

### P6 · `k8s-security-policies` — Seguridad de la plataforma (2 semanas)
- **Kyverno**: verificar firma cosign de las imágenes, prohibir root, exigir requests/limits y etiquetas.
- **NetworkPolicies** default-deny por namespace y permisos mínimos entre servicios.
- **Falco** para detección en tiempo de ejecución; **kube-bench** (CIS) con reporte.
- RBAC mínimo y Workload Identity en lugar de secretos.

**Terminado cuando:** una imagen sin firmar es rechazada por el cluster y hay un reporte CIS antes/después.

### P7 · `dr-finops` — Recuperación y costos (1–2 semanas)
- **Velero** con backups a Blob Storage programados.
- **Simulacro de DR**: destruir el cluster, recrearlo con P1 + P3 + Velero, medir RTO y RPO reales.
- **HPA** / **KEDA** y cluster autoscaler probados con k6.
- **OpenCost** para costo por namespace; documento de optimizaciones aplicadas.

**Terminado cuando:** el informe del simulacro trae RTO/RPO medidos y el costo mensual estimado del entorno.

---

## Fase 4 — Portabilidad (opcional, semanas 17–19)

### P8 · `infra-aws-terraform` — Misma plataforma en AWS
- VPC, EKS, ECR con Terraform y OIDC GitHub → AWS.
- Reutilizar P3/P4 sin cambios de manifiestos (solo overlays).
- Tabla comparativa Azure vs AWS: servicios, costo, fricciones encontradas.

**Terminado cuando:** Online Boutique corre en EKS desplegado por el mismo repo GitOps.

---

## Disciplina de costos (aplica a todo)

- Desarrollar **primero en local (kind)**; la nube solo para lo que exige nube.
- Cluster AKS de 1–2 nodos pequeños (B-series / spot) y **`terraform destroy` al terminar cada sesión**.
- Budget con alerta desde el día 1. Usar una suscripción **personal** (Azure free/estudiante), nunca una de trabajo.
