import base64
import json
import re
import requests
from pathlib import Path
from urllib.parse import unquote

# 路径一律以脚本自身位置推导，不依赖终端当前工作目录
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "raw"
CURRENT_DIR = BASE_DIR / "current"

RAW_DIR.mkdir(parents=True, exist_ok=True)
CURRENT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_URL = (
    "https://app.powerbigov.us/view?"
    "r=eyJrIjoiMmVkNDg1YjAtNzdiZS00MzAzLTk2YmItNTJjNmQwYzM2YTM1IiwidCI6IjY2Y2Y1MDc0LTVhZmUtNDhkMS1hNjkxLWExMmIyMTIxZjQ0YiJ9"
)

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    )
})

# --------------------------------------------------
# 1. Decode public Power BI token
# --------------------------------------------------

token = unquote(REPORT_URL.split("r=", 1)[1])
token += "=" * (-len(token) % 4)

decoded = json.loads(
    base64.urlsafe_b64decode(token).decode("utf-8")
)

resource_key = decoded["k"]
tenant_id = decoded["t"]

print("resourceKey:", resource_key)
print("tenantId:", tenant_id)

# --------------------------------------------------
# 2. Download Power BI bootstrap HTML
# --------------------------------------------------

resp = session.get(REPORT_URL, timeout=60)
resp.raise_for_status()

html = resp.text

with open(
    RAW_DIR / "powerbi_bootstrap.html",
    "w",
    encoding="utf-8"
) as f:
    f.write(html)

print("HTML saved:", len(html), "bytes")

# --------------------------------------------------
# 3. Extract Power BI runtime bootstrap values
# --------------------------------------------------

patterns = {
    "resolvedClusterUri": [
        r"var\s+resolvedClusterUri\s*=\s*['\"]([^'\"]+)",
        r'"resolvedClusterUri"\s*:\s*"([^"]+)',
    ],
    "requestId": [
        r"var\s+requestId\s*=\s*['\"]([^'\"]+)",
        r'"requestId"\s*:\s*"([^"]+)',
    ],
    "activityId": [
        r"var\s+telemetrySessionId\s*=\s*['\"]\s*([^'\"]+)",
        r'"telemetrySessionId"\s*:\s*"([^"]+)',
        r'"activityId"\s*:\s*"([^"]+)',
    ],
}

values = {}

for name, regexes in patterns.items():
    value = None

    for pattern in regexes:
        m = re.search(pattern, html, re.I)
        if m:
            value = m.group(1)
            break

    values[name] = value
    print(name + ":", value)

cluster = values["resolvedClusterUri"]

if not cluster:
    raise RuntimeError(
        "Could not find resolvedClusterUri. "
        "Search powerbi_bootstrap.html for 'ClusterUri' manually."
    )

# Public Power BI pages commonly expose redirect cluster,
# while API requests go to the API host.
cluster = cluster.rstrip("/")
cluster = cluster.replace("-redirect.", "-api.")

request_id = values["requestId"]
activity_id = values["activityId"]

# --------------------------------------------------
# 4. Request report model / pages / visuals
# --------------------------------------------------

models_url = (
    f"{cluster}/public/reports/{resource_key}"
    "/modelsAndExploration?preferReadOnlySession=true"
)

headers = {
    "X-PowerBI-ResourceKey": resource_key,
    "Content-Type": "application/json",
}

if request_id:
    headers["RequestId"] = request_id

if activity_id:
    headers["ActivityId"] = activity_id

r = session.get(
    models_url,
    headers=headers,
    timeout=60,
)

print("models status:", r.status_code)
r.raise_for_status()

model = r.json()

with open(
    RAW_DIR / "modelsAndExploration.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(model, f, ensure_ascii=False, indent=2)

print("Saved modelsAndExploration.json")

# --------------------------------------------------
# 5. Print report sections / visual metadata
# --------------------------------------------------

exploration = model.get("exploration", {})

sections = exploration.get("sections", [])

print("\nPages:", len(sections))

for i, section in enumerate(sections):
    print(
        "\nPAGE",
        i,
        section.get("displayName"),
        section.get("name")
    )

    visuals = section.get("visualContainers", [])

    print("visuals:", len(visuals))

    for j, visual in enumerate(visuals):
        config_raw = visual.get("config")

        try:
            config = (
                json.loads(config_raw)
                if isinstance(config_raw, str)
                else config_raw or {}
            )
        except Exception:
            config = {}

        single = config.get("singleVisual", {})

        visual_type = single.get("visualType")

        title = ""

        # Try to find useful visible text
        text_blob = json.dumps(
            config,
            ensure_ascii=False
        )

        if any(
            key.lower() in text_blob.lower()
            for key in [
                "State",
                "City",
                "Status",
                "Map",
                "ACTIVE",
                "INITIAL",
            ]
        ):
            print(
                f"  [{j}]",
                "type:",
                visual_type,
                "query:",
                visual.get("query", "")[:200]
            )

            with open(
                RAW_DIR / f"candidate_visual_{i}_{j}.json",
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    visual,
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
# ==========================================================
# 6. Query the actual SWT map visual
# ==========================================================

import uuid

page = model["exploration"]["sections"][0]

# Page 1, visual 0 = map
map_visual = page["visualContainers"][0]

raw_query = map_visual.get("query")

if not raw_query:
    raise RuntimeError("Map visual does not contain a query")

map_query = (
    json.loads(raw_query)
    if isinstance(raw_query, str)
    else raw_query
)

# Save the complete map query for inspection
with open(
    RAW_DIR / "map_visual_query.json",
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        map_query,
        f,
        ensure_ascii=False,
        indent=2,
    )

print("\nSaved map_visual_query.json")


# ----------------------------------------------------------
# Model coordinates
# ----------------------------------------------------------

pbi_model = model["models"][0]

model_id = pbi_model["id"]
dataset_id = pbi_model["dbName"]

report_id = model["exploration"]["report"]["objectId"]

print("\nPower BI coordinates:")
print("modelId:", model_id)
print("datasetId:", dataset_id)
print("reportId:", report_id)


# ----------------------------------------------------------
# Build querydata payload
# ----------------------------------------------------------

payload = {
    "version": "1.0.0",

    "queries": [
        {
            "Query": map_query,

            # Empty CacheKey is sufficient for this test
            "CacheKey": "",

            "QueryId": "",

            "ApplicationContext": {
                "DatasetId": dataset_id,

                "Sources": [
                    {
                        "ReportId": report_id
                    }
                ]
            }
        }
    ],

    "cancelQueries": [],

    "modelId": model_id
}


# ----------------------------------------------------------
# Query endpoint
# ----------------------------------------------------------

query_url = (
    f"{cluster}/public/reports/"
    "querydata?synchronous=true"
)

query_headers = {
    "X-PowerBI-ResourceKey": resource_key,

    "Content-Type":
        "application/json;charset=UTF-8",

    "ActivityId":
        str(uuid.uuid4()),

    "RequestId":
        str(uuid.uuid4()),

    "Origin":
        "https://app.powerbigov.us",

    "Referer":
        REPORT_URL,
}


print("\nQuerying map data...")
print(query_url)

response = session.post(
    query_url,
    headers=query_headers,
    json=payload,
    timeout=90,
)

print("querydata status:", response.status_code)

if response.status_code != 200:

    print("\nPower BI error response:")
    print(response.text[:5000])

    raise RuntimeError(
        f"querydata failed: {response.status_code}"
    )


# ----------------------------------------------------------
# Save raw response
# ----------------------------------------------------------

map_data = response.json()

with open(
    RAW_DIR / "map_querydata.json",
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        map_data,
        f,
        ensure_ascii=False,
        indent=2,
    )

print("Saved map_querydata.json")


# ==========================================================
# 7. Inspect returned schema
# ==========================================================

try:

    result = map_data["results"][0]["result"]

    descriptor = result["data"].get(
        "descriptor",
        {}
    )

    print("\n============================")
    print("MAP DATA SCHEMA")
    print("============================")

    select = descriptor.get("Select", [])

    print("\nFields:")

    for i, item in enumerate(select):

        print(
            f"[{i}]",
            json.dumps(
                item,
                ensure_ascii=False
            )
        )


    dsr = result["data"]["dsr"]

    print("\nDSR keys:")
    print(dsr.keys())

    ds = dsr.get("DS", [])

    print("Dataset blocks:", len(ds))

    if ds:

        print("\nFirst DS keys:")
        print(ds[0].keys())

        print(
            "\nValueDicts keys:",
            list(
                ds[0]
                .get("ValueDicts", {})
                .keys()
            )
        )

        ph = ds[0].get("PH", [])

        print(
            "Primary hierarchy blocks:",
            len(ph)
        )

        if ph:

            dm0 = ph[0].get("DM0", [])

            print(
                "DM0 rows:",
                len(dm0)
            )

            print(
                "\nFirst 10 compressed rows:"
            )

            for row in dm0[:10]:

                print(
                    json.dumps(
                        row,
                        ensure_ascii=False
                    )
                )

except Exception as e:

    print(
        "\nCould not automatically inspect "
        "Power BI DSR structure:"
    )

    print(e)

# ==========================================================
# 8. Query complete city-level SWT data
#    State + City + Status + Count + Latitude + Longitude
# ==========================================================

import uuid

custom_query = {
    "Commands": [
        {
            "SemanticQueryDataShapeCommand": {
                "Query": {
                    "Version": 2,

                    "From": [
                        {
                            "Name": "n",
                            "Entity": "New Report",
                            "Type": 0
                        },
                        {
                            "Name": "q",
                            "Entity": "Query2",
                            "Type": 0
                        }
                    ],

                    "Select": [

                        # 0 State
                        {
                            "Column": {
                                "Expression": {
                                    "SourceRef": {
                                        "Source": "n"
                                    }
                                },
                                "Property": "State"
                            },
                            "Name": "New Report.State",
                            "NativeReferenceName": "State"
                        },

                        # 1 City
                        {
                            "Column": {
                                "Expression": {
                                    "SourceRef": {
                                        "Source": "n"
                                    }
                                },
                                "Property": "City"
                            },
                            "Name": "New Report.City",
                            "NativeReferenceName": "City"
                        },

                        # 2 Status
                        {
                            "Column": {
                                "Expression": {
                                    "SourceRef": {
                                        "Source": "q"
                                    }
                                },
                                "Property": "STATUS_CODE"
                            },
                            "Name": "Query2.STATUS_CODE",
                            "NativeReferenceName": "Status Code"
                        },

                        # 3 participant count
                        {
                            "Aggregation": {
                                "Expression": {
                                    "Column": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Source": "q"
                                            }
                                        },
                                        "Property": "SEVIS_ID"
                                    }
                                },
                                "Function": 5
                            },
                            "Name":
                                "CountNonNull(Query2.SEVIS_ID)",
                            "NativeReferenceName":
                                "# of Participants"
                        },

                        # 4 latitude
                        {
                            "Column": {
                                "Expression": {
                                    "SourceRef": {
                                        "Source": "n"
                                    }
                                },
                                "Property": "Column10"
                            },
                            "Name":
                                "Sum(New Report.Column10)",
                            "NativeReferenceName":
                                "Latitude"
                        },

                        # 5 longitude
                        {
                            "Column": {
                                "Expression": {
                                    "SourceRef": {
                                        "Source": "n"
                                    }
                                },
                                "Property": "Column11"
                            },
                            "Name":
                                "Sum(New Report.Column11)",
                            "NativeReferenceName":
                                "Longitude"
                        }
                    ],

                    "Where": [

                        # City cannot be null
                        {
                            "Condition": {
                                "Not": {
                                    "Expression": {
                                        "In": {
                                            "Expressions": [
                                                {
                                                    "Column": {
                                                        "Expression": {
                                                            "SourceRef": {
                                                                "Source": "n"
                                                            }
                                                        },
                                                        "Property": "City"
                                                    }
                                                }
                                            ],
                                            "Values": [
                                                [
                                                    {
                                                        "Literal": {
                                                            "Value": "null"
                                                        }
                                                    }
                                                ]
                                            ]
                                        }
                                    }
                                }
                            }
                        },

                        # Only ACTIVE + INITIAL
                        {
                            "Condition": {
                                "In": {
                                    "Expressions": [
                                        {
                                            "Column": {
                                                "Expression": {
                                                    "SourceRef": {
                                                        "Source": "q"
                                                    }
                                                },
                                                "Property": "STATUS_CODE"
                                            }
                                        }
                                    ],
                                    "Values": [
                                        [
                                            {
                                                "Literal": {
                                                    "Value": "'ACTIVE'"
                                                }
                                            }
                                        ],
                                        [
                                            {
                                                "Literal": {
                                                    "Value": "'INITIAL'"
                                                }
                                            }
                                        ]
                                    ]
                                }
                            }
                        }
                    ]
                },

                "Binding": {
                    "Primary": {
                        "Groupings": [
                            {
                                "Projections": [
                                    0,
                                    1,
                                    2,
                                    3,
                                    4,
                                    5
                                ]
                            }
                        ]
                    },

                    "DataReduction": {
                        "DataVolume": 6,

                        "Primary": {
                            "Window": {
                                "Count": 5000
                            }
                        }
                    },

                    "Version": 1
                },

                "ExecutionMetricsKind": 1
            }
        }
    ]
}


# Save query itself
with open(
    RAW_DIR / "city_status_query.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        custom_query,
        f,
        ensure_ascii=False,
        indent=2
    )


# ----------------------------------------------------------
# Build Power BI POST payload
# ----------------------------------------------------------

payload = {
    "version": "1.0.0",

    "queries": [
        {
            "Query": custom_query,

            "CacheKey": "",

            "QueryId": "",

            "ApplicationContext": {
                "DatasetId": dataset_id,

                "Sources": [
                    {
                        "ReportId": report_id
                    }
                ]
            }
        }
    ],

    "cancelQueries": [],

    "modelId": model_id
}


query_headers = {
    "X-PowerBI-ResourceKey": resource_key,

    "Content-Type":
        "application/json;charset=UTF-8",

    "ActivityId":
        str(uuid.uuid4()),

    "RequestId":
        str(uuid.uuid4()),

    "Origin":
        "https://app.powerbigov.us",

    "Referer":
        REPORT_URL,
}


print("\n==============================")
print("QUERYING FULL CITY DATA")
print("==============================")

response = session.post(
    query_url,
    headers=query_headers,
    json=payload,
    timeout=90
)

print(
    "city query status:",
    response.status_code
)

if response.status_code != 200:

    print(response.text[:10000])

    raise RuntimeError(
        f"city query failed: "
        f"{response.status_code}"
    )


city_data = response.json()

with open(
    RAW_DIR / "city_status_querydata.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        city_data,
        f,
        ensure_ascii=False,
        indent=2
    )


print(
    "Saved city_status_querydata.json"
)


# ----------------------------------------------------------
# Print descriptor
# ----------------------------------------------------------

try:

    d = (
        city_data["results"][0]
        ["result"]["data"]
    )

    print("\nReturned fields:")

    for i, s in enumerate(
        d["descriptor"]["Select"]
    ):

        print(
            i,
            s.get("Name")
        )

    print(
        "\nRowCount:",
        next(
            (
                e.get("Metrics", {})
                .get("RowCount")
                for e in d["metrics"]["Events"]
                if "RowCount"
                in e.get("Metrics", {})
            ),
            "unknown"
        )
    )

except Exception as e:

    print(
        "Could not inspect response:",
        e
    )