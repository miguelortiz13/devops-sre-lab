# ADR-0002 — Nube principal: Azure, con AWS como segunda nube

- **Estado:** propuesto
- **Fecha:** 2026-09-12

## Contexto

El laboratorio necesita un proveedor cloud con Kubernetes gestionado. El
presupuesto es personal y limitado.

## Decisión propuesta

- **Azure (AKS)** como nube principal:
  - El plano de control de AKS en el tier *Free* no se cobra; solo se pagan los nodos. En EKS el plano de control se cobra por hora aunque no haya carga.
  - Ya existe experiencia previa (proyecto `cloud-mart-platform`, Azure CLI configurado).
- **AWS (EKS)** en P8 para demostrar portabilidad, que es lo que más piden las ofertas.

## Consecuencias

- Módulos Terraform con `azurerm`; P8 repite el patrón con `aws`.
- Hay que usar una suscripción **personal**, separada de cualquier suscripción laboral.
- Si se prefiere AWS como principal, se invierte el orden P1 ↔ P8 y este ADR pasa a *reemplazado*.
