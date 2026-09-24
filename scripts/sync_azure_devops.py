#!/usr/bin/env python3
"""Sincroniza backlog/*.yaml con Azure DevOps Boards (DevOps - SRE).

Crea Épicas (Epic) y Tareas (Issue) enlazadas jerárquicamente como parent/child.
Es idempotente: si el work item ya existe por título, no lo duplica.
Usa la autenticación de Azure CLI activa o la variable AZURE_DEVOPS_TOKEN.

Uso:
  scripts/sync_azure_devops.py --dry-run
  scripts/sync_azure_devops.py
"""

import argparse
import glob
import html
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import yaml

ORGANIZATION = "devops-sre-lab"
PROJECT = "DevOps - SRE"
API_VERSION = "7.0"
BASE_URL = f"https://dev.azure.com/{ORGANIZATION}/{urllib.parse.quote(PROJECT)}/_apis"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_token():
    token = os.environ.get("AZURE_DEVOPS_TOKEN")
    if token:
        return token
    res = subprocess.run(
        [
            "az",
            "account",
            "get-access-token",
            "--resource",
            "499b84ac-1321-427f-aa17-267ca6975798",
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"Error obteniendo token de Azure CLI: {res.stderr.strip()}"
        )
    return res.stdout.strip()


def api_request(method, url, data=None, token=None, content_type=None):
    if content_type is None:
        if "/workitems/" in url or "/workitems$" in url:
            content_type = "application/json-patch+json"
        else:
            content_type = "application/json"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
    }
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise RuntimeError(f"HTTP {e.code} en {method} {url}: {err_msg}")


def get_existing_work_items(token):
    wiql = {
        "query": (
            "Select [System.Id], [System.Title], [System.WorkItemType] "
            "From WorkItems Where [System.TeamProject] = @project"
        )
    }
    url = f"{BASE_URL}/wit/wiql?api-version={API_VERSION}"
    res = api_request("POST", url, data=wiql, token=token)
    items = res.get("workItems", [])
    if not items:
        return {}

    existing = {}
    chunk_size = 100
    ids = [str(item["id"]) for item in items]
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        details_url = f"{BASE_URL}/wit/workitems?ids={','.join(chunk)}&fields=System.Id,System.Title,System.WorkItemType&api-version={API_VERSION}"
        details = api_request("GET", details_url, token=token)
        for item in details.get("value", []):
            title = item["fields"]["System.Title"]
            existing[title] = {
                "id": item["id"],
                "type": item["fields"]["System.WorkItemType"],
            }
    return existing


def format_list(title, items, is_checklist=False):
    if not items:
        return ""
    res = f"<h3>{html.escape(title)}</h3><ul>"
    for item in items:
        clean = html.escape(str(item))
        if is_checklist:
            res += f"<li>[ ] {clean}</li>"
        else:
            res += f"<li>{clean}</li>"
    res += "</ul>"
    return res


def build_epic_description(epic):
    desc = ""
    if epic.get("objective"):
        desc += (
            f"<h3>Objetivo</h3><p>{html.escape(epic['objective'].strip())}</p>"
        )
    desc += format_list("Criterio de terminado", epic.get("done_when", []))
    desc += format_list("Lo que aprenderás", epic.get("learn", []))
    return desc


def build_task_description(task):
    desc = ""
    who = html.escape(task.get("who", "Tú"))
    est = html.escape(task.get("estimate", ""))
    desc += f"<p><strong>Responsable:</strong> {who}"
    if est:
        desc += f" | <strong>Estimación:</strong> {est}"
    desc += "</p>"

    if task.get("why"):
        desc += f"<h3>Por qué</h3><p>{html.escape(task['why'].strip())}</p>"

    desc += format_list("Conceptos clave", task.get("learn", []))
    desc += format_list("Paso a paso", task.get("steps", []), is_checklist=True)
    desc += format_list("Criterios de aceptación", task.get("acceptance", []))

    if task.get("resources"):
        desc += "<h3>Recursos y referencias</h3><ul>"
        for r in task["resources"]:
            esc_r = html.escape(r)
            desc += f'<li><a href="{esc_r}" target="_blank">{esc_r}</a></li>'
        desc += "</ul>"

    return desc


def create_work_item(item_type, title, description, state, tags, parent_id=None, token=None):
    patch = [
        {"op": "add", "path": "/fields/System.Title", "value": title},
        {"op": "add", "path": "/fields/System.Description", "value": description},
        {"op": "add", "path": "/fields/System.Tags", "value": tags},
    ]
    if parent_id:
        parent_url = f"https://dev.azure.com/{ORGANIZATION}/_apis/wit/workItems/{parent_id}"
        patch.append(
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": parent_url,
                    "attributes": {"comment": f"Parent Epic #{parent_id}"},
                },
            }
        )
    url = f"{BASE_URL}/wit/workitems/${item_type}?api-version={API_VERSION}"
    res = api_request("POST", url, data=patch, token=token)
    item_id = res["id"]

    if state and state != "To Do":
        state_patch = [{"op": "add", "path": "/fields/System.State", "value": state}]
        update_url = f"{BASE_URL}/wit/workitems/{item_id}?api-version={API_VERSION}"
        api_request("PATCH", update_url, data=state_patch, token=token)

    return item_id


def main():
    parser = argparse.ArgumentParser(
        description="Migrar backlog a Azure DevOps Boards"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra qué se crearía sin llamar a la API",
    )
    args = parser.parse_args()

    print(
        f"Conectando con Azure DevOps ({ORGANIZATION} / {PROJECT})...\n"
    )
    token = get_token() if not args.dry_run else "DRY_RUN_TOKEN"

    existing = {}
    if not args.dry_run:
        existing = get_existing_work_items(token)
        print(f"Work items existentes en el proyecto: {len(existing)}")
    else:
        print("[DRY-RUN] Modo simulación activado.")

    yaml_files = sorted(glob.glob(os.path.join(ROOT, "backlog", "P*.yaml")))
    if not yaml_files:
        print("No se encontraron archivos en backlog/P*.yaml")
        sys.exit(1)

    created_epics = 0
    created_issues = 0

    for path in yaml_files:
        with open(path, encoding="utf-8") as f:
            epic = yaml.safe_load(f)

        epic_id = epic["id"]
        epic_title = f"{epic_id} · Épica: {epic['title']}"
        epic_state = "Done" if epic_id == "P0" else "To Do"
        epic_tags = "; ".join(
            [epic_id, "tipo:épica"] + epic.get("labels", [])
        )

        epic_devops_id = None
        if epic_title in existing:
            epic_devops_id = existing[epic_title]["id"]
            print(
                f"\n✔ Épica existente [#{epic_devops_id}]: {epic_title}"
            )
        else:
            print(
                f"\n+ Creando Épica: {epic_title} (Estado: {epic_state})..."
            )
            if not args.dry_run:
                epic_devops_id = create_work_item(
                    "Epic",
                    epic_title,
                    build_epic_description(epic),
                    epic_state,
                    epic_tags,
                    token=token,
                )
                existing[epic_title] = {"id": epic_devops_id, "type": "Epic"}
                created_epics += 1
                print(f"  ➜ Épica creada con ID #{epic_devops_id}")
                time.sleep(0.3)
            else:
                epic_devops_id = 9999
                created_epics += 1

        # Crear tareas como Issues hijos
        tasks = epic.get("tasks", [])
        for task in tasks:
            task_key = task["key"]
            task_title = f"{task_key} · {task['title']}"
            task_state = "Done" if epic_id == "P0" else "To Do"

            tags_list = [epic_id, "tipo:tarea"] + task.get("labels", [])
            if task.get("who") == "Tú":
                tags_list.append("hazlo-tú")
            task_tags = "; ".join(tags_list)

            if task_title in existing:
                print(
                    f"  ✔ Tarea existente [#{existing[task_title]['id']}]: {task_title}"
                )
                continue

            print(
                f"  + Creando Tarea: {task_title} (Estado: {task_state})..."
            )
            if not args.dry_run:
                task_id = create_work_item(
                    "Issue",
                    task_title,
                    build_task_description(task),
                    task_state,
                    task_tags,
                    parent_id=epic_devops_id,
                    token=token,
                )
                existing[task_title] = {"id": task_id, "type": "Issue"}
                created_issues += 1
                time.sleep(0.3)
            else:
                created_issues += 1

    print("\n" + "=" * 50)
    if args.dry_run:
        print(
            f"[DRY-RUN] Simulación completa: se crearían {created_epics} Épicas y {created_issues} Tareas."
        )
    else:
        print(
            f"Sincronización finalizada con éxito: {created_epics} Épicas y {created_issues} Tareas procesadas."
        )


if __name__ == "__main__":
    main()
