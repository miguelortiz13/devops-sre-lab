#!/usr/bin/env python3
"""Sincroniza backlog/*.yaml con issues de GitHub.

Crea etiquetas, milestones, épicas y tareas, y enlaza cada tarea como
sub-issue de su épica. Es idempotente: identifica cada issue por su clave
(`P1-04 · ...`), así que se puede ejecutar las veces que haga falta.

Por defecto NO sobrescribe el cuerpo de issues existentes (para no borrar
checkboxes marcados en GitHub). Usa --update-bodies para forzarlo.

Uso:
  scripts/sync_backlog.py --dry-run
  scripts/sync_backlog.py
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = False


def gh_api(method, path, body=None, paginate=False):
    cmd = ["gh", "api", "-X", method, path, "-H", "X-GitHub-Api-Version: 2022-11-28"]
    if paginate:
        cmd += ["--paginate", "--jq", ".[]"]
    if body is not None:
        cmd += ["--input", "-"]
    res = subprocess.run(cmd, input=json.dumps(body) if body is not None else None,
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"{method} {path}: {res.stderr.strip() or res.stdout.strip()}")
    if paginate:
        return [json.loads(line) for line in res.stdout.splitlines() if line.strip()]
    return json.loads(res.stdout) if res.stdout.strip() else None


def write(method, path, body, desc):
    print(f"  {'[dry-run] ' if DRY else ''}{desc}")
    if DRY:
        return None
    out = gh_api(method, path, body)
    time.sleep(0.8)  # evita el rate limit secundario de creación de contenido
    return out


def section(title, items, checkbox=False):
    if not items:
        return ""
    prefix = "- [ ] " if checkbox else "- "
    return f"## {title}\n\n" + "\n".join(prefix + i for i in items) + "\n\n"


def epic_body(e):
    return (
        f"> **Épica {e['id']}** · Repositorio: `{e['repo']}` · {e['milestone']}\n\n"
        f"## Objetivo\n\n{e['objective'].strip()}\n\n"
        + section("Criterio de terminado", e.get("done_when", []), checkbox=True)
        + section("Conceptos que cubre", e.get("learn", []))
        + "## Tareas\n\nLas tareas aparecen como **sub-issues** de esta épica, en orden de clave "
        f"(`{e['id']}-01`, `{e['id']}-02`...). Trabájalas en ese orden.\n"
    )


def task_body(e, t):
    who = t.get("who", "Tú")
    body = f"> **Épica:** {e['id']} · {e['title']} · **Quién:** {who}"
    if t.get("estimate"):
        body += f" · **Estimado:** {t['estimate']}"
    body += "\n\n"
    body += f"## Por qué\n\n{t['why'].strip()}\n\n"
    body += section("Conceptos que vas a aprender", t.get("learn", []))
    body += section("Paso a paso", t.get("steps", []), checkbox=True)
    body += section("Criterios de aceptación", t.get("acceptance", []), checkbox=True)
    body += section("Qué se hizo", t.get("done", []))
    body += section("Recursos", t.get("resources", []))
    return body.rstrip() + "\n"


def main():
    global DRY
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="miguelortiz13/devops-sre-lab")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--update-bodies", action="store_true")
    args = ap.parse_args()
    DRY = args.dry_run
    repo = f"repos/{args.repo}"

    with open(os.path.join(ROOT, "backlog", "_config.yaml")) as f:
        config = yaml.safe_load(f)
    epics = []
    for path in sorted(glob.glob(os.path.join(ROOT, "backlog", "P*.yaml"))):
        with open(path) as f:
            epics.append(yaml.safe_load(f))

    print("Etiquetas")
    existing_labels = {l["name"] for l in gh_api("GET", f"{repo}/labels?per_page=100", paginate=True)}
    for label in config["labels"]:
        if label["name"] not in existing_labels:
            write("POST", f"{repo}/labels", label, f"crear etiqueta {label['name']}")

    print("Milestones")
    milestones = {m["title"]: m["number"] for m in
                  gh_api("GET", f"{repo}/milestones?state=all&per_page=100", paginate=True)}
    for m in config["milestones"]:
        if m["title"] not in milestones:
            out = write("POST", f"{repo}/milestones", m, f"crear milestone {m['title']}")
            milestones[m["title"]] = out["number"] if out else 0

    issues = {}
    for i in gh_api("GET", f"{repo}/issues?state=all&per_page=100", paginate=True):
        if "pull_request" not in i:
            issues[i["title"].split(" · ")[0]] = i

    def upsert(key, title, body, labels, milestone, state):
        payload = {"title": f"{key} · {title}", "labels": labels,
                   "milestone": milestones.get(milestone) or None}
        current = issues.get(key)
        if current is None:
            payload["body"] = body
            out = write("POST", f"{repo}/issues", payload, f"crear {key}")
            current = out or {"number": 0, "id": 0, "state": "open"}
            issues[key] = current
        else:
            if args.update_bodies:
                payload["body"] = body
            write("PATCH", f"{repo}/issues/{current['number']}", payload, f"actualizar {key} (#{current['number']})")
        if state == "closed" and current.get("state") != "closed" and current["number"]:
            write("PATCH", f"{repo}/issues/{current['number']}",
                  {"state": "closed", "state_reason": "completed"}, f"cerrar {key}")
        return current

    for e in epics:
        print(f"Épica {e['id']}")
        epic = upsert(e["id"], f"Épica: {e['title']}", epic_body(e),
                      ["tipo:épica", e["id"]] + e.get("labels", []), e["milestone"], e.get("state", "open"))
        linked = set()
        if epic["number"] and not DRY:
            linked = {s["id"] for s in gh_api("GET", f"{repo}/issues/{epic['number']}/sub_issues?per_page=100",
                                               paginate=True)}
        for t in e["tasks"]:
            labels = ["tipo:tarea", e["id"]] + t.get("labels", [])
            if t.get("who", "Tú").startswith("Tú"):
                labels.append("hazlo-tú")
            task = upsert(t["key"], t["title"], task_body(e, t), labels, e["milestone"], t.get("state", "open"))
            if task["id"] not in linked:
                write("POST", f"{repo}/issues/{epic['number']}/sub_issues", {"sub_issue_id": task["id"]},
                      f"enlazar {t['key']} → {e['id']}")
    print("Listo.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)
