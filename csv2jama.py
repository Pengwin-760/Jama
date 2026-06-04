import os
import re
import csv
import json
import time
import sys
import argparse
import requests
import pandas as pd
from typing import Dict, Optional, Any
from pathlib import Path
from dotenv import load_dotenv


# ============================================================
# VERIFICATION METHOD MAPPING
# ============================================================
# Jama picklist option IDs for verification methods (from jama2csv.py).
VERIFICATION_METHOD_MAP = {
    422: "Test",
    420: "Inspection",
    419: "Demonstration",
    418: "Analysis",
}

# Reverse mapping for import: display value -> picklist option ID.
VERIFICATION_METHOD_IMPORT_MAP = {
    "Test": 422,
    "Inspection": 420,
    "Demonstration": 419,
    "Analysis": 418,
}

# Aliases for Excel input: T/I/D/A and case-insensitive full words.
VERIFICATION_METHOD_ALIASES = {
    "T": "Test",
    "I": "Inspection",
    "D": "Demonstration",
    "A": "Analysis",
    "TEST": "Test",
    "INSPECTION": "Inspection",
    "DEMONSTRATION": "Demonstration",
    "DEMO": "Demonstration",
    "ANALYSIS": "Analysis",
}

# Pattern for matching verification method field keys with item-type-specific suffixes.
# Examples: verification_method$86, verification_method$112, verification_method$97
VERIFICATION_FIELD_PATTERN = re.compile(r"^verification_method\$\d+$", re.IGNORECASE)


def is_verification_method_field_key(key: str) -> bool:
    """
    Check if a field key matches the verification method pattern.

    Args:
        key: Field key to check

    Returns:
        True if key matches pattern like verification_method$112

    Examples:
        is_verification_method_field_key("verification_method$112") → True
        is_verification_method_field_key("verification_method$86") → True
        is_verification_method_field_key("verification_method") → False
        is_verification_method_field_key("name") → False
    """
    if not key:
        return False
    return bool(VERIFICATION_FIELD_PATTERN.match(str(key).strip()))


def collect_verification_method_field_keys_from_cached_items(item_type_id: Optional[int] = None) -> set:
    """
    Collect verification method field keys from cached Jama items.

    Searches cached items for fields matching "verification_method$<number>",
    using the same approach as jama2csv.py.

    Args:
        item_type_id: Optional filter for specific item type

    Returns:
        Set of field keys matching verification_method$<number>

    Examples:
        collect_verification_method_field_keys_from_cached_items(112)
        → {"verification_method$243"}

        collect_verification_method_field_keys_from_cached_items()
        → {"verification_method$112", "verification_method$243"}
    """
    keys = set()
    global _item_metadata_by_id

    for item in _item_metadata_by_id.values():
        if item_type_id is not None and item.get("itemType") != item_type_id:
            continue

        fields = item.get("fields", {})
        for field_name in fields.keys():
            if is_verification_method_field_key(field_name):
                keys.add(field_name)

    return keys


def resolve_verification_method_field_key(
    item_type_name: str,
    item_type_id: int,
    parent_item_id: Optional[int] = None,
    row: Optional[pd.Series] = None
) -> tuple[Optional[str], str]:
    """
    Resolve verification method field key using jama2csv.py approach.

    Resolution strategy:
    A. Use exact field key from .env (e.g., verification_method$243)
    B. Search cached items dynamically

    Dynamic search priority:
    1. Items with same itemType
    2. Project-wide if only one candidate exists (with warning)
    3. Fail if multiple candidates and no type-specific match

    Args:
        item_type_name: Item type name (e.g., "Software Requirement")
        item_type_id: Item type ID (e.g., 112)
        parent_item_id: Reserved for future use
        row: Reserved for future use

    Returns:
        Tuple of (field_key, resolution_source):
        - "env_explicit": from .env with exact key
        - "type_specific": from cached items of same type
        - "project_wide": from cached items project-wide (with warning)
        - None if cannot resolve

    Examples:
        resolve_verification_method_field_key("Software Requirement", 112)
        → ("verification_method$243", "type_specific")
    """
    configured_field = FIELD_MAP.get("verification_method")

    # Priority A: Exact field key from .env
    if configured_field and is_verification_method_field_key(configured_field):
        return (configured_field, "env_explicit")

    # Priority B & C: Dynamic search of cached items
    global _item_metadata_by_id

    if not _item_metadata_by_id:
        print("[INFO] Building project item cache for verification field discovery...")
        try:
            build_folder_document_key_cache()
        except Exception as e:
            print(f"[WARN] Could not build project cache: {e}")

    if not _item_metadata_by_id:
        # Cache still empty - cannot do dynamic search.
        if configured_field:
            return (f"{configured_field}${item_type_id}", "env_base_fallback")
        return (None, "no_cache")

    # Step 1: Search items of the same type
    type_specific_keys = collect_verification_method_field_keys_from_cached_items(item_type_id)

    if len(type_specific_keys) == 1:
        return (next(iter(type_specific_keys)), "type_specific")
    elif len(type_specific_keys) > 1:
        return (None, "multiple_type_specific")

    # Step 2: No type-specific fields - search whole project
    all_keys = collect_verification_method_field_keys_from_cached_items()

    if len(all_keys) == 1:
        # Use project-wide field with warning (target Set may be empty).
        return (next(iter(all_keys)), "project_wide")
    elif len(all_keys) > 1:
        # Multiple project-wide fields, no type-specific match - cannot determine.
        return (None, "multiple_project_wide")

    # No verification method fields found in cache.
    if configured_field:
        return (f"{configured_field}${item_type_id}", "env_base_fallback")

    return (None, "not_found")


def normalize_verification_method(value: str) -> Optional[str]:
    """
    Normalize verification method from Excel to canonical form.

    Supports letter aliases (T, I, D, A) and case-insensitive full words.

    Args:
        value: Excel value (e.g., "T", "Test", "test", " Test ")

    Returns:
        Canonical English value (e.g., "Test") or None if not recognized

    Examples:
        normalize_verification_method("T") → "Test"
        normalize_verification_method("test") → "Test"
        normalize_verification_method("I") → "Inspection"
        normalize_verification_method("D") → "Demonstration"
        normalize_verification_method("A") → "Analysis"
    """
    if not value or not isinstance(value, str):
        return None

    normalized = value.strip().upper()

    if not normalized:
        return None

    if normalized in VERIFICATION_METHOD_ALIASES:
        return VERIFICATION_METHOD_ALIASES[normalized]

    for canonical in VERIFICATION_METHOD_IMPORT_MAP.keys():
        if normalized == canonical.upper():
            return canonical

    return None


def get_verification_method_picklist_id(value: str) -> Optional[int]:
    """
    Convert canonical English verification method to Jama picklist option ID.

    Args:
        value: Canonical English value (e.g., "Test")

    Returns:
        Jama picklist option ID or None if not found

    Examples:
        get_verification_method_picklist_id("Test") → 422
        get_verification_method_picklist_id("Inspection") → 420
        get_verification_method_picklist_id("Demonstration") → 419
        get_verification_method_picklist_id("Analysis") → 418
    """
    if not value:
        return None

    return VERIFICATION_METHOD_IMPORT_MAP.get(value)


def format_verification_method_value(picklist_id: int) -> list:
    """
    Format verification method for Jama API payload.

    Verification Method uses a list of picklist option IDs, e.g. [422].

    Args:
        picklist_id: Picklist option ID (e.g., 422)

    Returns:
        Array containing the picklist ID

    Examples:
        format_verification_method_value(422) → [422]
        format_verification_method_value(420) → [420]
    """
    return [int(picklist_id)]


# ============================================================
# CONFIGURATION LOADING
# ============================================================

def load_configuration():
    """
    Load configuration from .env file and validate required settings.
    """
    env_path = Path(__file__).parent / ".env"
    env_file_exists = env_path.exists()

    if env_file_exists:
        load_dotenv(env_path)
        print(f"[INFO] Loaded configuration from .env")
    else:
        print(f"[WARN] No .env file found at {env_path}")
        print(f"[WARN] Copy .env.example to .env and configure it before running.")

    # Warn about legacy jama.config file
    config_path = Path(__file__).parent / "jama.config"
    if config_path.exists():
        print(f"[WARN] jama.config detected. This file appears to be a legacy/placeholder credential file.")
        print(f"[WARN] The importer now uses .env instead. Do not rely on Base64 as secure storage.")

    config = {}

    config["JAMA_BASE_URL"] = os.getenv("JAMA_BASE_URL")
    if not config["JAMA_BASE_URL"]:
        print("[ERROR] Missing required configuration: JAMA_BASE_URL")
        print("[ERROR] Set JAMA_BASE_URL in your .env file")
        sys.exit(1)

    project_id_str = os.getenv("JAMA_PROJECT_ID", "").strip()
    if not project_id_str:
        print("[ERROR] Missing required configuration: JAMA_PROJECT_ID")
        print("[ERROR] Set JAMA_PROJECT_ID in your .env file")
        sys.exit(1)

    try:
        config["JAMA_PROJECT_ID"] = int(project_id_str)
    except ValueError:
        print(f"[ERROR] JAMA_PROJECT_ID must be an integer, got: {project_id_str}")
        sys.exit(1)

    # Required: Root Parent Item ID
    root_parent_str = os.getenv("ROOT_PARENT_ITEM_ID")
    if not root_parent_str:
        print("[ERROR] Missing required configuration: ROOT_PARENT_ITEM_ID")
        print("[ERROR] Set ROOT_PARENT_ITEM_ID in your .env file")
        sys.exit(1)

    try:
        config["ROOT_PARENT_ITEM_ID"] = int(root_parent_str)
    except ValueError:
        print(f"[ERROR] ROOT_PARENT_ITEM_ID must be an integer, got: {root_parent_str}")
        sys.exit(1)

    config["EXCEL_FILE"] = os.getenv("INPUT_FILE", "requirements_import.xlsx")

    # Subsystem is modeled as a Set item type in this project.
    # It intentionally maps to JAMA_ITEM_TYPE_SET.
    try:
        config["ITEM_TYPE_IDS"] = {
            "Set": int(os.getenv("JAMA_ITEM_TYPE_SET", "31")),
            "Folder": int(os.getenv("JAMA_ITEM_TYPE_FOLDER", "32")),
            "Text": int(os.getenv("JAMA_ITEM_TYPE_TEXT", "33")),
            "Text Document": int(os.getenv("JAMA_ITEM_TYPE_TEXT", "33")),  # Alias for Text
            "Segment": int(os.getenv("JAMA_ITEM_TYPE_SEGMENT", "243")),
            "Subsystem": int(os.getenv("JAMA_ITEM_TYPE_SET", "31")),  # Subsystem uses Set item type
            "Stakeholder Requirement": int(os.getenv("JAMA_ITEM_TYPE_STAKEHOLDER_REQUIREMENT", "97")),
            "Subsystem Requirement": int(os.getenv("JAMA_ITEM_TYPE_SUBSYSTEM_REQUIREMENT", "87")),
            "Software Requirement": int(os.getenv("JAMA_ITEM_TYPE_SOFTWARE_REQUIREMENT", "112")),
        }
    except ValueError as e:
        print(f"[ERROR] Item type IDs must be integers: {e}")
        sys.exit(1)

    # Legacy "System Requirement" mapping
    default_req_type = os.getenv("DEFAULT_REQUIREMENT_ITEM_TYPE_ID", "")
    if default_req_type:
        try:
            config["ITEM_TYPE_IDS"]["System Requirement"] = int(default_req_type)
            print(f"[INFO] Legacy 'System Requirement' mapped to item type ID: {default_req_type}")
        except ValueError:
            print(f"[WARN] DEFAULT_REQUIREMENT_ITEM_TYPE_ID is not a valid integer: {default_req_type}")

    # Jama container childItemType is the type of content allowed inside the container.
    # It is not the type of the folder itself.
    # The script determines childItemType by:
    #   1. Inheriting from parent container metadata
    #   2. Inferring from requirement rows under the folder
    #   3. Using these .env values as fallback (only if 1 & 2 fail)
    # Most users can leave these unset.
    config["CHILD_ITEM_TYPE_IDS"] = {}

    try:
        set_child = os.getenv("JAMA_SET_CHILD_ITEM_TYPE", "")
        if set_child:
            config["CHILD_ITEM_TYPE_IDS"]["Set"] = int(set_child)

        folder_child = os.getenv("JAMA_FOLDER_CHILD_ITEM_TYPE", "")
        if folder_child:
            config["CHILD_ITEM_TYPE_IDS"]["Folder"] = int(folder_child)
    except ValueError as e:
        print(f"[ERROR] Child item type IDs must be integers: {e}")
        sys.exit(1)

    # Optional child item types for Segment and Subsystem (if required by your project)
    try:
        segment_child = os.getenv("JAMA_SEGMENT_CHILD_ITEM_TYPE", "")
        if segment_child:
            config["CHILD_ITEM_TYPE_IDS"]["Segment"] = int(segment_child)

        subsystem_child = os.getenv("JAMA_SUBSYSTEM_CHILD_ITEM_TYPE", "")
        if subsystem_child:
            config["CHILD_ITEM_TYPE_IDS"]["Subsystem"] = int(subsystem_child)
    except ValueError as e:
        print(f"[WARN] Optional child item type ID is not a valid integer: {e}")

    # Optional fallback for empty/new branches where parent metadata cannot determine childItemType.
    # Examples: Software Requirement=112, Subsystem Requirement=87, Stakeholder Requirement=97.
    default_req_child_type = os.getenv("DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE", "")
    if default_req_child_type:
        try:
            config["DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE"] = int(default_req_child_type)
            print(f"[INFO] Default requirement child item type: {config['DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE']}")
        except ValueError:
            print(f"[ERROR] DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE must be an integer, got: {default_req_child_type}")
            sys.exit(1)
    else:
        config["DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE"] = None

    config["IMPORT_MODE"] = os.getenv("IMPORT_MODE", "upsert").lower()
    if config["IMPORT_MODE"] not in ("create", "upsert"):
        print(f"[ERROR] Invalid IMPORT_MODE: {config['IMPORT_MODE']}")
        print("[ERROR] Must be one of: create, upsert")
        sys.exit(1)

    config["DRY_RUN"] = os.getenv("DRY_RUN", "true").lower() == "true"

    config["RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY"] = os.getenv("RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY", "true").lower() == "true"
    config["USE_EXCEL_ID_AS_DOCUMENT_KEY"] = os.getenv("USE_EXCEL_ID_AS_DOCUMENT_KEY", "true").lower() == "true"
    config["CREATE_MISSING_FOLDERS"] = os.getenv("CREATE_MISSING_FOLDERS", "true").lower() == "true"
    config["USE_FOLDER_DOCUMENT_KEY_CACHE"] = os.getenv("USE_FOLDER_DOCUMENT_KEY_CACHE", "true").lower() == "true"
    config["USE_GLOBAL_ID_LOOKUP"] = os.getenv("USE_GLOBAL_ID_LOOKUP", "true").lower() == "true"
    config["ENABLE_PRE_POST_DUPLICATE_CHECK"] = os.getenv("ENABLE_PRE_POST_DUPLICATE_CHECK", "true").lower() == "true"

    field_id = os.getenv("JAMA_FIELD_ID", "")
    if field_id.lower() in ("none", "null", ""):
        field_id = None

    # Jama requires fields.name in POST payloads.
    jama_field_name = os.getenv("JAMA_FIELD_NAME", "name").strip()
    if jama_field_name.lower() in ("", "none", "null"):
        print("[WARN] JAMA_FIELD_NAME is blank or invalid. Using default 'name'.")
        jama_field_name = "name"

    jama_field_description = os.getenv("JAMA_FIELD_DESCRIPTION", "description").strip()
    if jama_field_description.lower() in ("", "none", "null"):
        print("[WARN] JAMA_FIELD_DESCRIPTION is blank or invalid. Using default 'description'.")
        jama_field_description = "description"

    jama_field_verification_method = os.getenv("JAMA_FIELD_VERIFICATION_METHOD", "").strip()
    if jama_field_verification_method.lower() in ("none", "null"):
        jama_field_verification_method = ""

    config["FIELD_MAP"] = {
        "id": field_id,
        "name": jama_field_name,
        "description": jama_field_description,
        "verification_method": jama_field_verification_method if jama_field_verification_method else None
    }

    # Priority: OAuth > Bearer Token > Basic Auth
    config["JAMA_CLIENT_ID"] = os.getenv("JAMA_CLIENT_ID")
    config["JAMA_CLIENT_SECRET"] = os.getenv("JAMA_CLIENT_SECRET")
    config["JAMA_BEARER_TOKEN"] = os.getenv("JAMA_BEARER_TOKEN")
    config["JAMA_USERNAME"] = os.getenv("JAMA_USERNAME")
    config["JAMA_PASSWORD"] = os.getenv("JAMA_PASSWORD")

    if not config["JAMA_BASE_URL"].endswith("/rest/v1"):
        print(f"[WARN] JAMA_BASE_URL does not appear to end with /rest/v1")
        print(f"[WARN] Current value: {config['JAMA_BASE_URL']}")
        print(f"[WARN] Expected format: https://your-jama-instance.com/rest/v1")

    has_oauth = bool(config["JAMA_CLIENT_ID"] and config["JAMA_CLIENT_SECRET"])
    has_bearer = bool(config["JAMA_BEARER_TOKEN"])
    has_basic = bool(config["JAMA_USERNAME"] and config["JAMA_PASSWORD"])

    if not has_oauth and not has_bearer and not has_basic:
        print("[ERROR] Missing authentication credentials")
        print("[ERROR] Provide one of:")
        print("[ERROR]   - JAMA_CLIENT_ID and JAMA_CLIENT_SECRET (OAuth)")
        print("[ERROR]   - JAMA_BEARER_TOKEN")
        print("[ERROR]   - JAMA_USERNAME and JAMA_PASSWORD")
        sys.exit(1)

    # OAuth takes priority
    if has_oauth:
        config["AUTH_MODE"] = "OAuth 2.0 (Client Credentials)"
        config["OAUTH_TOKEN"] = None  # Populated on first API call
    elif has_bearer:
        config["AUTH_MODE"] = "Bearer Token"
    else:
        config["AUTH_MODE"] = "Basic Auth"

    ssl_verify_str = os.getenv("JAMA_SSL_VERIFY", "true").lower()
    ssl_cert_path = os.getenv("JAMA_SSL_CERT", "")

    if ssl_cert_path:
        config["SSL_VERIFY"] = ssl_cert_path
        config["SSL_VERIFY_DISPLAY"] = f"Custom cert: {ssl_cert_path}"
    elif ssl_verify_str == "false":
        config["SSL_VERIFY"] = False
        config["SSL_VERIFY_DISPLAY"] = "Disabled (not recommended)"
        print("[WARN] SSL verification is disabled. This should only be used temporarily for debugging.")
    else:
        config["SSL_VERIFY"] = True
        config["SSL_VERIFY_DISPLAY"] = "Enabled (standard)"

    config["DEBUG_JAMA_GET"] = os.getenv("DEBUG_JAMA_GET", "false").lower() == "true"
    config["DEBUG_JAMA_AUTH"] = os.getenv("DEBUG_JAMA_AUTH", "false").lower() == "true"

    # Jama caps maxResults at 50.
    page_size = int(os.getenv("JAMA_ITEMS_PAGE_SIZE", "50"))

    if page_size > 50:
        print(f"[WARN] JAMA_ITEMS_PAGE_SIZE={page_size} exceeds Jama max of 50. Clamping to 50.")
        page_size = 50

    if page_size < 1:
        print(f"[WARN] JAMA_ITEMS_PAGE_SIZE={page_size} is invalid. Using 50.")
        page_size = 50

    config["JAMA_ITEMS_PAGE_SIZE"] = page_size

    return config


def validate_configuration(config: dict):
    """
    Validate configuration for unsafe combinations.

    Raises:
        SystemExit: If configuration is unsafe
    """
    # Check for unsafe folder creation without lookup
    if config.get("CREATE_MISSING_FOLDERS", False) and not config.get("RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY", True):
        print("\n" + "=" * 80)
        print("[ERROR] Unsafe configuration detected!")
        print("=" * 80)
        print("CREATE_MISSING_FOLDERS=true but RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=false")
        print()
        print("This combination will create duplicate folders because the script won't")
        print("check if folders already exist before creating them.")
        print()
        print("Solution: Set RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true in .env")
        print("=" * 80 + "\n")
        sys.exit(1)


def print_configuration_summary(config: dict, mode: str = None, dry_run: bool = True):
    """
    Print configuration summary without exposing secrets.
    """
    print("\n" + "=" * 80)
    print("IMPORT CONFIGURATION")
    print("=" * 80)
    print(f"Input File:                           {config['EXCEL_FILE']}")
    print(f"Import Mode:                          {mode or config.get('IMPORT_MODE', 'upsert')}")
    print(f"Execution Mode:                       {'DRY RUN' if dry_run else 'EXECUTE'}")
    print(f"Resolve Folders by documentKey:       {config.get('RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY', True)}")
    print(f"Use Excel ID as documentKey:          {config.get('USE_EXCEL_ID_AS_DOCUMENT_KEY', True)}")
    print(f"Create Missing Folders:               {config.get('CREATE_MISSING_FOLDERS', True)}")
    print(f"Use Folder DocumentKey Cache:         {config.get('USE_FOLDER_DOCUMENT_KEY_CACHE', True)}")
    print(f"Use Global ID Lookup:                 {config.get('USE_GLOBAL_ID_LOOKUP', True)}")
    print(f"Pre-POST Duplicate Check:             {config.get('ENABLE_PRE_POST_DUPLICATE_CHECK', True)}")
    print(f"Root Parent Item ID:                  {config['ROOT_PARENT_ITEM_ID']}")
    print(f"Jama Project ID:                      {config['JAMA_PROJECT_ID']}")
    print(f"Authentication Mode:                  {config['AUTH_MODE']}")
    print(f"SSL Verification:                     {config.get('SSL_VERIFY_DISPLAY', 'Enabled (standard)')}")
    print()
    print("Item Type Mappings:")
    for name, type_id in config["ITEM_TYPE_IDS"].items():
        alias_note = " (alias of Set)" if name == "Subsystem" else ""
        print(f"  {name}: {type_id}{alias_note}")
    print()
    print("Field Mappings:")
    for field_name, field_api_name in config["FIELD_MAP"].items():
        print(f"  {field_name}: {field_api_name or '(not mapped)'}")
    print()
    # Verification Method Configuration
    verification_field = config["FIELD_MAP"].get("verification_method")
    if verification_field:
        if is_verification_method_field_key(verification_field):
            print(f"Verification Method Field:            {verification_field} (explicit .env override)")
        else:
            print(f"Verification Method Field:            {verification_field} (base name for dynamic search)")
    else:
        print(f"Verification Method Field:            dynamic (searches cached items for verification_method$...)")
    print(f"Verification Method Value Format:     array of picklist IDs (e.g., [422])")
    print(f"Verification Method Detection:        searches fields.keys() using startswith('verification_method$')")
    print("=" * 80 + "\n")


CONFIG = load_configuration()

ssl_verify_value = None


def get_ssl_verify():
    """
    Returns the value for requests verify parameter.

    Returns cert path if JAMA_SSL_CERT is set,
    False if JAMA_SSL_VERIFY=false, else True.
    """
    cert_path = os.getenv("JAMA_SSL_CERT", "").strip()
    if cert_path:
        return cert_path

    ssl_verify = os.getenv("JAMA_SSL_VERIFY", "true").strip().lower()
    return ssl_verify not in ("false", "0", "no", "off")


print(f"[INFO] Jama base URL: {CONFIG['JAMA_BASE_URL']}")
print(f"[INFO] Jama project ID: {CONFIG['JAMA_PROJECT_ID']}")

oauth_token_url_env = os.getenv("JAMA_OAUTH_TOKEN_URL", "")
if CONFIG["JAMA_CLIENT_ID"] and CONFIG["JAMA_CLIENT_SECRET"]:
    print(f"[INFO] OAuth token URL configured: {'yes (custom)' if oauth_token_url_env else 'no (using default)'}")

ssl_verify_value = get_ssl_verify()
if ssl_verify_value is False:
    print("[WARN] SSL verification is disabled. This should only be used temporarily for debugging.")
else:
    print(f"[INFO] SSL verify: {ssl_verify_value}")

print(f"[INFO] Debug Jama Auth: {CONFIG.get('DEBUG_JAMA_AUTH', False)}")
print(f"[INFO] Debug Jama GET: {CONFIG.get('DEBUG_JAMA_GET', False)}")


JAMA_BASE_URL = CONFIG["JAMA_BASE_URL"]
JAMA_PROJECT_ID = CONFIG["JAMA_PROJECT_ID"]
EXCEL_FILE = CONFIG["EXCEL_FILE"]
ROOT_PARENT_ITEM_ID = CONFIG["ROOT_PARENT_ITEM_ID"]
ITEM_TYPE_IDS = CONFIG["ITEM_TYPE_IDS"]
CHILD_ITEM_TYPE_IDS = CONFIG["CHILD_ITEM_TYPE_IDS"]
FIELD_MAP = CONFIG["FIELD_MAP"]
JAMA_CLIENT_ID = CONFIG["JAMA_CLIENT_ID"]
JAMA_CLIENT_SECRET = CONFIG["JAMA_CLIENT_SECRET"]
JAMA_BEARER_TOKEN = CONFIG["JAMA_BEARER_TOKEN"]
JAMA_USERNAME = CONFIG["JAMA_USERNAME"]
JAMA_PASSWORD = CONFIG["JAMA_PASSWORD"]

IMPORT_RESULTS_CSV = "output/import_results.csv"

CREATE_ITEM_ENDPOINT = "/items"

OAUTH_TOKEN_ENDPOINT = "/oauth/token"

# ============================================================
# API CONFIGURATION CONSTANTS
# ============================================================

# API endpoints
ITEMS_ENDPOINT = "/items"

# API timeouts (seconds)
JAMA_API_TIMEOUT = 60
OAUTH_TOKEN_TIMEOUT = 30

# OAuth
OAUTH_GRANT_TYPE = "client_credentials"

# Pagination
DEFAULT_LOOKUP_PAGE_SIZE = 20

# API call delay to avoid hammering the server
API_CALL_DELAY_SECONDS = 0.2

# Dry-run fake ID starting point
DRY_RUN_ID_START = 900000

# Global ID pattern for extraction from Excel cells
GLOBAL_ID_PATTERN = re.compile(r'GID-\d+', re.IGNORECASE)

# CSV export schema for import results
IMPORT_RESULTS_CSV_FIELDNAMES = [
    "excel_row",
    "action",
    "status",
    "jama_id",
    "document_key",
    "global_id",
    "source_id",
    "item_type",
    "name",
    "resolved_by",
    "section_number",
    "parent_section_number",
    "parent_item_id",
    "created_item_id",
    "updated_item_id",
    "current_parent_item_id",
    "desired_parent_item_id",
    "moved",
    "move_method",
    "error"
]


# ============================================================
# API HELPERS
# ============================================================

def build_api_url(endpoint: str) -> str:
    """
    Construct API URL from base URL and endpoint path.
    Handles leading/trailing slashes.

    Examples:
        build_api_url("/items") -> "https://host.com/rest/v1/items"
        build_api_url("items") -> "https://host.com/rest/v1/items"
    """
    base = JAMA_BASE_URL.rstrip("/")
    path = endpoint.lstrip("/")
    return f"{base}/{path}"


def parse_json_response(response, context: str):
    """
    Parse JSON response with detailed error diagnostics.

    Args:
        response: requests.Response object
        context: Description of the request (e.g., "OAuth token request", "GET /items")

    Returns:
        Parsed JSON data

    Raises:
        RuntimeError: If response is not valid JSON
    """
    content_type = response.headers.get("Content-Type", "")
    text_preview = response.text[:500] if response.text else "(empty response)"

    if CONFIG.get("DEBUG_JAMA_AUTH", False) and "token" in context.lower():
        print(f"[DEBUG] {context} content-type: {content_type}")
        print(f"[DEBUG] {context} response preview (first 500 chars): {text_preview}")
    elif CONFIG.get("DEBUG_JAMA_GET", False) and context.startswith("GET"):
        print(f"[DEBUG] {context} content-type: {content_type}")
        print(f"[DEBUG] {context} response preview (first 500 chars): {text_preview}")

    try:
        return response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"{context} did not return valid JSON.\n"
            f"Status: {response.status_code}\n"
            f"URL: {response.url}\n"
            f"Content-Type: {content_type}\n"
            f"Response preview:\n{text_preview}\n\n"
            f"Likely causes: authentication failure, HTML login page, wrong OAuth URL, "
            f"wrong JAMA_BASE_URL, SSL/proxy issue, or expired/incorrect credentials."
        ) from exc


def get_oauth_token() -> str:
    """
    Exchange OAuth client credentials for an access token.
    Token is cached in CONFIG["OAUTH_TOKEN"] for reuse.
    """
    if not JAMA_CLIENT_ID or not JAMA_CLIENT_SECRET:
        raise RuntimeError("OAuth credentials not configured")

    if CONFIG.get("OAUTH_TOKEN"):
        return CONFIG["OAUTH_TOKEN"]

    print("[INFO] Obtaining OAuth access token...")

    # Jama OAuth endpoint is typically at /rest/oauth/token, not /rest/v1/oauth/token.
    oauth_token_url = os.getenv("JAMA_OAUTH_TOKEN_URL", "")

    if oauth_token_url:
        token_url = oauth_token_url
    else:
        base_without_v1 = JAMA_BASE_URL.rstrip('/').replace('/rest/v1', '')
        token_url = f"{base_without_v1}/rest/oauth/token"

    if CONFIG.get("DEBUG_JAMA_AUTH", False):
        print(f"[DEBUG] OAuth token URL: {token_url}")

    payload = {
        "grant_type": OAUTH_GRANT_TYPE
    }

    response = requests.post(
        token_url,
        auth=(JAMA_CLIENT_ID, JAMA_CLIENT_SECRET),
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=OAUTH_TOKEN_TIMEOUT,
        verify=get_ssl_verify()
    )

    if CONFIG.get("DEBUG_JAMA_AUTH", False):
        print(f"[DEBUG] OAuth status: {response.status_code}")

    if not response.ok:
        content_type = response.headers.get("Content-Type", "")
        raise RuntimeError(
            f"OAuth token request failed: {response.status_code}\n"
            f"URL: {token_url}\n"
            f"Content-Type: {content_type}\n"
            f"Response preview:\n{response.text[:500]}\n\n"
            f"Check JAMA_CLIENT_ID and JAMA_CLIENT_SECRET in .env"
        )

    token_data = parse_json_response(response, "OAuth token request")
    access_token = token_data.get("access_token")

    if not access_token:
        raise RuntimeError(
            f"No access_token in OAuth response.\n"
            f"URL: {token_url}\n"
            f"Response keys: {list(token_data.keys())}"
        )

    CONFIG["OAUTH_TOKEN"] = access_token
    print("[INFO] OAuth access token obtained successfully")

    return access_token


def get_headers() -> Dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Priority: OAuth > Bearer Token > Basic Auth
    if JAMA_CLIENT_ID and JAMA_CLIENT_SECRET:
        token = get_oauth_token()
        headers["Authorization"] = f"Bearer {token}"
    elif JAMA_BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {JAMA_BEARER_TOKEN}"

    return headers


def get_auth():
    """
    Returns Basic Auth tuple if configured, else None.
    OAuth and Bearer Token use headers, not auth parameter.
    """
    if JAMA_CLIENT_ID and JAMA_CLIENT_SECRET:
        return None

    if JAMA_BEARER_TOKEN:
        return None

    if JAMA_USERNAME and JAMA_PASSWORD:
        return (JAMA_USERNAME, JAMA_PASSWORD)

    return None


def jama_post(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST to Jama API with payload validation.

    Args:
        endpoint: API endpoint path
        payload: Request payload

    Returns:
        Parsed JSON response

    Raises:
        ValueError: If payload is missing required fields.name
        RuntimeError: If POST request fails
    """
    # Jama requires fields.name in POST payloads.
    fields = payload.get("fields", {})
    if "name" not in fields or not str(fields.get("name", "")).strip():
        raise ValueError(
            f"POST payload missing required fields.name. "
            f"Check JAMA_FIELD_NAME in .env; it must normally be 'name'. "
            f"Payload fields keys: {list(fields.keys())}"
        )

    url = build_api_url(endpoint)

    response = requests.post(
        url,
        headers=get_headers(),
        auth=get_auth(),
        data=json.dumps(payload),
        timeout=JAMA_API_TIMEOUT,
        verify=get_ssl_verify()
    )

    if not response.ok:
        content_type = response.headers.get("Content-Type", "")
        error_msg = f"POST failed: {response.status_code}\n"
        error_msg += f"URL: {url}\n"
        error_msg += f"Content-Type: {content_type}\n"
        error_msg += f"Payload:\n{json.dumps(payload, indent=2)}\n"
        error_msg += f"Response preview:\n{response.text[:500]}\n"

        # Verification method field rejection guidance
        response_text = response.text[:500]
        verification_field_keys = [k for k in fields.keys() if is_verification_method_field_key(k)]
        if verification_field_keys and "Could not parse" in response_text and "verification_method" in response_text:
            verification_field_key = verification_field_keys[0]
            verification_value = fields.get(verification_field_key)
            error_msg += f"\n"
            error_msg += f"VERIFICATION METHOD ERROR GUIDANCE:\n"
            error_msg += f"The verification method field '{verification_field_key}' was rejected with value '{verification_value}'.\n"
            error_msg += f"Verification Method uses a list of picklist option IDs, e.g. [422].\n"
            error_msg += f"If Jama rejects it, the field key suffix may be wrong for this item type/project.\n"
            error_msg += f"Try configuring JAMA_FIELD_VERIFICATION_METHOD explicitly using the field key seen\n"
            error_msg += f"in a known-good Jama item, such as verification_method$243.\n"

        raise RuntimeError(error_msg)

    return parse_json_response(response, f"POST {endpoint}")


def jama_get(endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    GET from Jama API with robust error handling and debugging support.
    """
    url = build_api_url(endpoint)

    # Debug logging if enabled
    if CONFIG.get("DEBUG_JAMA_GET", False):
        print(f"[DEBUG] GET URL: {url}")
        print(f"[DEBUG] GET params: {params}")

    response = requests.get(
        url,
        headers=get_headers(),
        auth=get_auth(),
        params=params,
        timeout=JAMA_API_TIMEOUT,
        verify=get_ssl_verify()
    )

    # Debug response info
    if CONFIG.get("DEBUG_JAMA_GET", False):
        print(f"[DEBUG] GET status: {response.status_code}")

    if not response.ok:
        content_type = response.headers.get("Content-Type", "")
        raise RuntimeError(
            f"GET failed: {response.status_code}\n"
            f"URL: {url}\n"
            f"Content-Type: {content_type}\n"
            f"Response preview:\n{response.text[:500]}"
        )

    # Validate that response is JSON before parsing
    content_type = response.headers.get("Content-Type", "")
    if "application/json" not in content_type.lower():
        raise RuntimeError(
            f"GET {endpoint} did not return JSON.\n"
            f"Status: {response.status_code}\n"
            f"URL: {url}\n"
            f"Content-Type: {content_type}\n"
            f"Response preview:\n{response.text[:500]}\n\n"
            f"Likely causes: authentication redirect, wrong JAMA_BASE_URL, SSL/proxy issue, or API endpoint mismatch."
        )

    return parse_json_response(response, f"GET {endpoint}")


# Folder documentKey lookup cache
_folder_document_key_cache = None
_folder_document_key_duplicates = {}

# Metadata cache for resolved items (folders, sets, containers).
# Tracks actual Jama metadata including childItemType for dynamic routing.
_item_metadata_by_id = {}  # item_id -> full item dict
_items_by_document_key = {}  # documentKey -> full item dict
_items_by_source_id = {}  # source ID (Excel ID) -> full item dict
_items_by_global_id = {}  # globalId -> full item dict
_items_by_global_id_duplicates = {}  # globalId -> list of item dicts


def build_folder_document_key_cache() -> Dict[str, Dict[str, Any]]:
    """
    Fetch all items from the project and build a cache of folders by documentKey.

    Returns:
        Dict mapping documentKey -> full Jama item dict

    Raises:
        RuntimeError: If API call fails

    Side effects:
        Populates global _folder_document_key_duplicates with duplicate documentKeys
    """
    # API configuration for fetching items
    endpoint = ITEMS_ENDPOINT

    global _folder_document_key_cache, _folder_document_key_duplicates

    if _folder_document_key_cache is not None:
        return _folder_document_key_cache

    print(f"[INFO] Building folder documentKey cache from Jama project {JAMA_PROJECT_ID}...")

    folder_type_id = ITEM_TYPE_IDS.get("Folder")
    folder_cache = {}
    duplicates = {}
    start_index = 0
    page_size = CONFIG.get("JAMA_ITEMS_PAGE_SIZE", 50)
    total_items_fetched = 0
    total_folders_cached = 0

    # Suppress debug output during cache build to avoid excessive logging.
    original_debug_get = CONFIG.get("DEBUG_JAMA_GET", False)
    if original_debug_get:
        print("[DEBUG] Temporarily suppressing GET debug output during cache build...")
        CONFIG["DEBUG_JAMA_GET"] = False

    try:
        while True:
            params = {
                "project": JAMA_PROJECT_ID,
                "startAt": start_index,
                "maxResults": page_size
            }

            response = jama_get(endpoint, params=params)

            data = response.get("data", [])
            meta = response.get("meta", {})
            page_info = meta.get("pageInfo", {})

            total_items_fetched += len(data)

            for item in data:
                item_id = item.get("id")
                doc_key = item.get("documentKey")
                item_type = item.get("itemType")

                # Store all items in metadata cache for location tracking.
                global _item_metadata_by_id, _items_by_document_key, _items_by_global_id, _items_by_global_id_duplicates
                if item_id:
                    _item_metadata_by_id[item_id] = item
                if doc_key:
                    _items_by_document_key[doc_key] = item

                # Store by global ID with duplicate detection
                global_id = item.get("globalId") or item.get("fields", {}).get("globalID") or item.get("fields", {}).get("globalId")
                if global_id:
                    global_id_str = str(global_id).strip()

                    # Check for duplicates
                    if global_id_str in _items_by_global_id:
                        # Duplicate found
                        if global_id_str not in _items_by_global_id_duplicates:
                            # First duplicate - move original to duplicates dict
                            _items_by_global_id_duplicates[global_id_str] = [_items_by_global_id[global_id_str], item]
                            del _items_by_global_id[global_id_str]
                        else:
                            # Additional duplicate
                            _items_by_global_id_duplicates[global_id_str].append(item)
                    elif global_id_str in _items_by_global_id_duplicates:
                        # Already marked as duplicate
                        _items_by_global_id_duplicates[global_id_str].append(item)
                    else:
                        # First occurrence
                        _items_by_global_id[global_id_str] = item

                # Build folder cache.
                if (item_type == folder_type_id and
                    item.get("project") == JAMA_PROJECT_ID and
                    doc_key):

                    if doc_key in folder_cache:
                        if doc_key not in duplicates:
                            duplicates[doc_key] = [folder_cache[doc_key], item]
                            del folder_cache[doc_key]
                        else:
                            duplicates[doc_key].append(item)
                    elif doc_key in duplicates:
                        duplicates[doc_key].append(item)
                    else:
                        folder_cache[doc_key] = item
                        total_folders_cached += 1

            result_count = page_info.get("resultCount", len(data))
            total_results = page_info.get("totalResults", len(data))

            if start_index + result_count >= total_results or len(data) == 0:
                break

            start_index += result_count

    finally:
        CONFIG["DEBUG_JAMA_GET"] = original_debug_get

    _folder_document_key_duplicates = duplicates

    _folder_document_key_cache = folder_cache

    print(f"[INFO] Fetched {total_items_fetched} total items from project.")
    print(f"[INFO] Cached {total_folders_cached} folders by documentKey.")
    print(f"[INFO] Total items in metadata cache: {len(_item_metadata_by_id)}")
    if duplicates:
        print(f"[WARN] Found {len(duplicates)} documentKeys with multiple folders (will fail if resolved).")
    print(f"[INFO] Cached {len(_items_by_global_id)} items by Global ID.")
    if _items_by_global_id_duplicates:
        print(f"[WARN] Found {len(_items_by_global_id_duplicates)} Global IDs with multiple items (will fail if resolved).")

    if folder_cache and CONFIG.get("DEBUG_JAMA_GET", False):
        sample_keys = list(folder_cache.keys())[:10]
        print(f"[DEBUG] Sample cached documentKeys: {sample_keys}")

    return folder_cache


def find_existing_folder_by_document_key(document_key: str) -> Optional[Dict[str, Any]]:
    """
    Find existing folder in Jama by documentKey.

    Uses cached lookup if USE_FOLDER_DOCUMENT_KEY_CACHE=true (default),
    otherwise falls back to per-folder API lookup.

    Returns:
        Full item dict if exactly one matching folder found, None otherwise.
        Item dict includes: id, documentKey, globalId, itemType, project, childItemType, location, fields

    Raises:
        RuntimeError: If API call fails
        ValueError: If multiple matching folders found
    """
    if not document_key:
        return None

    if CONFIG.get("USE_FOLDER_DOCUMENT_KEY_CACHE", True):
        return _find_folder_by_cache(document_key)
    else:
        return _find_folder_by_api_lookup(document_key)


def _find_folder_by_cache(document_key: str) -> Optional[Dict[str, Any]]:
    """
    Find folder using cached documentKey lookup.

    Returns:
        Full item dict if exactly one match found, None otherwise

    Raises:
        ValueError: If multiple matching folders found
    """
    global _folder_document_key_cache, _folder_document_key_duplicates

    if _folder_document_key_cache is None:
        build_folder_document_key_cache()

    if document_key in _folder_document_key_duplicates:
        duplicate_count = len(_folder_document_key_duplicates[document_key])
        raise ValueError(
            f"Folder documentKey '{document_key}' matched {duplicate_count} folders. "
            f"Please provide explicit Jama ID to resolve ambiguity."
        )

    return _folder_document_key_cache.get(document_key)


def _find_folder_by_api_lookup(document_key: str) -> Optional[Dict[str, Any]]:
    """
    Find folder using per-folder API lookup (fallback method).

    Returns:
        Full item dict if exactly one match found, None otherwise

    Raises:
        RuntimeError: If API call fails
        ValueError: If multiple matching folders found
    """
    try:
        # API configuration for folder lookup
        endpoint = ITEMS_ENDPOINT
        max_results = DEFAULT_LOOKUP_PAGE_SIZE

        folder_type_id = ITEM_TYPE_IDS.get("Folder")
        all_matching_folders = []
        start_index = 0

        while True:
            params = {
                "project": JAMA_PROJECT_ID,
                "contains": document_key,
                "startAt": start_index,
                "maxResults": max_results
            }

            response = jama_get(endpoint, params=params)

            data = response.get("data", [])
            meta = response.get("meta", {})
            page_info = meta.get("pageInfo", {})

            matching_folders = [
                item for item in data
                if (item.get("itemType") == folder_type_id and
                    item.get("documentKey") == document_key and
                    item.get("project") == JAMA_PROJECT_ID)
            ]

            all_matching_folders.extend(matching_folders)

            if len(all_matching_folders) > 0:
                break

            result_count = page_info.get("resultCount", len(data))
            total_results = page_info.get("totalResults", len(data))

            if start_index + result_count >= total_results or len(data) == 0:
                break

            start_index += result_count

        if len(all_matching_folders) == 0:
            return None
        elif len(all_matching_folders) == 1:
            return all_matching_folders[0]
        else:
            raise ValueError(
                f"Found {len(all_matching_folders)} folders with documentKey '{document_key}'. "
                f"documentKey should be unique. Please provide explicit Jama ID to resolve ambiguity."
            )

    except ValueError:
        raise
    except (RuntimeError, json.JSONDecodeError, Exception) as e:
        raise RuntimeError(f"Failed to lookup documentKey '{document_key}': {e}")


def get_item_metadata(item_id: int) -> Optional[Dict[str, Any]]:
    """
    Get metadata for a resolved item from cache.

    Args:
        item_id: Jama item ID

    Returns:
        Item metadata dict if available, None otherwise
    """
    return _item_metadata_by_id.get(item_id)


def store_item_metadata(item_id: int, item_data: Dict[str, Any]) -> None:
    """
    Store item metadata for dynamic childItemType resolution.

    Args:
        item_id: Jama item ID
        item_data: Full item dict from Jama API
    """
    global _item_metadata_by_id, _items_by_document_key, _items_by_global_id
    _item_metadata_by_id[item_id] = item_data

    doc_key = item_data.get("documentKey")
    if doc_key:
        _items_by_document_key[doc_key] = item_data

    # Also cache by Global ID if available
    global_id = item_data.get("globalId") or item_data.get("fields", {}).get("globalID") or item_data.get("fields", {}).get("globalId")
    if global_id:
        global_id_str = str(global_id).strip()
        _items_by_global_id[global_id_str] = item_data


def find_existing_item_by_document_key(document_key: str) -> Optional[Dict[str, Any]]:
    """
    Find any existing item (not just folders) by documentKey.

    Returns:
        Item dict if found, None otherwise
    """
    if not document_key:
        return None

    if _folder_document_key_cache is None:
        build_folder_document_key_cache()

    return _items_by_document_key.get(document_key)


def extract_global_id_from_value(value: str, warn_if_unparseable: bool = False) -> Optional[str]:
    """
    Extract Global ID from Excel value, handling both raw and HYPERLINK formula formats.

    Supports:
    - Raw: "GID-768902"
    - HYPERLINK: '=HYPERLINK("...","GID-768902")'

    Args:
        value: Excel cell value
        warn_if_unparseable: If True and value is populated but no GID pattern found, print warning

    Returns:
        Extracted Global ID (e.g., "GID-768902") or None
    """
    if not value or not isinstance(value, str):
        return None

    value = value.strip()
    if not value:
        return None

    # Pattern: GID-<digits>
    import re
    match = GLOBAL_ID_PATTERN.search(value)
    if match:
        return match.group(0)

    # Value was populated but no GID pattern found
    if warn_if_unparseable:
        print(f"[WARN] Global ID value was populated but no GID-#### pattern could be extracted: {value[:100]}")

    return None


def find_existing_item_by_global_id(global_id: str) -> Optional[Dict[str, Any]]:
    """
    Find existing item (any type) by Global ID.

    Returns:
        Item dict if found, None otherwise

    Raises:
        ValueError: If Global ID matches multiple items
    """
    if not global_id:
        return None

    if _folder_document_key_cache is None:
        build_folder_document_key_cache()

    global_id_str = str(global_id).strip()

    # Check for duplicates
    global _items_by_global_id_duplicates
    if global_id_str in _items_by_global_id_duplicates:
        duplicate_count = len(_items_by_global_id_duplicates[global_id_str])
        raise ValueError(
            f"Global ID '{global_id_str}' matched {duplicate_count} items. "
            f"Please provide explicit Jama ID to resolve ambiguity."
        )

    return _items_by_global_id.get(global_id_str)


def normalize_for_match(text: str) -> str:
    """
    Normalize text for duplicate matching.

    Strips leading/trailing whitespace and collapses internal whitespace.

    Args:
        text: Text to normalize

    Returns:
        Normalized text

    Examples:
        normalize_for_match("  External  Interfaces  ") -> "External Interfaces"
        normalize_for_match("Test\n\nData") -> "Test Data"
    """
    if not text:
        return ""

    # Strip whitespace and collapse internal whitespace
    return " ".join(str(text).split())


def find_existing_item_by_parent_type_name(
    parent_item_id: int,
    item_type_id: int,
    name: str,
    child_item_type: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Find existing item by parent ID, item type, and normalized name.

    Used for pre-POST duplicate checking and folder resolution.
    Searches _item_metadata_by_id cache for matching items.

    Args:
        parent_item_id: Parent item ID
        item_type_id: Item type ID to match
        name: Item name to match (will be normalized)
        child_item_type: Optional childItemType for folder matching

    Returns:
        Item dict if exactly one match found, None if no match

    Raises:
        ValueError: If multiple items match (ambiguous)

    Examples:
        find_existing_item_by_parent_type_name(12345, 32, "External Interfaces")
        -> Returns folder dict if exactly one match

        find_existing_item_by_parent_type_name(12345, 32, "Test Folder", child_item_type=112)
        -> Returns folder dict with matching childItemType if exactly one match
    """
    if not parent_item_id or not item_type_id or not name:
        return None

    # Build cache if not already built
    if _folder_document_key_cache is None:
        build_folder_document_key_cache()

    normalized_name = normalize_for_match(name)
    if not normalized_name:
        return None

    matches = []

    global _item_metadata_by_id
    for item in _item_metadata_by_id.values():
        # Match parent
        item_parent_id = get_current_parent_id(item)
        if item_parent_id != parent_item_id:
            continue

        # Match item type
        if item.get("itemType") != item_type_id:
            continue

        # Match normalized name
        item_name = item.get("fields", {}).get("name", "")
        if normalize_for_match(item_name) != normalized_name:
            continue

        # For folders, optionally match childItemType if provided
        if child_item_type is not None:
            item_child_type = item.get("childItemType")
            # Only enforce if both have values
            if item_child_type and child_item_type != item_child_type:
                continue

        matches.append(item)

    if len(matches) == 0:
        return None
    elif len(matches) == 1:
        return matches[0]
    else:
        # Multiple matches - ambiguous
        item_ids = [str(item.get("id")) for item in matches]
        item_type_name = next((k for k, v in ITEM_TYPE_IDS.items() if v == item_type_id), str(item_type_id))
        raise ValueError(
            f"Found {len(matches)} items matching parent={parent_item_id}, "
            f"itemType={item_type_id} ({item_type_name}), name='{name}'.\n"
            f"Matching item IDs: {', '.join(item_ids)}\n"
            f"Cannot determine which item to use. Provide explicit Jama ID to resolve ambiguity."
        )


def validate_item_type_match(item: Dict[str, Any], expected_item_type: str, global_id: str) -> None:
    """
    Validate that resolved item's type matches expected Excel Item Type.

    Args:
        item: Resolved Jama item dict
        expected_item_type: Item Type from Excel row
        global_id: Global ID used for resolution (for error messages)

    Raises:
        ValueError: If item types don't match
    """
    if expected_item_type not in ITEM_TYPE_IDS:
        raise ValueError(f"Unsupported Item Type: {expected_item_type}")

    expected_type_id = ITEM_TYPE_IDS[expected_item_type]
    actual_type_id = item.get("itemType")

    if actual_type_id != expected_type_id:
        actual_type_name = next((k for k, v in ITEM_TYPE_IDS.items() if v == actual_type_id), str(actual_type_id))
        raise ValueError(
            f"Global ID '{global_id}' resolved to item type '{actual_type_name}' (itemType={actual_type_id}), "
            f"but Excel row is Item Type '{expected_item_type}' (itemType={expected_type_id}). "
            f"Global ID does not match expected item type."
        )


def validate_folder_child_item_type_compatibility(
    found_folder: Dict[str, Any],
    expected_child_type: Optional[int],
    folder_name: str,
    resolution_method: str
) -> None:
    """
    Validate folder childItemType compatibility.

    Used by both documentKey and Global ID folder resolution.

    Args:
        found_folder: Resolved folder item dict
        expected_child_type: Expected childItemType (from parent/inference/config)
        folder_name: Folder name for error messages
        resolution_method: "Global ID" or "documentKey" for logging

    Raises:
        ValueError: If childItemType is incompatible
    """
    existing_child_type = found_folder.get("childItemType")
    folder_id = found_folder.get("id")
    folder_doc_key = found_folder.get("documentKey", "unknown")

    if expected_child_type and existing_child_type and expected_child_type != existing_child_type:
        # childItemType mismatch - fail clearly
        expected_type_name = next((k for k, v in ITEM_TYPE_IDS.items() if v == expected_child_type), str(expected_child_type))
        existing_type_name = next((k for k, v in ITEM_TYPE_IDS.items() if v == existing_child_type), str(existing_child_type))

        raise ValueError(
            f"Folder resolved by {resolution_method} has incompatible childItemType.\n"
            f"Folder: '{folder_name}'\n"
            f"Jama ID: {folder_id}\n"
            f"Document Key: {folder_doc_key}\n"
            f"Existing childItemType: {existing_child_type} ({existing_type_name})\n"
            f"Expected childItemType: {expected_child_type} ({expected_type_name})\n\n"
            f"This folder cannot hold the expected content type.\n"
            f"Either use a different folder or update the folder's childItemType in Jama."
        )


def get_current_parent_id(item: Dict[str, Any]) -> Optional[int]:
    """
    Extract current parent item ID from item metadata.

    Args:
        item: Full item dict with location info

    Returns:
        Parent item ID, or None if not available
    """
    location = item.get("location", {})
    parent_info = location.get("parent", {})
    parent_id = parent_info.get("item")
    return int(parent_id) if parent_id else None


def get_created_item_id(response: Dict[str, Any]) -> int:
    """
    Extract created item ID from Jama POST response.

    Typical Jama responses return response["data"]["id"].
    """
    data = response.get("data")

    if isinstance(data, dict) and data.get("id"):
        return int(data["id"])

    if response.get("id"):
        return int(response["id"])

    raise ValueError(f"Could not find created item ID in response: {response}")


def extract_item_metadata(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract item metadata from Jama API response.
    Returns dict with: jama_id, document_key, global_id

    Raises:
        ValueError: If item ID cannot be extracted
    """
    # Try multiple response structures:
    # 1. response["data"]["id"] - typical GET response
    # 2. response["meta"]["id"] - POST/PUT response
    # 3. response["id"] - fallback

    item_id = None
    document_key = ""
    global_id = ""

    data = response.get("data")
    if isinstance(data, dict):
        item_id = data.get("id")
        document_key = data.get("documentKey", "")
        global_id = data.get("globalId", "")

    # POST responses typically don't include documentKey/globalId in meta.
    if not item_id:
        meta = response.get("meta")
        if isinstance(meta, dict):
            item_id = meta.get("id")

    if not item_id:
        item_id = response.get("id")

    if not item_id:
        raise ValueError(
            f"Created item ID is missing from Jama response.\n"
            f"Response preview: {json.dumps(response, indent=2)[:500]}\n"
            f"This may indicate a POST failure or unexpected response format."
        )

    return {
        "jama_id": int(item_id),
        "document_key": document_key,
        "global_id": global_id
    }


# ============================================================
# EXCEL HELPERS
# ============================================================

# Item type classifications
REQUIREMENT_ITEM_TYPES = {
    "Stakeholder Requirement",
    "Subsystem Requirement",
    "Software Requirement",
    "System Requirement",
}

STRUCTURE_ITEM_TYPES = {
    "Set",
    "Folder",
    "Segment",
    "Subsystem",
}


def is_requirement_row(item_type: str) -> bool:
    """Check if item type is a requirement."""
    return item_type in REQUIREMENT_ITEM_TYPES


def requires_description(item_type: str) -> bool:
    """Check if item type requires a description."""
    return is_requirement_row(item_type)


def load_excel(path: str) -> pd.DataFrame:
    df = pd.read_excel(path).fillna("")

    # Required columns - Description is optional
    required_columns = ["ID", "Item Type", "Name"]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required Excel column: {col}")

    # Optional columns for upsert support and descriptions
    optional_columns = ["Description", "Jama ID", "Document Key", "Global ID", "Verification Method"]

    # Add missing optional columns
    for col in optional_columns:
        if col not in df.columns:
            df[col] = ""

    # Ensure all columns are strings and stripped
    for col in required_columns + optional_columns:
        df[col] = df[col].astype(str).str.strip()

    # Drop rows with no item type or no name.
    df = df[df["Item Type"] != ""]
    df = df[df["Name"] != ""]

    return df


def validate_item_types(df: pd.DataFrame) -> None:
    """
    Validate that all Item Type values in the input file are supported.
    """
    unique_types = df["Item Type"].unique()
    unsupported_types = []

    for item_type in unique_types:
        if item_type not in ITEM_TYPE_IDS:
            unsupported_types.append(item_type)

    if unsupported_types:
        print("\n" + "=" * 80)
        print("[ERROR] Unsupported Item Types found in input file:")
        for item_type in unsupported_types:
            print(f"  - '{item_type}'")
        print()
        print("Supported Item Types:")
        for supported_type in ITEM_TYPE_IDS.keys():
            print(f"  - {supported_type}")
        print()
        if "System Requirement" in unsupported_types:
            print("Note: 'System Requirement' is a legacy item type.")
            print("      Set DEFAULT_REQUIREMENT_ITEM_TYPE_ID in .env to map it,")
            print("      or update your Excel file to use the explicit requirement types:")
            print("        - Stakeholder Requirement")
            print("        - Subsystem Requirement")
            print("        - Software Requirement")
        print("=" * 80)
        sys.exit(1)

    # Note: Child item types are no longer validated here.
    # The script now determines childItemType dynamically:
    #   1. Infers from items under the folder (lookahead)
    #   2. Inherits from parent container
    #   3. Uses .env fallback if configured
    # Validation happens at creation time with helpful error messages.

    # Validate that requirement rows have descriptions
    has_requirements = any(item_type in REQUIREMENT_ITEM_TYPES for item_type in unique_types)
    if has_requirements and "Description" not in df.columns:
        print("[ERROR] Input contains requirement rows but Description column is missing")
        print("[ERROR] Requirement types (Stakeholder, Subsystem, Software) require descriptions")
        sys.exit(1)


# ============================================================
# SECTION / HIERARCHY HELPERS
# ============================================================

def extract_section_number(name: str) -> Optional[str]:
    """
    Extract section number from folder name using strict rules to avoid false positives.

    Only matches:
    - Numbers at the start (after optional classification): "3.2.1 External Interfaces"
    - Numbers after "Section" keyword: "Section 1.1.1 Signal Processing"
    - Supports trailing dot for top-level sections: "3." or "3. REQUIREMENTS"

    Does NOT match:
    - Numbers in middle/end: "UAI / 1553 Interface" -> None
    - Large numbers (>99): "1553" -> None (likely standards, not sections)

    Examples:
        "Section 1.0"                         -> "1.0"
        "Folder Section 1.1"                  -> "1.1"
        "(U) Section 1.1.1 Signal Processing" -> "1.1.1"
        "3.2.1 External Interfaces"           -> "3.2.1"
        "(U) 3.2 Requirements"                -> "3.2"
        "3. REQUIREMENTS"                     -> "3."
        "3 REQUIREMENTS"                      -> "3"
        "(U) Sample Requirements"             -> None
        "(U) UAI / 1553 Interface"            -> None
        "MIL-STD-1553 Requirements"           -> None
    """
    name_str = str(name).strip()

    # Pattern 1: "Section X.Y.Z"
    section_match = re.search(r"\bSection\s+(\d+(?:\.\d+)*\.?)\b", name_str, re.IGNORECASE)
    if section_match:
        return section_match.group(1)

    # Pattern 2: Number at start (after optional classification like "(U)").
    # Captures: "3 REQUIREMENTS", "3. REQUIREMENTS", "3.0 REQUIREMENTS", "3.1 REQUIRED STATES"
    start_match = re.match(r"^(?:\([A-Z]+\)\s+)?(\d+(?:\.\d+)*\.?)\s+", name_str)
    if start_match:
        section = start_match.group(1)
        # Only accept if first number < 100 (avoids standards like 1553).
        first_num = int(section.split('.')[0])
        if first_num < 100:
            return section

    return None


def normalize_top_level_section(section_number: str) -> str:
    """
    Normalize top-level sections to standard ".0" format.

    Allows Excel files to use any of these forms:
    - "3 REQUIREMENTS" -> "3.0"
    - "3. REQUIREMENTS" -> "3.0"
    - "3.0 REQUIREMENTS" -> "3.0"

    Examples:
        "3"    -> "3.0"
        "3."   -> "3.0"
        "3.0"  -> "3.0"
        "3.1"  -> "3.1"
        "3.1.1" -> "3.1.1"
    """
    section_number = section_number.rstrip(".")

    parts = section_number.split(".")

    if len(parts) == 1:
        return f"{section_number}.0"

    return section_number


def get_parent_section_number(section_number: str) -> Optional[str]:
    """
    Determine parent section based on section numbering.

    Examples:
        1.0     -> None
        1.1     -> 1.0
        1.1.1   -> 1.1
        3.2.4   -> 3.2
    """
    section_number = normalize_top_level_section(section_number)
    parts = section_number.split(".")

    if len(parts) <= 1:
        return None

    if len(parts) == 2:
        # Section 1.1 belongs under Section 1.0.
        if parts[1] == "0":
            return None

        return f"{parts[0]}.0"

    return ".".join(parts[:-1])


# ============================================================
# PAYLOAD BUILDERS
# ============================================================

def build_fields(row: pd.Series, item_type_id: int = None) -> Dict[str, Any]:
    """
    Build fields dict for Jama API payload.

    Args:
        row: DataFrame row with item data
        item_type_id: Optional item type ID for dynamic field key resolution

    Returns:
        Dict with field API names as keys

    Raises:
        ValueError: If required Name field is blank
    """
    item_type = row["Item Type"]

    if item_type_id is None:
        if item_type not in ITEM_TYPE_IDS:
            raise ValueError(f"Unsupported Item Type for verification method lookup: {item_type}")
        item_type_id = ITEM_TYPE_IDS[item_type]

    name_value = str(row.get("Name", "")).strip()
    if not name_value:
        raise ValueError("Name field is required but is blank or missing.")

    fields = {
        FIELD_MAP["name"]: name_value
    }

    # Excel ID as Jama custom field (if configured and available).
    if FIELD_MAP.get("id") and row["ID"]:
        fields[FIELD_MAP["id"]] = row["ID"]

    # Only include description if present.
    # Structure types (Set, Folder, Segment, Subsystem) typically don't have descriptions.
    description = row.get("Description", "").strip()
    if description:
        fields[FIELD_MAP["description"]] = description

    # Verification method (requirement rows only).
    if item_type in REQUIREMENT_ITEM_TYPES:
        verification_value = row.get("Verification Method", "").strip()
        if verification_value:
            canonical_value = normalize_verification_method(verification_value)
            if not canonical_value:
                supported_values = ", ".join(sorted(set(
                    list(VERIFICATION_METHOD_ALIASES.keys()) + list(VERIFICATION_METHOD_IMPORT_MAP.keys())
                )))
                raise ValueError(
                    f"Unsupported Verification Method value: '{verification_value}'.\n"
                    f"Supported values: {supported_values}"
                )

            picklist_id = get_verification_method_picklist_id(canonical_value)
            if picklist_id is None:
                raise ValueError(
                    f"Could not map verification method '{canonical_value}' to Jama picklist ID"
                )

            # Jama field suffixes vary by project/item type, so discover verification_method$... keys from cached item fields.
            verification_field_key, resolution_source = resolve_verification_method_field_key(
                item_type_name=item_type,
                item_type_id=item_type_id,
                parent_item_id=None,
                row=row
            )

            if not verification_field_key:
                # Collect available keys for detailed error message
                global _item_metadata_by_id
                type_specific_keys = collect_verification_method_field_keys_from_cached_items(item_type_id)
                all_keys = collect_verification_method_field_keys_from_cached_items()

                if resolution_source == "multiple_type_specific":
                    keys_str = ", ".join(sorted(type_specific_keys))
                    raise ValueError(
                        f"Row has Verification Method populated, but multiple verification method field keys found for {item_type} (itemType={item_type_id}):\n"
                        f"  {keys_str}\n\n"
                        f"Could not determine which to use.\n\n"
                        f"Solution: Set JAMA_FIELD_VERIFICATION_METHOD in .env to the correct key.\n"
                        f"Example: JAMA_FIELD_VERIFICATION_METHOD=verification_method$243"
                    )
                elif resolution_source == "multiple_project_wide":
                    keys_str = ", ".join(sorted(all_keys))
                    raise ValueError(
                        f"Row has Verification Method populated, but multiple verification method field keys found in project:\n"
                        f"  {keys_str}\n\n"
                        f"No items of type {item_type} (itemType={item_type_id}) were found in the cache with verification method fields.\n"
                        f"The target Set may be empty or may not contain existing examples.\n\n"
                        f"Solution: Set JAMA_FIELD_VERIFICATION_METHOD in .env to the correct key.\n"
                        f"Example: JAMA_FIELD_VERIFICATION_METHOD=verification_method$243"
                    )
                elif resolution_source == "not_found" or resolution_source == "no_cache":
                    raise ValueError(
                        f"Row has Verification Method populated, but no verification method field keys found in cached Jama items.\n\n"
                        f"The script searched for fields starting with 'verification_method$' in cached items but found none.\n"
                        f"The target Set may be empty, or no existing project item exposes the verification method field.\n\n"
                        f"Solution: Either:\n"
                        f"  1. Ensure the project cache includes items with verification method fields (run with existing items in Jama)\n"
                        f"  2. Set JAMA_FIELD_VERIFICATION_METHOD in .env to the correct key\n"
                        f"     Example: JAMA_FIELD_VERIFICATION_METHOD=verification_method$243"
                    )
                else:
                    # Fallback error
                    raise ValueError(
                        f"Could not resolve verification method field key for {item_type} (itemType={item_type_id}).\n"
                        f"Resolution source: {resolution_source}\n"
                        f"Set JAMA_FIELD_VERIFICATION_METHOD in .env to the correct key."
                    )

            # Store for logging (extracted later).
            fields["_verification_method_resolved_key"] = verification_field_key
            fields["_verification_method_canonical"] = canonical_value
            fields["_verification_method_picklist_id"] = picklist_id
            fields["_verification_method_source"] = resolution_source

            # Verification Method uses a list of picklist option IDs, e.g. [422].
            fields[verification_field_key] = format_verification_method_value(picklist_id)

    return fields


def build_payload(
    row: pd.Series,
    parent_item_id: int,
    sort_order: int,
    is_update: bool = False,
    allow_move: bool = False,
    parent_metadata: Optional[Dict[str, Any]] = None,
    inferred_child_type: Optional[int] = None
) -> Dict[str, Any]:
    """
    Build payload for creating or updating a Jama item.

    Args:
        row: DataFrame row with item data
        parent_item_id: Parent Jama item ID
        sort_order: Sort order under parent
        is_update: True if updating existing item
        allow_move: True to include location in update (moves item)
        parent_metadata: Optional parent item metadata from Jama (includes childItemType)
        inferred_child_type: Optional inferred childItemType from lookahead (for folders)

    Returns:
        Payload dict for POST or PUT
    """
    item_type_name = row["Item Type"]

    if item_type_name not in ITEM_TYPE_IDS:
        raise ValueError(f"Unsupported Item Type: {item_type_name}")

    # Get item type ID for dynamic field resolution
    item_type_id = ITEM_TYPE_IDS[item_type_name]

    # For updates, only send fields by default
    if is_update:
        payload = {
            "fields": build_fields(row, item_type_id)
        }

        # Only include location if explicitly allowed (moves the item)
        if allow_move:
            payload["location"] = {
                "parent": {
                    "item": parent_item_id
                },
                "sortOrder": sort_order
            }

        return payload

    # For creates, send full payload
    payload = {
        "fields": build_fields(row, item_type_id),
        "itemType": item_type_id,
        "location": {
            "parent": {
                "item": parent_item_id
            },
            "sortOrder": sort_order
        }
    }

    # Jama requires childItemType when creating containers (Set, Folder, Segment, Subsystem).
    # childItemType represents what type of content the container holds, not the container type itself.
    # Leaf/content items (Requirements, Text) do not have childItemType but still require location.parent.item.
    # Priority: 1) Inherit from parent, 2) Infer from lookahead, 3) General fallback, 4) Folder-specific fallback
    if item_type_name in ("Set", "Folder"):
        child_type_source = None  # Track how childItemType was determined

        # Priority 1: Inherit from parent container (PREFERRED)
        inherited_child_type = None
        if parent_metadata:
            inherited_child_type = parent_metadata.get("childItemType")

        if inherited_child_type:
            payload["childItemType"] = inherited_child_type
            child_type_source = "parent"
        # Priority 2: Infer from next requirement row under this folder
        elif inferred_child_type:
            payload["childItemType"] = inferred_child_type
            child_type_source = "inference"
        # Priority 3: Use general DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE (import-level fallback)
        elif CONFIG.get("DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE"):
            payload["childItemType"] = CONFIG["DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE"]
            child_type_source = "default_requirement"
        # Priority 4: Use folder-specific JAMA_FOLDER_CHILD_ITEM_TYPE (legacy fallback)
        elif item_type_name in CHILD_ITEM_TYPE_IDS:
            payload["childItemType"] = CHILD_ITEM_TYPE_IDS[item_type_name]
            child_type_source = "fallback_folder"
        else:
            # Cannot determine childItemType - provide helpful error
            type_examples = []
            for name, type_id in ITEM_TYPE_IDS.items():
                if name in REQUIREMENT_ITEM_TYPES:
                    type_examples.append(f"  - {name}: {type_id}")

            type_examples_str = "\n".join(type_examples) if type_examples else "  - Check your Jama item type IDs"

            raise ValueError(
                f"Cannot determine childItemType for {item_type_name} '{row.get('Name', 'unknown')}'.\n\n"
                f"The script tried to:\n"
                f"  1. Inherit from parent container (no parent metadata or no childItemType)\n"
                f"  2. Infer from items under this folder (none found)\n"
                f"  3. Use DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE from .env (not configured)\n"
                f"  4. Use JAMA_FOLDER_CHILD_ITEM_TYPE from .env (not configured)\n\n"
                f"This usually means the folder is empty or at root level.\n\n"
                f"Solution 1 (Recommended): Ensure parent container has childItemType set\n\n"
                f"Solution 2: Add requirement items under this folder in Excel\n\n"
                f"Solution 3: Set DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE in .env for this import:\n"
                f"{type_examples_str}\n\n"
                f"Add to .env:\n"
                f"  DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=<type_id>\n"
            )

        # Store the source for logging later
        if child_type_source:
            payload["_child_type_source"] = child_type_source

    # Segment and Subsystem may optionally require childItemType depending on project configuration
    # Subsystem is an alias of Set, so it uses the same child type rules
    elif item_type_name in ("Segment", "Subsystem"):
        child_type_source = None  # Track how childItemType was determined

        # Priority 1: Inherit from parent container (PREFERRED)
        inherited_child_type = None
        if parent_metadata:
            inherited_child_type = parent_metadata.get("childItemType")

        if inherited_child_type:
            payload["childItemType"] = inherited_child_type
            child_type_source = "parent"
        # Priority 2: Infer from next requirement row under this container
        elif inferred_child_type:
            payload["childItemType"] = inferred_child_type
            child_type_source = "inference"
        # Priority 3: Use general DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE (import-level fallback)
        elif CONFIG.get("DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE"):
            payload["childItemType"] = CONFIG["DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE"]
            child_type_source = "default_requirement"
        # Priority 4: Use container-specific fallback (legacy)
        elif item_type_name in CHILD_ITEM_TYPE_IDS:
            payload["childItemType"] = CHILD_ITEM_TYPE_IDS[item_type_name]
            child_type_source = "fallback_specific"
        # else: No childItemType determined, will be caught by validation below if required

        # Store the source for logging later
        if child_type_source:
            payload["_child_type_source"] = child_type_source

    return payload


def validate_container_child_item_type(row: pd.Series, payload: Dict[str, Any]) -> None:
    """
    Validate that container payloads have childItemType set.

    Args:
        row: DataFrame row
        payload: POST payload

    Raises:
        ValueError: If container is missing childItemType
    """
    item_type_name = row["Item Type"]
    if item_type_name in ("Set", "Folder", "Subsystem"):
        child_type = payload.get("childItemType")
        if not child_type:
            # Provide helpful error with type IDs
            env_var_name = f"JAMA_{item_type_name.upper().replace(' ', '_')}_CHILD_ITEM_TYPE"
            type_examples = []
            for name, type_id in ITEM_TYPE_IDS.items():
                if name in REQUIREMENT_ITEM_TYPES:
                    type_examples.append(f"  - {name}: {type_id}")

            type_examples_str = "\n".join(type_examples) if type_examples else "  - Check your Jama item type IDs"

            raise ValueError(
                f"Cannot determine childItemType for {item_type_name} '{row.get('Name', 'unknown')}'.\n\n"
                f"The script tried to:\n"
                f"  1. Inherit from parent container (no parent metadata or no childItemType)\n"
                f"  2. Infer from items under this folder (none found)\n"
                f"  3. Use DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE from .env (not configured)\n"
                f"  4. Use {env_var_name} from .env (not configured)\n\n"
                f"This usually means the folder is empty or at root level.\n\n"
                f"Solution 1 (Recommended): Ensure parent container has childItemType set\n\n"
                f"Solution 2: Add requirement items under this folder in Excel\n\n"
                f"Solution 3: Set DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE in .env for this import:\n"
                f"{type_examples_str}\n\n"
                f"Add to .env:\n"
                f"  DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=<type_id>\n"
            )


def validate_parent_compatibility(
    row: pd.Series,
    payload: Dict[str, Any],
    parent_item_id: int,
    parent_metadata: Optional[Dict[str, Any]]
) -> None:
    """
    Validate that new item is compatible with parent container's childItemType.

    Args:
        row: DataFrame row
        payload: POST payload
        parent_item_id: Parent Jama item ID
        parent_metadata: Parent item metadata from Jama

    Raises:
        ValueError: If item type incompatible with parent childItemType
    """
    if not parent_metadata:
        # No metadata available - cannot validate
        return

    item_type_name = row["Item Type"]
    new_item_type = payload.get("itemType")
    parent_child_type = parent_metadata.get("childItemType")

    if not parent_child_type:
        # Parent doesn't have childItemType restriction
        return

    # For non-container rows (requirements and Text), validate compatibility
    if item_type_name not in ("Set", "Folder", "Segment", "Subsystem"):
        # This is a requirement or Text item (leaf/content node with parent but no childItemType)

        # Skip strict childItemType validation for Text items
        # Text items need location.parent.item but not parent.childItemType == 33
        # Let Jama API accept/reject Text placement based on document tree rules
        if item_type_name in ("Text", "Text Document"):
            print(f"[INFO] Text item: no childItemType, but location.parent.item is required (itemType={new_item_type})")
            return

        # Strict validation for requirement rows only
        # Requirements must match parent.childItemType exactly
        if new_item_type != parent_child_type:
            parent_doc_key = parent_metadata.get("documentKey", "unknown")
            parent_name = parent_metadata.get("fields", {}).get("name", "unknown")
            parent_item_type = parent_metadata.get("itemType", "unknown")

            raise ValueError(
                f"Cannot create {item_type_name} (itemType={new_item_type}) under parent item {parent_item_id}.\n"
                f"Parent documentKey: {parent_doc_key}\n"
                f"Parent name: {parent_name}\n"
                f"Parent itemType: {parent_item_type}\n"
                f"Parent childItemType: {parent_child_type}\n"
                f"Expected new itemType to match parent childItemType ({parent_child_type}), but got {new_item_type}.\n"
                f"This row is routed to the wrong folder/container."
            )

    # For container rows, validate childItemType matches parent's childItemType
    else:
        new_child_type = payload.get("childItemType")
        if new_child_type and new_child_type != parent_child_type:
            parent_doc_key = parent_metadata.get("documentKey", "unknown")
            parent_name = parent_metadata.get("fields", {}).get("name", "unknown")

            raise ValueError(
                f"Cannot create {item_type_name} with childItemType={new_child_type} under parent item {parent_item_id}.\n"
                f"Parent documentKey: {parent_doc_key}\n"
                f"Parent name: {parent_name}\n"
                f"Parent childItemType: {parent_child_type}\n"
                f"New container childItemType should match parent ({parent_child_type}), but got {new_child_type}.\n"
                f"This creates incompatible nesting in Jama hierarchy."
            )


# ============================================================
# IMPORT REPORTING
# ============================================================

def write_import_results_csv(results: list, path: str) -> None:
    if not results:
        return

    fieldnames = IMPORT_RESULTS_CSV_FIELDNAMES

    with open(path, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            writer.writerow({
                "excel_row": result.get("excel_row", ""),
                "action": result.get("action", ""),
                "status": result.get("status", ""),
                "jama_id": result.get("jama_id", ""),
                "document_key": result.get("document_key", ""),
                "global_id": result.get("global_id", ""),
                "source_id": result.get("source_id", ""),
                "item_type": result.get("item_type", ""),
                "name": result.get("name", ""),
                "resolved_by": result.get("resolved_by", ""),
                "section_number": result.get("section_number", ""),
                "parent_section_number": result.get("parent_section_number", ""),
                "parent_item_id": result.get("parent_item_id", ""),
                "created_item_id": result.get("created_item_id", ""),
                "updated_item_id": result.get("updated_item_id", ""),
                "current_parent_item_id": result.get("current_parent_item_id", ""),
                "desired_parent_item_id": result.get("desired_parent_item_id", ""),
                "moved": result.get("moved", ""),
                "move_method": result.get("move_method", ""),
                "error": result.get("error", "")
            })


# ============================================================
# MAIN IMPORT LOGIC
# ============================================================

def infer_folder_child_item_type(df: pd.DataFrame, folder_row_pos: int) -> Optional[int]:
    """
    Infer the childItemType needed for a folder by looking at the next items that will go under it.

    Args:
        df: DataFrame with all rows
        folder_row_pos: Positional index (0-based) of the folder row in the DataFrame

    Returns:
        Item type ID that should be the childItemType, or None if cannot determine
    """
    # Bounds check
    if folder_row_pos < 0 or folder_row_pos >= len(df):
        return None

    folder_row = df.iloc[folder_row_pos]
    folder_name = folder_row["Name"]
    folder_section = extract_section_number(folder_name)

    # Look at subsequent rows to find the first requirement item under this folder
    # Note: Text items should NOT determine folder childItemType - skip them
    for next_pos in range(folder_row_pos + 1, len(df)):
        next_row = df.iloc[next_pos]
        next_type = next_row["Item Type"]
        next_name = next_row["Name"]

        # If we hit another container, check if it's a child or sibling
        if next_type in ("Set", "Folder", "Segment", "Subsystem"):
            next_section = extract_section_number(next_name)
            if next_section and folder_section:
                # If next section is not a child of current folder, stop looking
                norm_next = normalize_top_level_section(next_section)
                parent_of_next = get_parent_section_number(norm_next)
                norm_folder = normalize_top_level_section(folder_section)

                if parent_of_next != norm_folder:
                    # This container is not a direct child, stop
                    break
            # Continue - this is a child container, keep looking for requirement items
            continue

        # Skip Text items - they don't determine folder childItemType
        if next_type in ("Text", "Text Document"):
            continue

        # Found a requirement item - this is what the folder should contain
        if next_type in REQUIREMENT_ITEM_TYPES:
            return ITEM_TYPE_IDS[next_type]

    # No clear requirement items found, return None
    return None


def import_excel(mode: str = "upsert", dry_run: bool = True) -> None:
    """
    Import items from Excel to Jama.

    Args:
        mode: Import mode - "create" or "upsert"
        dry_run: If True, simulate without making API calls
    """
    df = load_excel(EXCEL_FILE)

    print(f"[INFO] Loaded {len(df)} rows from Excel.")
    print(f"[INFO] Import mode: {mode}")
    print(f"[INFO] Execution mode: {'DRY RUN' if dry_run else 'EXECUTE'}")

    # Validate all item types before starting
    validate_item_types(df)

    # Fetch ROOT_PARENT_ITEM_ID metadata before processing rows
    # This allows folders created under root to inherit root's childItemType
    if not dry_run and ROOT_PARENT_ITEM_ID not in _item_metadata_by_id:
        print(f"[INFO] Fetching root parent item metadata (ID: {ROOT_PARENT_ITEM_ID})...")
        try:
            root_response = jama_get(f"/items/{ROOT_PARENT_ITEM_ID}")
            root_item = root_response.get("data")
            if root_item:
                store_item_metadata(ROOT_PARENT_ITEM_ID, root_item)
                root_child_type = root_item.get("childItemType")
                if root_child_type:
                    print(f"[INFO] Root parent childItemType: {root_child_type}")
                else:
                    print(f"[INFO] Root parent has no childItemType set")
        except Exception as e:
            print(f"[WARN] Could not fetch root parent metadata: {e}")
            print(f"[WARN] Folder childItemType will use inference or fallback")

    # Maps section numbers to created Jama folder IDs.
    #
    # Example:
    #   "1.0"   -> Jama item ID for Section 1.0
    #   "1.1"   -> Jama item ID for Section 1.1
    #   "1.1.1" -> Jama item ID for Section 1.1.1
    folder_by_section: Dict[str, int] = {}

    # Most recently active folder.
    # Requirements go under this folder.
    # Unnumbered folders also go under this folder.
    current_folder_item_id = ROOT_PARENT_ITEM_ID

    # Used for dry-run fake IDs.
    dry_run_id_counter = DRY_RUN_ID_START

    # Keeps sibling order by parent item ID.
    sort_order_by_parent: Dict[int, int] = {}

    results = []

    # Use enumerate to get true positional indices (0-based)
    # row_pos is the 0-based position in the DataFrame
    # row_index is the DataFrame index label (may not be sequential)
    for row_pos, (row_index, row) in enumerate(df.iterrows()):
        excel_row_number = row_pos + 2  # +2 because Excel row 1 is headers, DataFrame is 0-based

        item_type = row["Item Type"]
        name = row["Name"]
        excel_id = row["ID"]
        jama_id_str = row.get("Jama ID", "").strip()
        document_key = row.get("Document Key", "").strip()
        global_id = row.get("Global ID", "").strip()
        description = row.get("Description", "").strip()

        # Derive item_type_id from item_type for verification method and other uses
        if item_type not in ITEM_TYPE_IDS:
            raise ValueError(f"Unsupported Item Type: {item_type}")
        item_type_id = ITEM_TYPE_IDS[item_type]

        section_number = None
        parent_section_number = None
        parent_item_id = None
        created_item_id = None
        updated_item_id = None
        action = None
        final_jama_id = None

        try:
            # Validate that requirement rows have descriptions
            if requires_description(item_type) and not description:
                raise ValueError(
                    f"Row {excel_row_number} is a {item_type} and requires Description."
                )

            # Parse and validate Jama ID if present
            existing_jama_id = None
            if jama_id_str:
                try:
                    existing_jama_id = int(jama_id_str)
                except ValueError:
                    raise ValueError(f"Invalid Jama ID: '{jama_id_str}' must be an integer")

            # Track how this item was resolved
            resolved_by = "none"

            # Track if this item already exists in Jama
            existing_item_metadata = None
            current_parent_item_id = None

            # Try to find existing item by Jama ID or documentKey
            if existing_jama_id:
                existing_item_metadata = get_item_metadata(existing_jama_id)
                if not existing_item_metadata:
                    # Try to fetch from API if not in cache
                    try:
                        existing_item_metadata = jama_get(f"/items/{existing_jama_id}").get("data")
                        if existing_item_metadata:
                            store_item_metadata(existing_jama_id, existing_item_metadata)
                    except:
                        pass  # Item may not exist yet

            # Try Global ID lookup for all item types if configured
            if not existing_jama_id and CONFIG.get("USE_GLOBAL_ID_LOOKUP", True):
                global_id_raw = row.get("Global ID", "").strip()
                global_id_value = extract_global_id_from_value(global_id_raw, warn_if_unparseable=True) if global_id_raw else None

                if global_id_value:
                    try:
                        existing_item_metadata = find_existing_item_by_global_id(global_id_value)
                        if existing_item_metadata:
                            # Validate item type matches
                            validate_item_type_match(existing_item_metadata, item_type, global_id_value)

                            existing_jama_id = existing_item_metadata.get("id")
                            resolved_by = "global_id"
                            print(f"[INFO] Resolved existing {item_type} by Global ID {global_id_value} -> Jama ID {existing_jama_id}")
                            store_item_metadata(existing_jama_id, existing_item_metadata)
                    except ValueError as e:
                        # Item type mismatch or duplicate - fail the row
                        raise e

            # Try Document Key lookup if still not found
            if not existing_jama_id and document_key:
                # Try to find by documentKey
                existing_item_metadata = find_existing_item_by_document_key(document_key)
                if existing_item_metadata:
                    existing_jama_id = existing_item_metadata.get("id")

            # Get current parent if item exists
            if existing_item_metadata:
                current_parent_item_id = get_current_parent_id(existing_item_metadata)

            # Determine action based on mode and Jama ID presence
            if mode == "create":
                if existing_jama_id:
                    raise ValueError(f"Mode is 'create' but Jama ID is populated: {existing_jama_id}. Remove Jama ID for create mode.")
                action = "CREATE"
            elif mode == "upsert":
                if existing_jama_id:
                    # Container rows: resolve and register as parent
                    if item_type in ("Set", "Folder", "Segment", "Subsystem"):
                        action = "RESOLVE"
                    else:
                        # Requirement rows: check if needs move, otherwise skip
                        action = "SKIP"
                else:
                    action = "CREATE"

            final_jama_id = existing_jama_id

            if existing_jama_id:
                resolved_by = "jama_id"

            # For Folder rows: simple resolution by documentKey if Jama ID not provided
            # Priority: A) Jama ID (done above), B) Global ID, C) Document Key column, D) Excel ID as documentKey
            if item_type == "Folder" and not existing_jama_id:
                found_folder = None
                resolution_method = None

                print(f"[INFO] Folder row - attempting to resolve existing folder:")
                print(f"[INFO]   Excel ID: {excel_id}")
                print(f"[INFO]   Folder Name: {name}")

                # B) Try Global ID lookup (if configured and populated)
                if CONFIG.get("USE_GLOBAL_ID_LOOKUP", True):
                    global_id_raw = row.get("Global ID", "").strip()
                    global_id_extracted = extract_global_id_from_value(global_id_raw, warn_if_unparseable=True) if global_id_raw else None

                    if global_id_extracted:
                        print(f"[INFO] Attempting to resolve folder by Global ID: {global_id_extracted}")

                        try:
                            found_folder = find_existing_item_by_global_id(global_id_extracted)

                            if found_folder:
                                # Validate item type
                                validate_item_type_match(found_folder, item_type, global_id_extracted)

                                # Determine expected childItemType (reuse logic from documentKey resolution)
                                expected_child_type = None

                                # Priority 1: Try to inherit from parent
                                temp_parent_id = None
                                raw_section_number = extract_section_number(name)

                                if raw_section_number:
                                    temp_section_number = normalize_top_level_section(raw_section_number)
                                    temp_parent_section_number = get_parent_section_number(temp_section_number)

                                    if temp_parent_section_number:
                                        temp_parent_id = folder_by_section.get(temp_parent_section_number, current_folder_item_id)
                                    else:
                                        temp_parent_id = ROOT_PARENT_ITEM_ID
                                else:
                                    temp_parent_id = current_folder_item_id

                                temp_parent_metadata = get_item_metadata(temp_parent_id) if temp_parent_id else None
                                if temp_parent_metadata:
                                    expected_child_type = temp_parent_metadata.get("childItemType")

                                # Priority 2: Infer from items under this folder
                                if not expected_child_type:
                                    inferred_child_type = infer_folder_child_item_type(df, row_pos)
                                    expected_child_type = inferred_child_type

                                # Priority 3: Use DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE (general fallback)
                                if not expected_child_type:
                                    expected_child_type = CONFIG.get("DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE")

                                # Priority 4: Use folder-specific fallback
                                if not expected_child_type:
                                    expected_child_type = CHILD_ITEM_TYPE_IDS.get(item_type)

                                # Validate childItemType compatibility - raises ValueError if incompatible
                                validate_folder_child_item_type_compatibility(
                                    found_folder, expected_child_type, name, "Global ID"
                                )

                                # Compatible - resolve to this folder
                                final_jama_id = found_folder["id"]
                                existing_jama_id = final_jama_id
                                action = "RESOLVE"
                                resolved_by = "global_id"

                                # Capture metadata
                                if not document_key:
                                    document_key = found_folder.get("documentKey", "")
                                if not global_id:
                                    global_id = found_folder.get("globalId", "")

                                print(f"[INFO] ✓ Resolved existing folder by Global ID {global_id_extracted} -> Jama ID {final_jama_id}, documentKey {document_key}")
                                print(f"[INFO] Registered as current parent. No folder will be created.")

                                store_item_metadata(final_jama_id, found_folder)
                                resolution_method = "global_id"
                            else:
                                print(f"[INFO] ✗ Global ID {global_id_extracted} not found in project cache. Falling back to Document Key lookup.")

                        except (RuntimeError, ValueError) as lookup_error:
                            raise lookup_error

                # C) Try explicit Document Key column (if populated)
                if not found_folder and document_key:
                    print(f"[INFO] Attempting to resolve folder by Document Key column: {document_key}")
                    found_folder = find_existing_folder_by_document_key(document_key)
                    if found_folder:
                        resolution_method = "document_key_column"
                        print(f"[INFO] ✓ Found by Document Key column")
                    else:
                        print(f"[INFO] ✗ Not found by Document Key column")

                # C) Try Excel ID as documentKey (default behavior for Folder rows)
                if not found_folder and CONFIG.get("RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY", True) and CONFIG.get("USE_EXCEL_ID_AS_DOCUMENT_KEY", True):
                    print(f"[INFO] Attempting to resolve folder by documentKey from Excel ID: {excel_id}")

                    found_folder = find_existing_folder_by_document_key(excel_id)

                    if found_folder:
                        resolution_method = "document_key"
                        print(f"[INFO] ✓ Found by Excel ID as documentKey")
                    else:
                        print(f"[INFO] ✗ Not found in Jama by documentKey '{excel_id}'")

                # Process found folder
                if found_folder and resolution_method != "global_id":
                    try:
                        # Found a folder with matching documentKey
                        # Now check if its childItemType is compatible with what we need

                        # Determine expected childItemType
                        # Priority: 1) Inherit from parent, 2) Infer from contents, 3) Default from config
                        expected_child_type = None

                        # Priority 1: Try to inherit from parent
                        temp_parent_id = None
                        raw_section_number = extract_section_number(name)

                        if raw_section_number:
                            temp_section_number = normalize_top_level_section(raw_section_number)
                            temp_parent_section_number = get_parent_section_number(temp_section_number)

                            if temp_parent_section_number:
                                temp_parent_id = folder_by_section.get(temp_parent_section_number, current_folder_item_id)
                            else:
                                temp_parent_id = ROOT_PARENT_ITEM_ID
                        else:
                            temp_parent_id = current_folder_item_id

                        temp_parent_metadata = get_item_metadata(temp_parent_id) if temp_parent_id else None
                        if temp_parent_metadata:
                            expected_child_type = temp_parent_metadata.get("childItemType")

                        # Priority 2: Infer from items under this folder
                        if not expected_child_type:
                            inferred_child_type = infer_folder_child_item_type(df, row_pos)
                            expected_child_type = inferred_child_type

                        # Priority 3: Use DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE (general fallback)
                        if not expected_child_type:
                            expected_child_type = CONFIG.get("DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE")

                        # Priority 4: Use folder-specific fallback
                        if not expected_child_type:
                            expected_child_type = CHILD_ITEM_TYPE_IDS.get(item_type)

                        # Validate childItemType compatibility - raises ValueError if incompatible
                        validate_folder_child_item_type_compatibility(
                            found_folder, expected_child_type, name, "documentKey"
                        )

                        # childItemType compatible or not specified - resolve the folder
                        final_jama_id = found_folder["id"]
                        existing_jama_id = final_jama_id
                        action = "RESOLVE"
                        resolved_by = resolution_method

                        # Capture metadata from found folder
                        if not document_key:
                            document_key = found_folder.get("documentKey", "")
                        if not global_id:
                            global_id = found_folder.get("globalId", "")

                        method_desc = "Document Key column" if resolution_method == "document_key_column" else "documentKey"
                        print(f"[INFO] Resolved existing folder by {method_desc} '{excel_id}' -> Jama ID {final_jama_id}")
                        if expected_child_type:
                            existing_child_type = found_folder.get("childItemType")
                            print(f"[INFO] Existing folder childItemType: {existing_child_type} matches expected: {expected_child_type} (compatible)")
                        print(f"[INFO] Registered as current parent. No folder will be created.")

                        # Store metadata for resolved folder
                        store_item_metadata(final_jama_id, found_folder)

                    except (RuntimeError, ValueError) as lookup_error:
                        # Re-raise lookup errors so the row fails with the detailed error message
                        raise lookup_error

                # E) Try parent+itemType+name matching (pre-POST duplicate prevention)
                if not found_folder and CONFIG.get("ENABLE_PRE_POST_DUPLICATE_CHECK", True):
                    # Determine parent and expected childItemType for matching
                    temp_parent_id = None
                    raw_section_number = extract_section_number(name)

                    if raw_section_number:
                        temp_section_number = normalize_top_level_section(raw_section_number)
                        temp_parent_section_number = get_parent_section_number(temp_section_number)

                        if temp_parent_section_number:
                            temp_parent_id = folder_by_section.get(temp_parent_section_number, current_folder_item_id)
                        else:
                            temp_parent_id = ROOT_PARENT_ITEM_ID
                    else:
                        temp_parent_id = current_folder_item_id

                    if temp_parent_id:
                        print(f"[INFO] Attempting to resolve folder by parent+itemType+name matching: parent={temp_parent_id}, name='{name}'")

                        # Determine expected childItemType for matching
                        expected_child_type = None
                        temp_parent_metadata = get_item_metadata(temp_parent_id) if temp_parent_id else None
                        if temp_parent_metadata:
                            expected_child_type = temp_parent_metadata.get("childItemType")
                        if not expected_child_type:
                            inferred_child_type = infer_folder_child_item_type(df, row_pos)
                            expected_child_type = inferred_child_type
                        if not expected_child_type:
                            expected_child_type = CONFIG.get("DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE")
                        if not expected_child_type:
                            expected_child_type = CHILD_ITEM_TYPE_IDS.get(item_type)

                        try:
                            found_folder = find_existing_item_by_parent_type_name(
                                parent_item_id=temp_parent_id,
                                item_type_id=ITEM_TYPE_IDS[item_type],
                                name=name,
                                child_item_type=expected_child_type
                            )

                            if found_folder:
                                resolution_method = "parent_type_name"
                                print(f"[INFO] ✓ Found by parent+itemType+name matching")
                            else:
                                print(f"[INFO] ✗ Not found by parent+itemType+name matching")
                        except ValueError as e:
                            # Multiple matches - fail the row
                            raise e

                # Process found folder (parent_type_name match)
                if found_folder and resolution_method == "parent_type_name":
                    try:
                        # Found a folder with matching parent+type+name
                        # Validate childItemType compatibility
                        expected_child_type = None

                        # Priority 1: Try to inherit from parent
                        temp_parent_id = None
                        raw_section_number = extract_section_number(name)

                        if raw_section_number:
                            temp_section_number = normalize_top_level_section(raw_section_number)
                            temp_parent_section_number = get_parent_section_number(temp_section_number)

                            if temp_parent_section_number:
                                temp_parent_id = folder_by_section.get(temp_parent_section_number, current_folder_item_id)
                            else:
                                temp_parent_id = ROOT_PARENT_ITEM_ID
                        else:
                            temp_parent_id = current_folder_item_id

                        temp_parent_metadata = get_item_metadata(temp_parent_id) if temp_parent_id else None
                        if temp_parent_metadata:
                            expected_child_type = temp_parent_metadata.get("childItemType")

                        # Priority 2: Infer from items under this folder
                        if not expected_child_type:
                            inferred_child_type = infer_folder_child_item_type(df, row_pos)
                            expected_child_type = inferred_child_type

                        # Priority 3: Use DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE (general fallback)
                        if not expected_child_type:
                            expected_child_type = CONFIG.get("DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE")

                        # Priority 4: Use folder-specific fallback
                        if not expected_child_type:
                            expected_child_type = CHILD_ITEM_TYPE_IDS.get(item_type)

                        # Validate childItemType compatibility - raises ValueError if incompatible
                        validate_folder_child_item_type_compatibility(
                            found_folder, expected_child_type, name, "parent+itemType+name"
                        )

                        # childItemType compatible or not specified - resolve the folder
                        final_jama_id = found_folder["id"]
                        existing_jama_id = final_jama_id
                        action = "RESOLVE"
                        resolved_by = resolution_method

                        # Capture metadata from found folder
                        if not document_key:
                            document_key = found_folder.get("documentKey", "")
                        if not global_id:
                            global_id = found_folder.get("globalId", "")

                        print(f"[INFO] Resolved existing folder by parent+itemType+name -> Jama ID {final_jama_id}")
                        if expected_child_type:
                            existing_child_type = found_folder.get("childItemType")
                            print(f"[INFO] Existing folder childItemType: {existing_child_type} matches expected: {expected_child_type} (compatible)")
                        print(f"[INFO] Registered as current parent. No folder will be created.")

                        # Store metadata for resolved folder
                        store_item_metadata(final_jama_id, found_folder)

                    except (RuntimeError, ValueError) as lookup_error:
                        # Re-raise lookup errors so the row fails with the detailed error message
                        raise lookup_error

                elif not CONFIG.get("CREATE_MISSING_FOLDERS", False):
                    # Not found and create is disabled
                    raise ValueError(
                        f"Folder documentKey '{excel_id}' was not found in Jama.\n"
                        f"Folder name: {name}\n"
                        f"CREATE_MISSING_FOLDERS=false, so no duplicate folder will be created.\n"
                        f"Solution:\n"
                        f"  1. Verify Excel ID matches the actual Jama documentKey for this folder\n"
                        f"  2. Or provide the Jama ID in 'Jama ID' column in Excel\n"
                        f"  3. Or set CREATE_MISSING_FOLDERS=true to create new folders"
                    )
                else:
                    # CREATE_MISSING_FOLDERS=true, will create the folder
                    print(f"[INFO] Folder documentKey '{excel_id}' was not found in Jama after lookup.")
                    print(f"[INFO] CREATE_MISSING_FOLDERS=true, so a new folder will be created.")
                    if not dry_run:
                        print(f"[INFO] If this folder already exists with a different documentKey, this may create a DUPLICATE.")

            # Determine parent and section hierarchy
            if item_type in ("Set", "Folder", "Segment", "Subsystem"):
                raw_section_number = extract_section_number(name)

                if raw_section_number:
                    section_number = normalize_top_level_section(raw_section_number)
                    print(f"[INFO] Detected section: raw='{raw_section_number}' normalized='{section_number}'")
                    parent_section_number = get_parent_section_number(section_number)

                    if parent_section_number:
                        if parent_section_number not in folder_by_section:
                            raise ValueError(
                                f"Could not find parent section '{parent_section_number}' "
                                f"for {item_type.lower()} '{section_number}' / '{name}'. "
                                f"Make sure the parent container appears earlier in the Excel file."
                            )

                        parent_item_id = folder_by_section[parent_section_number]
                    else:
                        # Top-level section (no parent section number)
                        # Always use ROOT_PARENT_ITEM_ID for top-level sections
                        parent_item_id = ROOT_PARENT_ITEM_ID

                else:
                    parent_item_id = current_folder_item_id

            else:
                # Requirement row
                parent_item_id = current_folder_item_id

            sort_order = sort_order_by_parent.get(parent_item_id, 0)

            # Get parent metadata for dynamic childItemType resolution
            parent_metadata = get_item_metadata(parent_item_id)

            # Check if existing item needs to be moved to different parent
            needs_move = False
            if existing_jama_id and current_parent_item_id is not None and current_parent_item_id != parent_item_id:
                needs_move = True
                if action == "SKIP":
                    # Change action from SKIP to MOVE if move is allowed
                    if allow_move:
                        action = "MOVE"
                    else:
                        # Keep as SKIP but record that move is needed
                        action = "SKIP_NEEDS_MOVE"

            # Infer childItemType for folder/container creation by looking ahead
            inferred_child_type = None
            if action == "CREATE" and item_type in ("Set", "Folder", "Segment", "Subsystem"):
                inferred_child_type = infer_folder_child_item_type(df, row_pos)
                if inferred_child_type:
                    inferred_type_name = next((k for k, v in ITEM_TYPE_IDS.items() if v == inferred_child_type), str(inferred_child_type))
                    print(f"[INFO] Inferred childItemType for new {item_type}: {inferred_child_type} ({inferred_type_name})")

            # Build payload (only for CREATE actions, not for RESOLVE or SKIP)
            payload = None
            if action == "CREATE":
                payload = build_payload(
                    row=row,
                    parent_item_id=parent_item_id,
                    sort_order=sort_order,
                    is_update=False,
                    allow_move=False,
                    parent_metadata=parent_metadata,
                    inferred_child_type=inferred_child_type
                )

            print("\n" + "=" * 80)
            print(f"[ROW {excel_row_number}] {action} {item_type}: {name}")

            # Log how childItemType was determined for containers
            if action == "CREATE" and payload and item_type in ("Set", "Folder", "Segment", "Subsystem"):
                child_type_source = payload.get("_child_type_source")
                child_type_value = payload.get("childItemType")
                if child_type_source and child_type_value:
                    if child_type_source == "parent":
                        print(f"[INFO] Folder childItemType resolved from parent metadata: {child_type_value}")
                    elif child_type_source == "inference":
                        inferred_type_name = next((k for k, v in ITEM_TYPE_IDS.items() if v == child_type_value), str(child_type_value))
                        print(f"[INFO] Folder childItemType inferred from next requirement row: {child_type_value} ({inferred_type_name})")
                    elif child_type_source == "default_requirement":
                        print(f"[INFO] Folder childItemType using DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE fallback: {child_type_value}")
                    elif child_type_source == "fallback_folder":
                        print(f"[INFO] Folder childItemType using JAMA_FOLDER_CHILD_ITEM_TYPE fallback: {child_type_value}")
                    elif child_type_source == "fallback_specific":
                        print(f"[INFO] Folder childItemType using container-specific fallback: {child_type_value}")
                # Remove internal tracking field before sending to API
                if "_child_type_source" in payload:
                    del payload["_child_type_source"]
            if existing_jama_id:
                if resolved_by == "document_key":
                    print(f"[INFO] Resolved existing folder by documentKey '{excel_id}' -> Jama ID: {existing_jama_id}")
                else:
                    print(f"[INFO] Existing Jama ID: {existing_jama_id}")

            # Show Text item detection
            if item_type in ("Text", "Text Document"):
                print(f"[INFO] Detected Text item from Excel Item Type column")

            # Show verification method if present (extract from payload fields)
            if action == "CREATE" and payload and item_type in REQUIREMENT_ITEM_TYPES:
                payload_fields = payload.get("fields", {})
                if "_verification_method_canonical" in payload_fields:
                    excel_value = row.get("Verification Method", "").strip()
                    canonical_value = payload_fields.get("_verification_method_canonical")
                    picklist_id = payload_fields.get("_verification_method_picklist_id")
                    resolved_key = payload_fields.get("_verification_method_resolved_key")
                    resolution_source = payload_fields.get("_verification_method_source")

                    print(f"[INFO] Verification Method: {excel_value} -> {canonical_value} -> {picklist_id}")

                    # Show how field key was resolved
                    if resolution_source == "env_explicit":
                        print(f"[INFO] Verification field key from .env (explicit): {resolved_key}")
                    elif resolution_source == "type_specific":
                        # Show dynamic resolution from same item type
                        type_specific_keys = collect_verification_method_field_keys_from_cached_items(item_type_id)
                        candidates_str = ", ".join(sorted(type_specific_keys))
                        print(f"[INFO] Verification field key candidates for itemType={item_type_id}: {candidates_str}")
                        print(f"[INFO] Verification field key resolved dynamically (type-specific): {resolved_key}")
                    elif resolution_source == "project_wide":
                        # Show dynamic resolution from project-wide search with warning
                        all_keys = collect_verification_method_field_keys_from_cached_items()
                        candidates_str = ", ".join(sorted(all_keys))
                        print(f"[WARN] No same-itemType verification field found for itemType={item_type_id}")
                        print(f"[WARN] Using only project-wide candidate: {resolved_key}")
                        print(f"[INFO] Project-wide verification field key candidates: {candidates_str}")
                    elif resolution_source == "env_base_fallback":
                        print(f"[WARN] No cached verification fields found, using .env base name with item type suffix")
                        print(f"[INFO] Verification field key: {resolved_key}")
                    else:
                        # Other sources
                        print(f"[INFO] Verification field key resolved ({resolution_source}): {resolved_key}")

                    print(f"[INFO] Verification payload value: [{picklist_id}]")

                    # Remove internal tracking fields before API call
                    payload_fields.pop("_verification_method_canonical", None)
                    payload_fields.pop("_verification_method_picklist_id", None)
                    payload_fields.pop("_verification_method_resolved_key", None)
                    payload_fields.pop("_verification_method_source", None)

            # Print parent metadata for diagnostics
            print(f"[INFO] Parent item ID: {parent_item_id}")
            if parent_metadata:
                parent_doc_key = parent_metadata.get("documentKey", "unknown")
                parent_name = parent_metadata.get("fields", {}).get("name", "unknown")
                parent_item_type = parent_metadata.get("itemType", "unknown")
                parent_child_type = parent_metadata.get("childItemType")
                print(f"[INFO] Parent documentKey: {parent_doc_key}")
                print(f"[INFO] Parent name: {parent_name}")
                print(f"[INFO] Parent itemType: {parent_item_type}")
                if parent_child_type:
                    print(f"[INFO] Parent childItemType: {parent_child_type} (parent accepts this content type)")

            if section_number:
                print(f"[INFO] Section number: {section_number}")

            if parent_section_number:
                print(f"[INFO] Parent section number: {parent_section_number}")

            # Dry run or execute
            if dry_run:
                if action == "CREATE":
                    # Validate container has childItemType
                    if item_type in ("Set", "Folder", "Subsystem"):
                        validate_container_child_item_type(row, payload)

                    # Validate compatibility with parent
                    validate_parent_compatibility(row, payload, parent_item_id, parent_metadata)

                    # Show field keys for validation
                    fields = payload.get("fields", {})
                    print(f"[DEBUG] POST fields keys: {list(fields.keys())}")

                    # Warn if 'name' field is missing
                    if "name" not in fields:
                        print("[WARN] POST fields does not contain literal 'name'. Jama requires fields.name.")

                    # Show itemType and childItemType
                    new_item_type = payload.get("itemType")
                    new_child_type = payload.get("childItemType")
                    print(f"[INFO] New itemType: {new_item_type}")
                    if new_child_type:
                        print(f"[INFO] New childItemType: {new_child_type} (new container will accept this content type)")

                    # Show compatibility for requirements
                    if item_type not in ("Set", "Folder", "Segment", "Subsystem") and parent_metadata:
                        parent_child_type = parent_metadata.get("childItemType")
                        if parent_child_type:
                            match_status = "✓ MATCH" if new_item_type == parent_child_type else "✗ MISMATCH"
                            print(f"[INFO] Compatibility check: requirement itemType={new_item_type} vs parent accepts childItemType={parent_child_type} → {match_status}")

                    print("[DRY RUN] Would POST:")
                    print(json.dumps(payload, indent=2))
                    dry_run_id_counter += 1
                    final_jama_id = dry_run_id_counter
                    created_item_id = final_jama_id
                elif action == "RESOLVE":
                    print(f"[DRY RUN] Resolved folder by documentKey {excel_id} -> Jama ID {existing_jama_id}")
                    print(f"[DRY RUN] Registered as current parent. No folder will be created.")
                    final_jama_id = existing_jama_id
                elif action == "SKIP":
                    print(f"[DRY RUN] SKIP: Existing {item_type} has Jama ID {existing_jama_id}")
                    if not needs_move:
                        print(f"[DRY RUN] Item is already in correct location. No action needed.")
                    final_jama_id = existing_jama_id
                elif action == "SKIP_NEEDS_MOVE":
                    print(f"[DRY RUN] SKIP: Existing {item_type} has Jama ID {existing_jama_id}")
                    print(f"[WARN] Item is under parent {current_parent_item_id}, but should be under {parent_item_id}")
                    print(f"[WARN] Enable --allow-move to move this item to the correct parent")
                    final_jama_id = existing_jama_id
                elif action == "MOVE":
                    # Validate compatibility with target parent before move
                    new_item_type = ITEM_TYPE_IDS.get(item_type)
                    if new_item_type and parent_metadata:
                        parent_child_type = parent_metadata.get("childItemType")
                        if parent_child_type and new_item_type != parent_child_type:
                            raise ValueError(
                                f"Cannot move {item_type} (itemType={new_item_type}) to parent {parent_item_id}.\n"
                                f"Parent childItemType={parent_child_type} does not match item type.\n"
                                f"This item cannot be placed under this parent."
                            )

                    print(f"[DRY RUN] Existing item {excel_id} / Jama ID {existing_jama_id} is under parent {current_parent_item_id}")
                    print(f"[DRY RUN] Desired parent is {parent_item_id}")
                    move_method = CONFIG.get("MOVE_METHOD", "PATCH")
                    print(f"[DRY RUN] Would MOVE item {existing_jama_id} to parent {parent_item_id} using {move_method}")

                    # Show what the move payload would look like
                    move_payload = {
                        "location": {
                            "parent": {
                                "item": parent_item_id
                            },
                            "sortOrder": sort_order
                        }
                    }
                    print(f"[DRY RUN] Move payload:")
                    print(json.dumps(move_payload, indent=2))
                    final_jama_id = existing_jama_id
            else:
                if action == "CREATE":
                    # Validate container has childItemType
                    if item_type in ("Set", "Folder", "Subsystem"):
                        validate_container_child_item_type(row, payload)

                    # Validate compatibility with parent
                    validate_parent_compatibility(row, payload, parent_item_id, parent_metadata)

                    # Show itemType and childItemType
                    new_item_type = payload.get("itemType")
                    new_child_type = payload.get("childItemType")
                    print(f"[INFO] New itemType: {new_item_type}")
                    if new_child_type:
                        print(f"[INFO] New childItemType: {new_child_type}")

                    # PRE-POST DUPLICATE CHECK: Check for existing item by parent+itemType+name
                    if CONFIG.get("ENABLE_PRE_POST_DUPLICATE_CHECK", True):
                        print(f"[INFO] Pre-POST duplicate check: parent={parent_item_id}, itemType={new_item_type}, name='{name}'")
                        try:
                            duplicate_item = find_existing_item_by_parent_type_name(
                                parent_item_id=parent_item_id,
                                item_type_id=new_item_type,
                                name=name,
                                child_item_type=new_child_type if item_type in ("Set", "Folder", "Segment", "Subsystem") else None
                            )

                            if duplicate_item:
                                # Found existing item - skip POST
                                duplicate_id = duplicate_item.get("id")
                                duplicate_doc_key = duplicate_item.get("documentKey", "")
                                duplicate_global_id = duplicate_item.get("globalId", "")

                                print(f"[WARN] Pre-POST duplicate check found existing item: Jama ID {duplicate_id}")
                                print(f"[WARN] Skipping POST to prevent duplicate creation")

                                # Update action and metadata
                                if item_type in ("Set", "Folder", "Segment", "Subsystem"):
                                    # For folders: change to RESOLVE and register as parent
                                    action = "RESOLVE"
                                    final_jama_id = duplicate_id
                                    resolved_by = "parent_type_name_match"

                                    # Update metadata
                                    if not document_key:
                                        document_key = duplicate_doc_key
                                    if not global_id:
                                        global_id = duplicate_global_id

                                    # Store and register
                                    store_item_metadata(duplicate_id, duplicate_item)
                                    print(f"[OK] Resolved existing {item_type} by parent+itemType+name -> Jama ID {duplicate_id}")
                                    print(f"[OK] Registered as current parent. No item created.")
                                else:
                                    # For requirements/Text: change to SKIP_EXISTING
                                    action = "SKIP_EXISTING"
                                    final_jama_id = duplicate_id
                                    resolved_by = "parent_type_name_match"

                                    # Update metadata
                                    if not document_key:
                                        document_key = duplicate_doc_key
                                    if not global_id:
                                        global_id = duplicate_global_id

                                    print(f"[SKIP] Pre-POST check found existing {item_type}: Jama ID {duplicate_id}")
                                    print(f"[SKIP] No item created.")

                        except ValueError as e:
                            # Multiple matches - fail the row
                            print(f"[ERROR] Pre-POST duplicate check failed: {e}")
                            raise e

                    # Only POST if action is still CREATE after duplicate check
                    if action == "CREATE":
                        response = jama_post(CREATE_ITEM_ENDPOINT, payload)
                        metadata = extract_item_metadata(response)
                        final_jama_id = metadata["jama_id"]
                        created_item_id = final_jama_id
                        document_key = metadata["document_key"]
                        global_id = metadata["global_id"]

                        # Store metadata for newly created containers
                        if item_type in ("Set", "Folder", "Segment", "Subsystem"):
                            # Store basic metadata for the newly created container
                            new_item_metadata = {
                                "id": final_jama_id,
                                "documentKey": document_key,
                                "globalId": global_id,
                                "itemType": new_item_type,
                                "childItemType": new_child_type,
                                "project": JAMA_PROJECT_ID,
                                "fields": payload.get("fields", {})
                            }
                            store_item_metadata(final_jama_id, new_item_metadata)

                        if item_type in ("Set", "Folder", "Segment", "Subsystem"):
                            print(f"[OK] Created new {item_type} with Jama ID: {final_jama_id}, documentKey: {document_key}")
                        else:
                            print(f"[OK] Created {item_type} with Jama ID: {final_jama_id}")
                        # Small delay to avoid hammering the API
                        time.sleep(API_CALL_DELAY_SECONDS)
                elif action == "RESOLVE":
                    # Existing item resolved - register as parent only, no update performed
                    final_jama_id = existing_jama_id
                    print(f"[OK] Resolved folder by documentKey {excel_id} -> Jama ID {final_jama_id}")
                    print(f"[OK] Registered as current parent. No folder created.")
                elif action == "SKIP":
                    final_jama_id = existing_jama_id
                    print(f"[SKIP] Existing {item_type} has Jama ID {final_jama_id}")
                    if not needs_move:
                        print(f"[SKIP] Item is already in correct location. No action needed.")
                elif action == "SKIP_NEEDS_MOVE":
                    final_jama_id = existing_jama_id
                    print(f"[SKIP] Existing {item_type} has Jama ID {final_jama_id}")
                    print(f"[WARN] Item is under parent {current_parent_item_id}, but should be under {parent_item_id}")
                    print(f"[WARN] Enable --allow-move to move this item to the correct parent")
                elif action == "MOVE":
                    # Validate compatibility with target parent before move
                    new_item_type = ITEM_TYPE_IDS.get(item_type)
                    if new_item_type and parent_metadata:
                        parent_child_type = parent_metadata.get("childItemType")
                        if parent_child_type and new_item_type != parent_child_type:
                            raise ValueError(
                                f"Cannot move {item_type} (itemType={new_item_type}) to parent {parent_item_id}.\n"
                                f"Parent childItemType={parent_child_type} does not match item type.\n"
                                f"This item cannot be placed under this parent."
                            )

                    print(f"[MOVE] Moving item {excel_id} / Jama ID {existing_jama_id} from parent {current_parent_item_id} to {parent_item_id}")

                    move_payload = {
                        "location": {
                            "parent": {
                                "item": parent_item_id
                            },
                            "sortOrder": sort_order
                        }
                    }

                    move_method = CONFIG.get("MOVE_METHOD", "PATCH")
                    if move_method == "PATCH":
                        response = jama_patch(existing_jama_id, move_payload)
                    else:  # PUT
                        # For PUT, need to include all required fields
                        if not existing_item_metadata:
                            raise RuntimeError(f"Cannot use PUT without existing item metadata for item {existing_jama_id}")

                        # Build full PUT payload
                        put_payload = {
                            "fields": existing_item_metadata.get("fields", {}),
                            "itemType": existing_item_metadata.get("itemType"),
                            "location": move_payload["location"]
                        }

                        # Include childItemType if present
                        if existing_item_metadata.get("childItemType"):
                            put_payload["childItemType"] = existing_item_metadata.get("childItemType")

                        response = jama_put(existing_jama_id, put_payload)

                    final_jama_id = existing_jama_id
                    updated_item_id = existing_jama_id
                    print(f"[OK] Moved item {existing_jama_id} from parent {current_parent_item_id} to {parent_item_id} using {move_method}")
                    time.sleep(API_CALL_DELAY_SECONDS)

            # Increment sibling sort order for this parent
            sort_order_by_parent[parent_item_id] = sort_order + 1

            # Register containers in hierarchy
            if item_type in ("Set", "Folder", "Segment", "Subsystem"):
                if section_number and final_jama_id:
                    folder_by_section[section_number] = final_jama_id

                # Folder rows establish the active parent for subsequent requirement rows.
                # This applies whether the folder was newly created or resolved from existing Jama.
                if final_jama_id:
                    current_folder_item_id = final_jama_id

            # Determine resolved_by for results
            if not resolved_by or resolved_by == "none":
                if action == "CREATE":
                    resolved_by = "dry_run_fake_create" if dry_run else "created"
                elif action == "RESOLVE":
                    resolved_by = resolved_by if resolved_by != "none" else "jama_id"
                elif action in ("SKIP", "SKIP_NEEDS_MOVE", "MOVE"):
                    resolved_by = "jama_id"

            # Determine status
            if dry_run:
                if action == "CREATE":
                    status = "DRY_RUN_OK"
                elif action == "RESOLVE":
                    status = "DRY_RUN_RESOLVED_PARENT"
                elif action == "SKIP":
                    status = "DRY_RUN_SKIPPED"
                elif action == "SKIP_NEEDS_MOVE":
                    status = "DRY_RUN_NEEDS_MOVE"
                elif action == "MOVE":
                    status = "DRY_RUN_MOVE"
                else:
                    status = "DRY_RUN_OK"
            else:
                if action == "CREATE":
                    status = "CREATED"
                elif action == "RESOLVE":
                    status = "RESOLVED_PARENT"
                elif action == "SKIP":
                    status = "SKIPPED_NO_CHANGE"
                elif action == "SKIP_NEEDS_MOVE":
                    status = "SKIPPED_NEEDS_MOVE"
                elif action == "MOVE":
                    status = "MOVED"
                else:
                    status = "UPDATED"

            results.append({
                "excel_row": excel_row_number,
                "action": action,
                "status": status,
                "jama_id": final_jama_id or "",
                "document_key": document_key,
                "global_id": global_id,
                "source_id": excel_id,
                "item_type": item_type,
                "name": name,
                "resolved_by": resolved_by,
                "section_number": section_number or "",
                "parent_section_number": parent_section_number or "",
                "parent_item_id": parent_item_id,
                "created_item_id": created_item_id or "",
                "updated_item_id": updated_item_id or "",
                "current_parent_item_id": current_parent_item_id or "",
                "desired_parent_item_id": parent_item_id or "",
                "moved": "true" if action == "MOVE" and not dry_run else "false",
                "move_method": CONFIG.get("MOVE_METHOD", "") if action == "MOVE" else "",
                "error": ""
            })

        except Exception as exc:
            print("\n" + "=" * 80)
            print(f"[ERROR] Row {excel_row_number} failed.")
            print(f"[ERROR] {exc}")

            results.append({
                "excel_row": excel_row_number,
                "action": action or "FAILED",
                "status": "FAILED",
                "jama_id": existing_jama_id or "",
                "document_key": document_key if 'document_key' in locals() else "",
                "global_id": global_id,
                "source_id": excel_id,
                "item_type": item_type,
                "name": name,
                "resolved_by": resolved_by if 'resolved_by' in locals() else "none",
                "section_number": section_number or "",
                "parent_section_number": parent_section_number or "",
                "parent_item_id": parent_item_id if 'parent_item_id' in locals() else "",
                "created_item_id": created_item_id if 'created_item_id' in locals() else "",
                "updated_item_id": updated_item_id if 'updated_item_id' in locals() else "",
                "current_parent_item_id": current_parent_item_id if 'current_parent_item_id' in locals() else "",
                "desired_parent_item_id": parent_item_id if 'parent_item_id' in locals() else "",
                "moved": "false",
                "move_method": "",
                "error": str(exc)
            })

    write_import_results_csv(results, IMPORT_RESULTS_CSV)

    created_count = len([r for r in results if r["action"] == "CREATE" and r["status"] != "FAILED"])
    resolved_count = len([r for r in results if r["action"] == "RESOLVE" and r["status"] != "FAILED"])
    skipped_count = len([r for r in results if r["action"] == "SKIP" and r["status"] != "FAILED"])
    moved_count = len([r for r in results if r["action"] == "MOVE" and r["status"] != "FAILED"])
    needs_move_count = len([r for r in results if r["action"] == "SKIP_NEEDS_MOVE" and r["status"] != "FAILED"])
    failed_count = len([r for r in results if r["status"] == "FAILED"])
    total_success = created_count + resolved_count + moved_count

    print("\n" + "=" * 80)
    print("IMPORT SUMMARY")
    print("=" * 80)
    print(f"Mode: {mode}")
    print(f"Execution: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print(f"Created rows: {created_count}")
    print(f"Resolved parent rows: {resolved_count}")
    print(f"Skipped rows: {skipped_count}")
    print(f"Moved rows: {moved_count}")
    if needs_move_count > 0:
        print(f"Rows needing move: {needs_move_count} (enable --allow-move to move these)")
    print(f"Failed rows: {failed_count}")
    print(f"Total successful: {total_success}")
    print(f"Results CSV: {IMPORT_RESULTS_CSV}")

    if failed_count:
        print("\nFailures:")
        for result in results:
            if result["status"] == "FAILED":
                print(
                    f"Row {result['excel_row']} | "
                    f"{result['source_id']} | "
                    f"{result['item_type']} | "
                    f"{result['name']} | "
                    f"{result['error']}"
                )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import Jama items from Excel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Simple Usage:
  python csv2jama.py               # Dry-run (safe preview, no changes)
  python csv2jama.py --execute     # Execute import (creates new items)

Advanced Options:
  python csv2jama.py --mode create # Create-only mode

Configuration:
  Settings are loaded from .env file in the same directory.
  See .env.example for available options.
        """
    )

    parser.add_argument(
        "--mode",
        choices=["create", "upsert"],
        default=None,
        help="Import mode: create (new only), upsert (new + resolve existing). Default: from .env (upsert)"
    )

    parser.add_argument(
        "--dry-run",
        dest="dry_run_flag",
        action="store_true",
        default=None,
        help="Force dry-run mode (preview only, no changes)"
    )

    parser.add_argument(
        "--execute",
        dest="execute_flag",
        action="store_true",
        default=False,
        help="Execute import (make actual API calls)"
    )

    args = parser.parse_args()

    # Determine mode: CLI arg overrides .env
    mode = args.mode if args.mode is not None else CONFIG.get("IMPORT_MODE", "upsert")

    # Determine dry_run: --execute overrides --dry-run overrides .env
    if args.execute_flag:
        dry_run = False
    elif args.dry_run_flag is not None:
        dry_run = args.dry_run_flag
    else:
        dry_run = CONFIG.get("DRY_RUN", True)

    # Validate configuration for safety
    validate_configuration(CONFIG)

    # Print configuration summary with runtime arguments
    print_configuration_summary(CONFIG, mode=mode, dry_run=dry_run)

    # Run import
    import_excel(mode=mode, dry_run=dry_run)