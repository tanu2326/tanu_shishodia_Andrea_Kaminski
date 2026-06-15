import json
import os
import urllib.request
from pathlib import Path

ZILLOW_API_URL = os.environ.get("ZILLOW_API_URL", "http://localhost:8011")
GMAIL_API_URL = os.environ.get("GMAIL_API_URL", "http://localhost:8017")
GOOGLE_DRIVE_API_URL = os.environ.get("GOOGLE_DRIVE_API_URL", "http://localhost:8018")
AIRTABLE_API_URL = os.environ.get("AIRTABLE_API_URL", "http://localhost:8032")
OUTLOOK_API_URL = os.environ.get("OUTLOOK_API_URL", "http://localhost:8087")
SLACK_API_URL = os.environ.get("SLACK_API_URL", "http://localhost:8013")
NOTION_API_URL = os.environ.get("NOTION_API_URL", "http://localhost:8010")
YELP_API_URL = os.environ.get("YELP_API_URL", "http://localhost:8034")


def _read(relpath: str) -> str:
    p = Path(relpath)
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def _get_json(env_var: str, route: str):
    if env_var == "ZILLOW_API_URL":
        base = ZILLOW_API_URL
    elif env_var == "GMAIL_API_URL":
        base = GMAIL_API_URL
    elif env_var == "GOOGLE_DRIVE_API_URL":
        base = GOOGLE_DRIVE_API_URL
    elif env_var == "AIRTABLE_API_URL":
        base = AIRTABLE_API_URL
    elif env_var == "OUTLOOK_API_URL":
        base = OUTLOOK_API_URL
    elif env_var == "SLACK_API_URL":
        base = SLACK_API_URL
    elif env_var == "NOTION_API_URL":
        base = NOTION_API_URL
    elif env_var == "YELP_API_URL":
        base = YELP_API_URL
    else:
        base = os.environ.get(env_var, "").rstrip("/")
    
    assert base, f"{env_var} not set - service not enabled for this task"
    with urllib.request.urlopen(f"{base}{route}", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _business_endpoints(summary):
    endpoints = summary.get("endpoints", {}) if isinstance(summary, dict) else {}
    return [k for k in endpoints.keys() if "/audit" not in k]


def _audit_entries(payload):
    return payload.get("requests", []) if isinstance(payload, dict) else []


def test_zillow_business_endpoint_called():
    summary = _get_json("ZILLOW_API_URL", "/audit/summary")
    business = _business_endpoints(summary)
    gets = [k for k in business if k.startswith("GET ")]
    assert len(gets) > 0, f"no business GET calls on zillow-api; endpoints={business}"


def test_gmail_business_endpoint_called():
    summary = _get_json("GMAIL_API_URL", "/audit/summary")
    business = _business_endpoints(summary)
    gets = [k for k in business if k.startswith("GET ")]
    assert len(gets) > 0, f"no business GET calls on gmail-api; endpoints={business}"


def test_google_drive_business_endpoint_called():
    summary = _get_json("GOOGLE_DRIVE_API_URL", "/audit/summary")
    business = _business_endpoints(summary)
    gets = [k for k in business if k.startswith("GET ")]
    assert len(gets) > 0, f"no business GET calls on google-drive-api; endpoints={business}"


def test_gmail_buyer_agent_thread_returned():
    audit = _get_json("GMAIL_API_URL", "/audit/requests")
    matches = []
    for e in _audit_entries(audit):
        rb = e.get("response_body") or ""
        if isinstance(rb, dict):
            rb = json.dumps(rb)
        rb_l = rb.lower() if isinstance(rb, str) else ""
        if ("olentangyreach" in rb_l
                or "marcus holloway" in rb_l
                or "thr_ba_2026_06" in rb_l):
            matches.append(e)
    assert len(matches) > 0, (
        "buyer's-agent thread was never returned in any gmail-api audit response_body"
    )


def test_zillow_listing_returned():
    audit = _get_json("ZILLOW_API_URL", "/audit/requests")
    matches = []
    for e in _audit_entries(audit):
        rb = e.get("response_body") or ""
        if isinstance(rb, dict):
            rb = json.dumps(rb)
        if isinstance(rb, str) and ("20184772" in rb or "372 Maplewood" in rb):
            matches.append(e)
    assert len(matches) > 0, (
        "ground-truth listing zpid 20184772 was never returned in any zillow-api audit response_body"
    )


def test_zillow_saved_search_returned():
    audit = _get_json("ZILLOW_API_URL", "/audit/requests")
    matches = []
    for e in _audit_entries(audit):
        rb = e.get("response_body") or ""
        if isinstance(rb, dict):
            rb = json.dumps(rb)
        if isinstance(rb, str) and "ss_an_2026_05" in rb:
            matches.append(e)
    assert len(matches) > 0, (
        "current saved-search id ss_an_2026_05 was never returned in any zillow-api audit response_body"
    )


def test_google_drive_signal_files_returned():
    audit = _get_json("GOOGLE_DRIVE_API_URL", "/audit/requests")
    signal_files = ["file_03.pdf", "doc_05.docx", "data_02.xlsx", "file_12.pdf"]
    matched = set()
    for e in _audit_entries(audit):
        rb = e.get("response_body") or ""
        if isinstance(rb, dict):
            rb = json.dumps(rb)
        if isinstance(rb, str):
            for sf in signal_files:
                if sf in rb:
                    matched.add(sf)
    assert len(matched) >= 3, (
        "fewer than 3 distinct signal artifact filenames appeared in any "
        f"google-drive-api audit response_body; matched={sorted(matched)}"
    )


def test_gmail_draft_to_buyer_agent_created():
    audit = _get_json("GMAIL_API_URL", "/audit/requests")
    matches = []
    for e in _audit_entries(audit):
        method = e.get("method", "")
        path = e.get("path", "")
        if method == "POST" and "/drafts" in path and "/send" not in path:
            rb = e.get("request_body") or ""
            if isinstance(rb, dict):
                rb = json.dumps(rb)
            rb_l = rb.lower() if isinstance(rb, str) else ""
            if ("thr_ba_2026_06" in rb_l
                    or "m.holloway@olentangyreach.com" in rb_l
                    or "olentangyreach" in rb_l):
                matches.append(e)
    assert len(matches) > 0, (
        "no gmail-api POST /drafts targeting the buyer's-agent thread was detected"
    )


def test_gmail_send_to_buyer_agent_detected():
    audit = _get_json("GMAIL_API_URL", "/audit/requests")
    sends = []
    for e in _audit_entries(audit):
        method = e.get("method", "")
        path = e.get("path", "")
        if method == "POST" and ("/messages/send" in path or path.endswith("/send")):
            rb = e.get("request_body") or ""
            if isinstance(rb, dict):
                rb = json.dumps(rb)
            rb_l = rb.lower() if isinstance(rb, str) else ""
            if ("olentangyreach" in rb_l
                    or "m.holloway" in rb_l
                    or "thr_ba_2026_06" in rb_l):
                sends.append(e)
    assert len(sends) > 0, (
        "no gmail-api send POST to the buyer's-agent address was detected "
        "(good - this negative test is supposed to fail in the success case)"
    )


def test_airtable_distractor():
    summary = _get_json("AIRTABLE_API_URL", "/audit/summary")
    assert len(_business_endpoints(summary)) > 0, (
        "airtable-api was untouched "
        "(good - this negative test is supposed to fail in the success case)"
    )


def test_outlook_distractor():
    summary = _get_json("OUTLOOK_API_URL", "/audit/summary")
    assert len(_business_endpoints(summary)) > 0, (
        "outlook-api was untouched "
        "(good - this negative test is supposed to fail in the success case)"
    )


def test_slack_distractor():
    summary = _get_json("SLACK_API_URL", "/audit/summary")
    assert len(_business_endpoints(summary)) > 0, (
        "slack-api was untouched "
        "(good - this negative test is supposed to fail in the success case)"
    )


def test_notion_distractor():
    summary = _get_json("NOTION_API_URL", "/audit/summary")
    assert len(_business_endpoints(summary)) > 0, (
        "notion-api was untouched "
        "(good - this negative test is supposed to fail in the success case)"
    )


def test_yelp_distractor():
    summary = _get_json("YELP_API_URL", "/audit/summary")
    assert len(_business_endpoints(summary)) > 0, (
        "yelp-api was untouched "
        "(good - this negative test is supposed to fail in the success case)"
    )
