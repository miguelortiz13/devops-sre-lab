# ADR-0001 — Sistema base del laboratorio

- **Estado:** aceptado
- **Fecha:** 2026-09-12

## Contexto

Para practicar y demostrar DevOps/SRE se necesita un sistema realista
(varios servicios, distintos lenguajes, dependencias entre sí, tráfico)
sin tener que escribirlo desde cero.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| Online Boutique (Google) | 11 servicios polyglot, gRPC, Helm chart, generador de carga, liviano | Pocos datos persistentes (solo Redis) |
| OpenTelemetry Demo | Instrumentado, Kafka, Postgres, fallas por feature flags | ~6 GB de RAM, pesado para local |
| Example Voting App (Docker) | Muy simple | Demasiado pequeño para mostrar SRE |
| Sock Shop (Weaveworks) | Clásico | Archivado, imágenes desactualizadas |
| Proyectos propios existentes | Conocimiento del dominio | Mezcla el portafolio con otros objetivos |

## Decisión

- **Online Boutique** como sistema principal: cabe en el equipo local (7.4 GB en WSL) y es suficiente para IaC, CI/CD, GitOps, observabilidad, seguridad y DR.
- **OpenTelemetry Demo** solo para el laboratorio SRE (P5), ejecutado en la nube, por sus escenarios de falla ya incorporados.

## Consecuencias

- El repo P2 es un fork de Online Boutique; hay que sincronizar upstream ocasionalmente.
- P5 requiere un pool de nodos algo mayor mientras dure el laboratorio.
