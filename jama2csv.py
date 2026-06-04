import csv
import base64
import re
import html
import getpass
import os
import requests
import urllib3
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dotenv import load_dotenv


# Load configuration from .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[INFO] Loaded configuration from .env")
else:
    print(f"[WARN] No .env file found at {env_path}")

# TEMP TESTING ONLY:
# This disables SSL certificate warnings because we are currently using verify=False.
# Remove this once you switch to a trusted company CA certificate.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Load BASE_URL from .env (required)
BASE_URL = os.getenv("JAMA_BASE_URL")
if not BASE_URL:
    raise ValueError(
        "JAMA_BASE_URL is not set in .env file.\n"
        "Please add JAMA_BASE_URL to your .env file.\n"
        
    )

# Remove /rest/v1 suffix if present in .env value
BASE_URL = BASE_URL.rstrip('/').replace('/rest/v1', '')
REST_URL = f"{BASE_URL}/rest/v1"

print(f"[INFO] Using Jama base URL: {BASE_URL}")
print(f"[INFO] REST API URL: {REST_URL}")

# Export CSV to the same directory as this .py file.
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_CSV = SCRIPT_DIR / "jama_requirements_export.csv"

# These are populated at runtime.
JAMA_USERNAME = ""
JAMA_PASSWORD = ""
PROJECT_ID = None

VERIFICATION_METHOD_MAP = {
    422: "Test",
    420: "Inspection",
    419: "Demonstration",
    418: "Analysis",
}

def prompt_for_runtime_inputs() -> None:
    global JAMA_USERNAME, JAMA_PASSWORD, PROJECT_ID

    print("\nEnter Jama credentials.")
    JAMA_USERNAME = input("Jama username: ").strip()
    JAMA_PASSWORD = getpass.getpass("Jama password: ")

    if not JAMA_USERNAME:
        raise ValueError("Jama username cannot be blank.")

    if not JAMA_PASSWORD:
        raise ValueError("Jama password cannot be blank.")

    print("\nEnter Jama project information.")
    project_id_raw = input("Jama project API ID: ").strip()

    if not project_id_raw:
        raise ValueError("Jama project API ID cannot be blank.")

    try:
        PROJECT_ID = int(project_id_raw)
    except ValueError:
        raise ValueError(
            f"Jama project API ID must be a number. You entered: {project_id_raw}"
        )


def build_basic_auth_header(username: str, password: str) -> str:
    raw_value = f"{username}:{password}"
    encoded_value = base64.b64encode(raw_value.encode("utf-8")).decode("utf-8")
    return f"Basic {encoded_value}"


def build_jama_item_url(item_id: Any) -> str:
    if not item_id:
        return ""

    return f"{BASE_URL}/perspective.req#/items/{item_id}?projectId={PROJECT_ID}"


def build_excel_hyperlink(url: str, display_text: str) -> str:
    """
    Builds one Excel HYPERLINK formula for CSV.
    """
    if not url:
        return ""

    safe_url = str(url).replace('"', '""')
    safe_display_text = str(display_text or url).replace('"', '""')

    return f'=HYPERLINK("{safe_url}","{safe_display_text}")'


def build_excel_hyperlink_from_id(
    item_id: Any,
    item_lookup: Dict[Any, Dict[str, Any]]
) -> str:
    """
    Builds a single clickable Jama link for one item ID.
    """
    if not item_id:
        return ""

    related_item = item_lookup.get(item_id)

    if not related_item:
        return ""

    fields = related_item.get("fields", {})
    document_key = related_item.get("documentKey", fields.get("documentKey", ""))

    if not document_key:
        return ""

    url = build_jama_item_url(item_id)
    return build_excel_hyperlink(url, document_key)


def clean_jama_html(raw_value: Any) -> str:
    """
    Cleans Jama rich text HTML into readable plain text for CSV export.
    """
    if raw_value is None:
        return ""

    text = str(raw_value)

    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*p\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*div\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*li\s*>", "\n", text)

    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = "\n".join(line.strip() for line in text.splitlines())

    return text.strip()


def get_verification_method(fields: Dict[str, Any]) -> str:
    """
    Finds verification method fields such as:
        verification_method$86
        verification_method$112
        verification_method$<any number>

    Then maps Jama picklist option IDs to readable values.
    """
    raw_value = ""

    for field_name, field_value in fields.items():
        if field_name.startswith("verification_method$"):
            raw_value = field_value
            break

    if raw_value == "":
        raw_value = get_field(
            fields,
            "verification_method",
            "verificationMethod",
            "verification method",
            "Verification Method"
        )

    if isinstance(raw_value, list):
        if not raw_value:
            return ""

        raw_value = raw_value[0]

    try:
        method_id = int(raw_value)
        return VERIFICATION_METHOD_MAP.get(method_id, str(method_id))
    except (TypeError, ValueError):
        return clean_jama_html(raw_value)


def jama_get(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{REST_URL}/{endpoint.lstrip('/')}"

    headers = {
        "Authorization": build_basic_auth_header(JAMA_USERNAME, JAMA_PASSWORD),
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "Accept": "application/json",
        "x-jama-date-fields-with-time": "true",
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        verify=False
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        print("\nJama API request failed.")
        print(f"URL: {response.url}")
        print(f"Status code: {response.status_code}")
        print(f"Response text: {response.text}")
        raise error

    return response.json()


def get_paginated_data(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    max_results: int = 50
) -> List[Dict[str, Any]]:
    all_data = []
    start_at = 0
    params = dict(params or {})

    while True:
        params["startAt"] = start_at
        params["maxResults"] = max_results

        response_json = jama_get(endpoint, params=params)

        data = response_json.get("data", [])
        page_info = response_json.get("meta", {}).get("pageInfo", {})

        result_count = page_info.get("resultCount", len(data))
        total_results = page_info.get("totalResults", None)

        all_data.extend(data)

        if result_count == 0 or len(data) == 0:
            break

        start_at += result_count

        if total_results is not None and start_at >= total_results:
            break

        if result_count < max_results:
            break

    return all_data


def get_all_project_items(project_id: int, max_results: int = 50) -> List[Dict[str, Any]]:
    params = {
        "project": project_id,
    }

    items = get_paginated_data("/items", params=params, max_results=max_results)

    print(f"Fetched {len(items)} total project items.")

    return items


def get_all_project_relationships(project_id: int, max_results: int = 1000) -> List[Dict[str, Any]]:
    all_relationships = []
    last_id = 1

    while True:
        params = {
            "project": project_id,
            "lastId": last_id,
            "omitCount": "true",
            "maxResults": max_results,
        }

        response_json = jama_get("/relationships", params=params)

        relationships = response_json.get("data", [])

        if not relationships:
            break

        all_relationships.extend(relationships)

        print(
            f"Fetched {len(relationships)} relationships. "
            f"Total so far: {len(all_relationships)}"
        )

        last_id = relationships[-1].get("id", last_id)

        if len(relationships) < max_results:
            break

    print(f"Fetched {len(all_relationships)} total project relationships.")

    return all_relationships


def build_relationship_maps(
    relationships: List[Dict[str, Any]],
    valid_item_ids: Set[Any]
) -> tuple[Dict[Any, List[Any]], Dict[Any, List[Any]]]:
    downstream_map: Dict[Any, List[Any]] = {}
    upstream_map: Dict[Any, List[Any]] = {}

    for rel in relationships:
        from_item = rel.get("fromItem")
        to_item = rel.get("toItem")

        if from_item not in valid_item_ids or to_item not in valid_item_ids:
            continue

        downstream_map.setdefault(from_item, []).append(to_item)
        upstream_map.setdefault(to_item, []).append(from_item)

    return downstream_map, upstream_map


def get_field(fields: Dict[str, Any], *possible_names: str) -> Any:
    for name in possible_names:
        if name in fields:
            return fields.get(name)

    return ""


def build_export_rows_for_item(
    item: Dict[str, Any],
    item_lookup: Dict[Any, Dict[str, Any]],
    downstream_map: Dict[Any, List[Any]],
    upstream_map: Dict[Any, List[Any]]
) -> List[Dict[str, Any]]:
    """
    Builds one or more export rows for a single Jama item.

    If there are multiple upstream/downstream links, each gets its own row.
    The core item fields are repeated on each row.
    """
    item_id = item.get("id", "")
    fields = item.get("fields", {})

    global_id = item.get("globalId", fields.get("globalID", ""))
    global_id_link = build_excel_hyperlink(
        build_jama_item_url(item_id),
        global_id
    ) if global_id else ""
    id_link = build_excel_hyperlink_from_id(item_id, item_lookup)
    name = clean_jama_html(fields.get("name", ""))
    description = clean_jama_html(fields.get("description", ""))

    verification_method = get_verification_method(fields)

    downstream_ids = downstream_map.get(item_id, [])
    upstream_ids = upstream_map.get(item_id, [])

    row_count = max(len(downstream_ids), len(upstream_ids), 1)

    rows = []

    for index in range(row_count):
        downstream_id = downstream_ids[index] if index < len(downstream_ids) else ""
        upstream_id = upstream_ids[index] if index < len(upstream_ids) else ""

        downstream_link = build_excel_hyperlink_from_id(downstream_id, item_lookup)
        upstream_link = build_excel_hyperlink_from_id(upstream_id, item_lookup)

        rows.append({
            "Global ID": global_id_link,
            "ID": id_link,
            "Downstream Requirements": downstream_link,
            "Name": name,
            "Description": description,
            "Upstream Requirements": upstream_link,
            "Verification Method": verification_method,
        })

    return rows


def export_to_csv(
    items: List[Dict[str, Any]],
    item_lookup: Dict[Any, Dict[str, Any]],
    downstream_map: Dict[Any, List[Any]],
    upstream_map: Dict[Any, List[Any]],
    output_path: Path
) -> None:
    fieldnames = [
        "Global ID",
        "ID",
        "Downstream Requirements",
        "Name",
        "Description",
        "Upstream Requirements",
        "Verification Method",
    ]

    rows = []
    total_items = len(items)

    for index, item in enumerate(items, start=1):
        item_id = item.get("id", "")
        document_key = item.get("documentKey", item.get("fields", {}).get("documentKey", ""))

        print(f"[{index}/{total_items}] Processing {document_key} / item ID {item_id}")

        item_rows = build_export_rows_for_item(
            item=item,
            item_lookup=item_lookup,
            downstream_map=downstream_map,
            upstream_map=upstream_map
        )

        rows.extend(item_rows)

    if not rows:
        print("No items found. CSV was not created.")
        return

    with open(output_path, mode="w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nExport complete: {output_path}")
    print(f"Total CSV rows written: {len(rows)}")


def main():
    print("Jama Requirements Export")
    print(f"Base URL: {BASE_URL}")
    print(f"REST URL: {REST_URL}")
    print(f"Project ID: {PROJECT_ID}")
    print(f"Output CSV: {OUTPUT_CSV}")

    prompt_for_runtime_inputs()

    print("\nFetching project items...")
    items = get_all_project_items(PROJECT_ID, max_results=50)

    item_lookup = {
        item.get("id"): item
        for item in items
        if item.get("id") is not None
    }

    valid_item_ids = set(item_lookup.keys())

    print("\nFetching project relationships...")
    relationships = get_all_project_relationships(PROJECT_ID, max_results=1000)

    print("\nBuilding upstream/downstream relationship maps...")
    downstream_map, upstream_map = build_relationship_maps(
        relationships=relationships,
        valid_item_ids=valid_item_ids
    )

    print("\nExporting CSV...")
    export_to_csv(
        items=items,
        item_lookup=item_lookup,
        downstream_map=downstream_map,
        upstream_map=upstream_map,
        output_path=OUTPUT_CSV
    )

    print("\nDone.")


if __name__ == "__main__":
    main()