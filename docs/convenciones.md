# Convenciones comunes

Reglas que aplican a todos los repos del laboratorio, para que el portafolio se lea
como el trabajo de un solo equipo.

## Repositorios

- Nombre en GitHub igual al de la carpeta (`infra-azure-terraform`, ...). Sin prefijos numéricos: el orden P0…P8 vive solo en la documentación.
- Públicos, con descripción y *topics* (`devops`, `sre`, `terraform`, `kubernetes`, `azure`, ...).
- Rama por defecto `main`, protegida: PR obligatorio y checks en verde para mergear.

## Commits y ramas

- [Conventional Commits](https://www.conventionalcommits.org/es/): `feat:`, `fix:`, `ci:`, `docs:`, `chore:`, `refactor:`.
- Ramas: `feat/<tema>`, `fix/<tema>`, `docs/<tema>`.
- Releases con tags semánticos (`v1.2.0`) y changelog generado.

## Estructura mínima de cada repo

```
README.md          # problema, arquitectura (Mermaid), cómo correrlo, evidencia, lecciones
docs/              # diagramas, decisiones, runbooks
.github/workflows/ # CI del propio repo
Makefile           # punto de entrada único: make help
```

## README de cada proyecto

1. **Qué problema resuelve** (2–3 líneas).
2. **Arquitectura** (diagrama Mermaid).
3. **Cómo ejecutarlo** (prerrequisitos + comandos).
4. **Evidencia**: capturas de Grafana/Argo CD, enlaces a runs de Actions.
5. **Decisiones y trade-offs**.
6. **Qué aprendí / qué haría distinto**.

## Seguridad

- Nunca credenciales en Git: OIDC para CI, Key Vault/External Secrets en el cluster.
- `pre-commit` con `gitleaks` en todos los repos.
- Versiones fijadas (providers de Terraform, charts de Helm, imágenes por digest cuando aplique).

## Decisiones

Toda decisión relevante va como ADR en `docs/adr/NNNN-titulo.md` del hub
(si afecta a varios repos) o del repo específico.
