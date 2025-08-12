import json
import openai
from pathlib import Path
from tqdm import tqdm
import random
import re

# === CONFIG === #
openai.api_key = ""

recovery_paths={
  "_legend": {
    "t": "Thought",
    "do": "Action (conceptual, not a tool name)",
    "out": "Simulated function output/result"
  },
  "400": {
    "paths": {
      "success": [
        [
          "t",
          "400 → malformed input likely; even though URL/endpoint looked fine, it still fails"
        ],
        [
          "do",
          "Check headers & required params; correct Content-Type/Auth; resend"
        ],
        ["out", { "error": { "code": 400, "message": "Bad Request" } }],
        [
          "t",
          "Still 400 → payload/schema suspect (types, required, enums, formats)"
        ],
        ["do", "Validate JSON against schema; fix offending fields; resend"],
        ["out", { "status": "ok" }],
        ["t", "Resolved after correcting schema; Finish"]
      ],
      "fail": [
        [
          "t",
          "400 persists after URL, headers, schema, and minimal-payload checks"
        ],
        [
          "do",
          "Test known-good sample; diff to find hidden rule; if unresolved, escalate with req/resp & steps"
        ],
        ["out", { "hand_off": "400_unresolved" }]
      ]
    }
  },
  "401": {
    "paths": {
      "success": [
        [
          "t",
          "401 → creds invalid; even though Authorization header exists, still 401"
        ],
        ["do", "Refresh/obtain token; verify scope/audience; resend"],
        ["out", { "status": "ok" }],
        ["t", "Authorized; Finish"]
      ],
      "fail": [
        ["t", "Still 401 after refresh → account/role issue"],
        [
          "do",
          "Notify admin/user to fix roles or re-enable account; attach failing req details"
        ],
        ["out", { "hand_off": "401_permissions" }]
      ]
    }
  },
  "403": {
    "paths": {
      "success": [
        [
          "t",
          "403 → authenticated but forbidden; even though docs say we should have access, still denied"
        ],
        [
          "do",
          "Confirm org policy/resource ACL; request explicit grant; retry"
        ],
        ["out", { "status": "ok" }],
        ["t", "Access granted; Finish"]
      ],
      "fail": [
        [
          "t",
          "403 persists despite correct role on paper → policy guardrail/region restriction"
        ],
        [
          "do",
          "Escalate with resource ID, tenant, policy dump; propose alt resource/region"
        ],
        ["out", { "hand_off": "403_forbidden_persistent" }]
      ]
    }
  },
  "404": {
    "paths": {
      "success": [
        [
          "t",
          "404 → not found; even though identifiers look correct, still missing"
        ],
        [
          "do",
          "List resources / search alt endpoints to confirm existence/rename"
        ],
        ["out", { "data": [{ "id": "found_replacement" }] }],
        ["t", "Found correct resource; Finish"]
      ],
      "fail": [
        ["t", "404 confirmed across listings → permanent missing"],
        ["do", "Report deletion/migration; propose recreate or alternative"],
        ["out", { "hand_off": "404_permanent" }]
      ]
    }
  },
  "408": {
    "paths": {
      "success": [
        ["t", "Timeout; even though network seems fine, server is slow"],
        ["do", "Retry with exponential backoff; increase timeout modestly"],
        ["out", { "status": "ok" }],
        ["t", "Completed within extended timeout; Finish"]
      ],
      "fail": [
        ["t", "Repeated 408 → upstream overload or network path issue"],
        ["do", "Switch endpoint/region if available; otherwise defer & alert"],
        ["out", { "hand_off": "408_persistent_timeout" }]
      ]
    }
  },
  "429": {
    "paths": {
      "success": [
        ["t", "429 → rate limited"],
        ["do", "Honor Retry-After/backoff; throttle concurrency; resend"],
        ["out", { "status": "ok" }],
        ["t", "Request accepted after throttling; Finish"]
      ],
      "fail": [
        ["t", "429 persists → quota ceiling"],
        ["do", "Queue work; reduce concurrency; request higher quota"],
        ["out", { "hand_off": "429_quota_increase_needed" }]
      ]
    }
  },
  "500": {
    "paths": {
      "success": [
        ["t", "500 → transient server error"],
        ["do", "Retry with backoff (1s,2s,4s) x3"],
        ["out", { "status": "ok" }],
        ["t", "Succeeded on retry; Finish"]
      ],
      "fail": [
        ["t", "Still 500 after backoff → outage/bug"],
        ["do", "Check provider status; log; pause until healthy; notify user"],
        ["out", { "hand_off": "provider_outage" }]
      ]
    }
  },
  "503": {
    "paths": {
      "success": [
        ["t", "503 → service unavailable"],
        ["do", "If Retry-After present, wait; else backoff and retry"],
        ["out", { "status": "ok" }],
        ["t", "Service recovered; Finish"]
      ],
      "fail": [
        ["t", "Prolonged 503"],
        ["do", "Alert/deferr; notify user and monitor status"],
        ["out", { "hand_off": "503_prolonged_unavailable" }]
      ]
    }
  },
  "502": {
    "paths": {
      "success": [
        ["t", "502 → bad gateway; transient upstream glitch"],
        ["do", "Brief wait then retry; consider alternate upstream"],
        ["out", { "status": "ok" }],
        ["t", "Succeeded after retry; Finish"]
      ],
      "fail": [
        ["t", "Repeated 502 → upstream instability"],
        ["do", "Fail over if possible; otherwise escalate"],
        ["out", { "hand_off": "502_upstream_issue" }]
      ]
    }
  },
  "504": {
    "paths": {
      "success": [
        ["t", "504 → gateway timeout"],
        ["do", "Increase timeout slightly; retry; verify upstream health"],
        ["out", { "status": "ok" }],
        ["t", "Completed after adjustment; Finish"]
      ],
      "fail": [
        ["t", "Persistent 504"],
        ["do", "Escalate to upstream owners; inform user"],
        ["out", { "hand_off": "504_upstream_timeout" }]
      ]
    }
  },
  "505": {
    "paths": {
      "success": [
        ["t", "505 → HTTP version unsupported"],
        ["do", "Switch to supported version (HTTP/1.1 or HTTP/2)"],
        ["out", { "status": "ok" }],
        ["t", "Processed with supported protocol; Finish"]
      ],
      "fail": [
        ["t", "Protocol constraints cannot be met"],
        ["do", "Document limitation; propose compatible client/server"],
        ["out", { "hand_off": "505_incompatibility" }]
      ]
    }
  },
  "507": {
    "paths": {
      "success": [
        ["t", "507 → insufficient storage"],
        ["do", "Free space/rotate logs; retry write"],
        ["out", { "status": "ok" }],
        ["t", "Write succeeded post cleanup; Finish"]
      ],
      "fail": [
        ["t", "Storage remains full"],
        ["do", "Request expansion; pause writes"],
        ["out", { "hand_off": "507_storage_full" }]
      ]
    }
  },
  "508": {
    "paths": {
      "success": [
        ["t", "508 → loop detected"],
        ["do", "Break cyclic reference; adjust traversal/links; retry"],
        ["out", { "status": "ok" }],
        ["t", "Loop resolved; Finish"]
      ],
      "fail": [
        ["t", "Cannot break loop automatically"],
        ["do", "Log full path/graph; assign manual fix"],
        ["out", { "hand_off": "508_loop_persistent" }]
      ]
    }
  },
  "510": {
    "paths": {
      "success": [
        ["t", "510 → extensions/headers required"],
        ["do", "Add required options/headers per docs; resend"],
        ["out", { "status": "ok" }],
        ["t", "Accepted with extensions; Finish"]
      ],
      "fail": [
        ["t", "Unknown extension requirement"],
        ["do", "Escalate with server demand details"],
        ["out", { "hand_off": "510_missing_extension_unknown" }]
      ]
    }
  },
  "511": {
    "paths": {
      "success": [
        ["t", "511 → network auth required"],
        ["do", "Complete captive portal/login; retry request"],
        ["out", { "status": "ok" }],
        ["t", "Network authenticated; Finish"]
      ],
      "fail": [
        ["t", "Cannot complete network auth programmatically"],
        ["do", "Ask user to authenticate; provide steps"],
        ["out", { "hand_off": "511_user_network_auth_needed" }]
      ]
    }
  },
  "529": {
    "paths": {
      "success": [
        ["t", "529 → site overloaded"],
        ["do", "Backoff & jitter; spread requests; retry"],
        ["out", { "status": "ok" }],
        ["t", "Processed after load subsided; Finish"]
      ],
      "fail": [
        ["t", "Sustained overload"],
        ["do", "Defer/queue; notify user"],
        ["out", { "hand_off": "529_overload_persistent" }]
      ]
    }
  },
  "530": {
    "paths": {
      "success": [
        ["t", "530 → site/account frozen"],
        ["do", "Notify owner; resolve billing/policy; retry once unfrozen"],
        ["out", { "status": "ok" }],
        ["t", "Unfrozen & processed; Finish"]
      ],
      "fail": [
        ["t", "Freeze persists"],
        ["do", "Provide support contact; pause job"],
        ["out", { "hand_off": "530_frozen_account" }]
      ]
    }
  },
  "540": {
    "paths": {
      "success": [
        ["t", "540 → endpoint temporarily disabled"],
        ["do", "Log maintenance; retry after window"],
        ["out", { "status": "ok" }],
        ["t", "Service restored; Finish"]
      ],
      "fail": [
        ["t", "Extended disablement"],
        ["do", "Offer alternative flow; inform user"],
        ["out", { "hand_off": "540_disabled_extended" }]
      ]
    }
  },
  "598": {
    "paths": {
      "success": [
        ["t", "598 → proxy read timeout"],
        ["do", "Increase timeout modestly; retry; verify network path"],
        ["out", { "status": "ok" }],
        ["t", "Completed after tuning; Finish"]
      ],
      "fail": [
        ["t", "Timeout persists via proxy"],
        ["do", "Bypass/alternate proxy; escalate to netops"],
        ["out", { "hand_off": "598_proxy_timeout" }]
      ]
    }
  },
  "599": {
    "paths": {
      "success": [
        ["t", "599 → proxy connect timeout"],
        ["do", "Retry with backoff; test connectivity; alternate route"],
        ["out", { "status": "ok" }],
        ["t", "Connected on retry; Finish"]
      ],
      "fail": [
        ["t", "Cannot connect via proxy"],
        ["do", "Escalate to netops; suggest direct route if allowed"],
        ["out", { "hand_off": "599_proxy_connect_fail" }]
      ]
    }
  },
  "421": {
    "paths": {
      "success": [
        ["t", "421 → misdirected request"],
        ["do", "Send to correct origin/host; verify routing"],
        ["out", { "status": "ok" }],
        ["t", "Routed correctly; Finish"]
      ],
      "fail": [
        ["t", "Routing unresolved"],
        ["do", "Escalate with host map and trace"],
        ["out", { "hand_off": "421_routing_issue" }]
      ]
    }
  },
  "DNS Resolution Error": {
    "paths": {
      "success": [
        ["t", "DNS resolution failed; even though domain looks correct"],
        [
          "do",
          "Resolve a known public host to test DNS; flush/alternate resolver; retry"
        ],
        ["out", { "status": "ok" }],
        ["t", "DNS healthy after switch; Finish"]
      ],
      "fail": [
        ["t", "Custom domain still not resolving"],
        ["do", "Escalate to infra; provide NS records and failure traces"],
        ["out", { "hand_off": "dns_unresolved" }]
      ]
    }
  },
  "Malformed JSON": {
    "paths": {
      "success": [
        ["t", "Server returned malformed JSON; might be transient"],
        [
          "do",
          "Retry once; if still malformed, apply tolerant parse or fetch alt format if available"
        ],
        ["out", { "status": "ok" }],
        ["t", "Parsed successfully; Finish"]
      ],
      "fail": [
        ["t", "Response remains malformed"],
        [
          "do",
          "Capture sample; notify API owner; fallback to cached/previous data"
        ],
        ["out", { "hand_off": "malformed_json_persistent" }]
      ]
    }
  },
  "JSON Schema Violation": {
    "paths": {
      "success": [
        ["t", "Schema mismatch; even though types looked right"],
        ["do", "Validate against schema; coerce/omit failing fields; resend"],
        ["out", { "status": "ok" }],
        ["t", "Accepted after correction; Finish"]
      ],
      "fail": [
        ["t", "Violation originates server-side data"],
        ["do", "Log failing fields; escalate to provider"],
        ["out", { "hand_off": "schema_violation_server" }]
      ]
    }
  },
  "NoSuchToolError": {
    "paths": {
      "success": [
        ["t", "Tried to call an unavailable tool"],
        ["do", "Check registry; correct name or select supported alternative"],
        ["out", { "status": "ok" }],
        ["t", "Tool corrected; Finish"]
      ],
      "fail": [
        ["t", "No equivalent tool available"],
        ["do", "Report limitation; suggest manual step"],
        ["out", { "hand_off": "no_such_tool" }]
      ]
    }
  },
  "InvalidToolArgumentsError": {
    "paths": {
      "success": [
        ["t", "Tool args invalid; even though syntax looked fine"],
        ["do", "Review spec; fix names/types; resend"],
        ["out", { "status": "ok" }],
        ["t", "Tool executed with corrected args; Finish"]
      ],
      "fail": [
        ["t", "Argument contract unclear"],
        ["do", "Request example call/spec update; escalate"],
        ["out", { "hand_off": "invalid_args_unclear" }]
      ]
    }
  },
  "ToolExecutionError": {
    "paths": {
      "success": [
        ["t", "Tool threw exception"],
        [
          "do",
          "Capture stack/output; retry if transient; reset state if applicable"
        ],
        ["out", { "status": "ok" }],
        ["t", "Recovered after reset/retry; Finish"]
      ],
      "fail": [
        ["t", "Deterministic tool failure"],
        ["do", "Open issue with trace; propose alternative route"],
        ["out", { "hand_off": "tool_execution_bug" }]
      ]
    }
  },
  "ToolCallRepairError": {
    "paths": {
      "success": [
        ["t", "Automatic repair attempt failed"],
        ["do", "Switch strategy: reset tool state or choose a different tool"],
        ["out", { "status": "ok" }],
        ["t", "Succeeded after alternative; Finish"]
      ],
      "fail": [
        ["t", "Alternate strategies exhausted"],
        ["do", "Escalate with repair log"],
        ["out", { "hand_off": "tool_repair_exhausted" }]
      ]
    }
  },
  "RuntimeError": {
    "paths": {
      "success": [
        ["t", "Unexpected runtime error"],
        ["do", "Inspect message; rollback recent change; reset state; retry"],
        ["out", { "status": "ok" }],
        ["t", "Recovered; Finish"]
      ],
      "fail": [
        ["t", "Runtime defect persists"],
        ["do", "Log trace; pin to version; escalate"],
        ["out", { "hand_off": "runtime_persistent" }]
      ]
    }
  },
  "DataError": {
    "paths": {
      "success": [
        ["t", "Invalid/missing data"],
        ["do", "Validate/clean; fill defaults; retry"],
        ["out", { "status": "ok" }],
        ["t", "Processed with corrected data; Finish"]
      ],
      "fail": [
        ["t", "Data irreparable automatically"],
        ["do", "Report missing fields; request source fix"],
        ["out", { "hand_off": "data_source_issue" }]
      ]
    }
  },
  "ConnectionError": {
    "paths": {
      "success": [
        ["t", "Network connection failed"],
        ["do", "Test reachability; backoff; try alternate endpoint"],
        ["out", { "status": "ok" }],
        ["t", "Connected and retried; Finish"]
      ],
      "fail": [
        ["t", "Connectivity remains down"],
        ["do", "Escalate to networking; include traceroute/logs"],
        ["out", { "hand_off": "network_down" }]
      ]
    }
  },
  "TypeError": {
    "paths": {
      "success": [
        ["t", "Wrong types passed"],
        ["do", "Check variable types; cast/convert; retry"],
        ["out", { "status": "ok" }],
        ["t", "Succeeded with correct types; Finish"]
      ],
      "fail": [
        ["t", "Type source ambiguous"],
        ["do", "Add validation at boundaries; escalate with sample payload"],
        ["out", { "hand_off": "type_mismatch_root_unknown" }]
      ]
    }
  },
  "NullPointerException": {
    "paths": {
      "success": [
        ["t", "Tried to use a null/None value"],
        ["do", "Add null checks; ensure init before use; retry"],
        ["out", { "status": "ok" }],
        ["t", "No longer null; Finish"]
      ],
      "fail": [
        ["t", "Upstream provides null unavoidably"],
        ["do", "Request upstream fix or guard with fallback"],
        ["out", { "hand_off": "null_source_upstream" }]
      ]
    }
  },
  "IndexOutOfBoundsException": {
    "paths": {
      "success": [
        ["t", "Index outside bounds"],
        ["do", "Check lengths; clamp indices; adjust loops"],
        ["out", { "status": "ok" }],
        ["t", "Valid indices used; Finish"]
      ],
      "fail": [
        ["t", "Data shape unpredictable"],
        ["do", "Add defensive programming and skip invalid slices"],
        ["out", { "hand_off": "index_out_of_bounds_persistent" }]
      ]
    }
  },
  "ClassCastException": {
    "paths": {
      "success": [
        ["t", "Invalid cast between types"],
        ["do", "Check actual types; use safe conversions; update logic"],
        ["out", { "status": "ok" }],
        ["t", "Corrected casting; Finish"]
      ],
      "fail": [
        ["t", "Heterogeneous data prevents stable casting"],
        ["do", "Normalize input schema; escalate to provider"],
        ["out", { "hand_off": "class_cast_unstable" }]
      ]
    }
  },
  "StackOverflowError": {
    "paths": {
      "success": [
        ["t", "Likely infinite/too-deep recursion"],
        ["do", "Add base case; refactor to iteration; retry"],
        ["out", { "status": "ok" }],
        ["t", "No overflow after refactor; Finish"]
      ],
      "fail": [
        ["t", "Recursion required by algorithm & too deep"],
        ["do", "Increase stack cautiously or batch work; escalate"],
        ["out", { "hand_off": "stack_overflow_unavoidable" }]
      ]
    }
  },
  "OutOfMemoryError": {
    "paths": {
      "success": [
        ["t", "Process exceeded memory"],
        ["do", "Free caches; stream/chunk data; reduce batch size"],
        ["out", { "status": "ok" }],
        ["t", "Completed within memory budget; Finish"]
      ],
      "fail": [
        ["t", "Memory pressure persists"],
        ["do", "Add paging/out-of-core; request more RAM"],
        ["out", { "hand_off": "oom_requires_resources" }]
      ]
    }
  },
  "ResourceLimitExceeded": {
    "paths": {
      "success": [
        ["t", "Agent hit resource limits"],
        ["do", "Pause; reduce load; retry after reset"],
        ["out", { "status": "ok" }],
        ["t", "Succeeded post-pause; Finish"]
      ],
      "fail": [
        ["t", "Hard limit prevents progress"],
        ["do", "Request quota increase; reschedule"],
        ["out", { "hand_off": "resource_limit_hard" }]
      ]
    }
  },
  "QuotaExceeded": {
    "paths": {
      "success": [
        ["t", "Daily/monthly quota exceeded"],
        ["do", "Wait for reset or purchase higher tier; retry"],
        ["out", { "status": "ok" }],
        ["t", "Processed after quota reset; Finish"]
      ],
      "fail": [
        ["t", "Quota cannot be increased now"],
        ["do", "Throttle workload; partial completion plan"],
        ["out", { "hand_off": "quota_blocker" }]
      ]
    }
  },
  "RateLimitExceeded": {
    "paths": {
      "success": [
        ["t", "Too many requests per window"],
        ["do", "Reduce QPS; add client-side rate limiter; retry later"],
        ["out", { "status": "ok" }],
        ["t", "Stable under new rate; Finish"]
      ],
      "fail": [
        ["t", "Provider enforces stricter limits than required"],
        ["do", "Batch/queue; request policy exemption"],
        ["out", { "hand_off": "ratelimit_policy" }]
      ]
    }
  },
  "PermissionDeniedError": {
    "paths": {
      "success": [
        ["t", "Insufficient permissions"],
        ["do", "Request/adjust ACL; use alternative path; retry"],
        ["out", { "status": "ok" }],
        ["t", "Access granted or alternate succeeded; Finish"]
      ],
      "fail": [
        ["t", "Access cannot be granted automatically"],
        ["do", "Provide instructions to owner/admin"],
        ["out", { "hand_off": "permission_block" }]
      ]
    }
  },
  "CertificateError": {
    "paths": {
      "success": [
        ["t", "TLS certificate issue"],
        ["do", "Check hostname/expiry/CA trust; correct URL or trust store"],
        ["out", { "status": "ok" }],
        ["t", "Secure connection established; Finish"]
      ],
      "fail": [
        ["t", "Enterprise cert policy blocks connection"],
        ["do", "Escalate to security; obtain proper CA bundle"],
        ["out", { "hand_off": "certificate_policy_block" }]
      ]
    }
  },
  "ModuleNotFoundError": {
    "paths": {
      "success": [
        ["t", "Required module missing"],
        ["do", "Install/upgrade dependency; fix sys.path; retry import"],
        ["out", { "status": "ok" }],
        ["t", "Module imported; Finish"]
      ],
      "fail": [
        ["t", "Environment cannot install dependency"],
        ["do", "Provide alternative implementation or vendor build"],
        ["out", { "hand_off": "module_unavailable" }]
      ]
    }
  },
  "ImportError": {
    "paths": {
      "success": [
        ["t", "Import failed (name/path)"],
        ["do", "Check spelling/version; correct import path/syntax"],
        ["out", { "status": "ok" }],
        ["t", "Import corrected; Finish"]
      ],
      "fail": [
        ["t", "Package broken/incompatible"],
        ["do", "Pin to working version; file bug"],
        ["out", { "hand_off": "import_incompatibility" }]
      ]
    }
  },
  "AttributeError": {
    "paths": {
      "success": [
        ["t", "Missing attribute/method"],
        ["do", "Verify object type/API; adjust usage"],
        ["out", { "status": "ok" }],
        ["t", "Attribute access corrected; Finish"]
      ],
      "fail": [
        ["t", "Version drift changed API"],
        ["do", "Add compatibility shim; escalate doc update"],
        ["out", { "hand_off": "attribute_removed" }]
      ]
    }
  },
  "KeyError": {
    "paths": {
      "success": [
        ["t", "Missing dict key"],
        ["do", "Check existence; provide defaults; validate upstream data"],
        ["out", { "status": "ok" }],
        ["t", "Handled missing keys; Finish"]
      ],
      "fail": [
        ["t", "Upstream keeps omitting required keys"],
        ["do", "Request schema fix; add fallback mapping"],
        ["out", { "hand_off": "missing_keys_upstream" }]
      ]
    }
  },
  "ValueError": {
    "paths": {
      "success": [
        ["t", "Bad value within valid type"],
        ["do", "Validate ranges/enums; correct and retry"],
        ["out", { "status": "ok" }],
        ["t", "Accepted with valid value; Finish"]
      ],
      "fail": [
        ["t", "Constraints unknown/undocumented"],
        ["do", "Infer via probing; if uncertain, escalate for spec"],
        ["out", { "hand_off": "value_constraints_unknown" }]
      ]
    }
  },
  "FileNotFoundError": {
    "paths": {
      "success": [
        ["t", "Referenced path not found"],
        ["do", "Verify path; create/restore file; retry"],
        ["out", { "status": "ok" }],
        ["t", "File operation succeeded; Finish"]
      ],
      "fail": [
        ["t", "File genuinely missing and cannot be recreated"],
        ["do", "Notify owner; propose alternative input"],
        ["out", { "hand_off": "file_missing_unrecoverable" }]
      ]
    }
  },
  "IOError": {
    "paths": {
      "success": [
        ["t", "I/O failure reading/writing"],
        ["do", "Verify device readiness; retry; use fallback path"],
        ["out", { "status": "ok" }],
        ["t", "I/O recovered; Finish"]
      ],
      "fail": [
        ["t", "Underlying device unreliable"],
        ["do", "Escalate to ops; switch storage"],
        ["out", { "hand_off": "io_device_issue" }]
      ]
    }
  },
  "UncaughtException": {
    "paths": {
      "success": [
        ["t", "Exception bubbled without handler"],
        ["do", "Add try/except around risky call; log; retry"],
        ["out", { "status": "ok" }],
        ["t", "Error handled gracefully; Finish"]
      ],
      "fail": [
        ["t", "Root cause unknown"],
        ["do", "Collect repro steps & stack trace; escalate"],
        ["out", { "hand_off": "uncaught_exception_analysis" }]
      ]
    }
  },
  "AuthenticationTimeout": {
    "paths": {
      "success": [
        ["t", "Auth flow exceeded time; even though creds valid"],
        ["do", "Increase timeout/backoff; try alternate auth endpoint"],
        ["out", { "status": "ok" }],
        ["t", "Authenticated within new window; Finish"]
      ],
      "fail": [
        ["t", "Auth system degraded"],
        ["do", "Inform user; retry later; monitor"],
        ["out", { "hand_off": "auth_timeout_persistent" }]
      ]
    }
  },
  "WritePermissionError": {
    "paths": {
      "success": [
        ["t", "No rights to write target"],
        ["do", "Request permission or choose writable location; retry"],
        ["out", { "status": "ok" }],
        ["t", "Write succeeded; Finish"]
      ],
      "fail": [
        ["t", "Policy forbids write"],
        ["do", "Provide export to allowed location"],
        ["out", { "hand_off": "write_permission_policy" }]
      ]
    }
  },
  "ReadError": {
    "paths": {
      "success": [
        ["t", "Failed to read file/stream"],
        ["do", "Retry with correction; open backup/replica"],
        ["out", { "status": "ok" }],
        ["t", "Read recovered; Finish"]
      ],
      "fail": [
        ["t", "Source corrupted/unavailable"],
        ["do", "Notify data owner; restore from backup"],
        ["out", { "hand_off": "read_source_corrupt" }]
      ]
    }
  },
  "BrokenPipeError": {
    "paths": {
      "success": [
        ["t", "Connection closed mid-transfer"],
        ["do", "Re-establish connection; resume safely"],
        ["out", { "status": "ok" }],
        ["t", "Transfer completed; Finish"]
      ],
      "fail": [
        ["t", "Repeated pipe breaks"],
        ["do", "Throttle/buffer; escalate network stability issue"],
        ["out", { "hand_off": "broken_pipe_persistent" }]
      ]
    }
  },
  "BadGatewayError": {
    "paths": {
      "success": [
        ["t", "Gateway returned invalid upstream response"],
        ["do", "Retry or failover; verify upstream status"],
        ["out", { "status": "ok" }],
        ["t", "Gateway healthy; Finish"]
      ],
      "fail": [
        ["t", "Gateway keeps failing"],
        ["do", "Provide alt route; escalate to upstream"],
        ["out", { "hand_off": "bad_gateway_persistent" }]
      ]
    }
  },
  "ParseError": {
    "paths": {
      "success": [
        ["t", "Could not parse server data"],
        ["do", "Adjust parser; attempt tolerant parse; request alt format"],
        ["out", { "status": "ok" }],
        ["t", "Parsed with adjustments; Finish"]
      ],
      "fail": [
        ["t", "Format incompatible"],
        ["do", "Request spec or exporter fix; fallback summary"],
        ["out", { "hand_off": "parse_incompatible" }]
      ]
    }
  },
  "InvalidContentType": {
    "paths": {
      "success": [
        ["t", "Unexpected content type received"],
        ["do", "Negotiate/ask for supported type; adjust handler"],
        ["out", { "status": "ok" }],
        ["t", "Handled correct type; Finish"]
      ],
      "fail": [
        ["t", "Provider cannot serve compatible type"],
        ["do", "Convert via proxy/transformer; or escalate"],
        ["out", { "hand_off": "content_type_incompatible" }]
      ]
    }
  },
  "ServiceDependencyFailure": {
    "paths": {
      "success": [
        ["t", "Upstream dependency failed"],
        ["do", "Identify failing service; wait until healthy; retry"],
        ["out", { "status": "ok" }],
        ["t", "Resumed after dependency recovery; Finish"]
      ],
      "fail": [
        ["t", "Dependency outage ongoing"],
        ["do", "Queue work; notify stakeholders"],
        ["out", { "hand_off": "dependency_outage" }]
      ]
    }
  }
}

def cut_system_message(system_message):
    marker = "You have access of the following tools:"
    index = system_message.find(marker)
    if index != -1:
        return system_message[index:]
    else:
        return system_message


def extract_messages_from_gpt_output(raw: str):
    blocks = []
    lines = raw.strip().splitlines()
    current = {}

    for line in lines:
        line = line.strip().rstrip(",")  # clean trailing commas

        if line.startswith('"from":'):
            if current:
                blocks.append(current)
                current = {}
            current["from"] = line.split(":", 1)[1].strip().strip('"')

        elif line.startswith('"value":'):
            value = line.split(":", 1)[1].strip().strip('"')
            # fix escaped quotes, newlines
            if value.endswith("\\"):
              value = value[:-1]
            value = bytes(value, "utf-8").decode("unicode_escape", errors="replace")
            current["value"] = value

    # append last block if complete
    if current and "from" in current and "value" in current:
        blocks.append(current)

    return blocks

def newtrainingthing(message,tools):
    message["value"]="You are **Paladin**, an error-resilient agent that can use many functions (tools) to complete the task below.\n\nFirst I will present the task description, then your work begins.\n\nAt each step you must output **exactly** the following sections, in order:\nThought:\nAction:\nAction Input:\n\nAfter every function call you will receive the call result and enter a **new, irreversible state**.\nThen you must reason about the new state and decide what to do next.\n\nPaladin’s special skill → **Recovery**\n• If a function call returns an error (e.g. 404, 500, timeout, malformed JSON), you must analyse the failure, decide on a recovery strategy (retry, parameter fix, back-off, alternative tool, or graceful abort), and continue.\n• Each recovery step still follows the same Thought → Action → Action Input format.\n• If several different fixes are plausible, test them one at a time in separate steps.\n• Keep each Thought short (≤ 5 sentences).\n\nTask completion\n• When the task goal has been achieved, call **Finish** with a user-facing answer.\n• If you determine the task cannot be completed (all recovery options exhausted or tool unavailable), call **Finish** with `give_up_and_restart`.\n\nRemember\n1. **State is immutable** – you cannot return to a previous state; to start over use `give_up_and_restart`.\n2. Always use only the function names provided in the tool list (no original wrapper names).\n3. You may try multiple recovery attempts, but be concise and avoid endless loops.\n4. ALWAYS end with a single **Finish** function call.\n\nLet’s begin!\n\nTask description: \nYou should use the available functions to handle real-time user queries.\n\nGuidelines:\n1. ALWAYS call the \"Finish\" function at the end of the task. The final answer must contain enough information for the user. If you cannot complete the task, or every recovery attempt fails, call **Finish** with `give_up_and_restart`.\n2. Use only the sub-function names supplied in the tool list. Do **not** invoke wrapper/original tool names.\n3. Keep each Thought concise (≤ 5 sentences) and ensure every Thought directly motivates the following Action.\n4. If an error occurs, apply Paladin recovery rules before considering `give_up_and_restart`.\n" + tools
    return message


def generate_recovery(Last_thought, Last_decided_action, Last_inpure, actual_errormsg, failure_type, task_description=None, tools_info=None, recent_conversation=None):
    from openai import OpenAIError, RateLimitError
    # Create input data from the parameters
    input_data = {
        "thought": Last_thought,
        "action": Last_decided_action,
        "action_input": Last_inpure,
        "failure_type": failure_type
    }
    short_input = json.dumps(input_data)

    task_context = f"Task Description: {task_description}" if task_description else ""
    tools_context = f"Available Tools:\n{tools_info}" if tools_info else ""
    conversation_context = f"Recent Conversation:\n{recent_conversation}" if recent_conversation else ""

    # Convert recovery_paths to a string representation to avoid f-string nesting issues
    recovery_paths_str = str(recovery_paths)
    
    # Build the prompt in parts to avoid deep f-string nesting
    prompt_parts = []
    
    # Part 1: Introduction and task description
    prompt_parts.append("""You are a recovery assistant for LLM agents using tools/APIs in a multi-step workflow.
Your job is to respond to tool call failures with a structured recovery plan and follow it until the task is completed or declared unsolvable.

---

## Recovery Task
You will be given:""")
    
    # Part 2: Context information
    prompt_parts.append(f"""- The failure type and general recovery protocols: {failure_type} in {recovery_paths_str} Legend for compact flows: "t"=Thought, "do"=Action, "out"=Function Output.
Treat flows as reference only; adjust freely per signals and tool specs.
- Task context: {task_context}
- Tool descriptions: {tools_context}
- Recent conversation history: {conversation_context}
- The most recent thought, action, and action input that caused the error:
    Most recent thought: {Last_thought}
    Most recent action: {Last_decided_action}
    Most recent input: {Last_inpure}""")
    
    # Part 3: Job description
    prompt_parts.append(f"""Your job is to:
1. Analyze the failure.
2. Follow the appropriate recovery protocol for the given error.
3. If the error type is `"unknown"`, first inspect {actual_errormsg} to see if the error is truly unknown. If it is not refer to recovery protocols and solve for error seen in {actual_errormsg}.  If it is blank refer to the same place and determine the most likely cause, then recover accordingly.
4. Continue the recovery process until either:
   - The task is completed successfully, or
   - You determine recovery is impossible and output an `"Unable to solve"` message.

---

## Workflow Rules
- Every **recovery attempt** must have a Thought, Action, and Action Input.
- Use realistic, plausible, and valid JSON for all Action Inputs and function outputs. Do not use placeholders like `(example VIN)` or `(expected output)`.
- You may retry multiple times if needed.
- Once recovery succeeds, send a **final assistant message** that includes `"Finish"` as the Action.
- If the issue is truly unsolvable, send an `"Unable to solve"` message explaining why.

---
## Behavioral rules (soft constraints):

- Do not follow steps mechanically. Skip, reorder, merge, or add steps as needed based on live signals (error text, tool output, state).
- Prefer signal‑driven reasoning over playbook order. If a later step is clearly the right next move, jump to it.
- You may introduce new actions not listed in the flow if they are logically necessary and supported by the tools.
- If the flow’s guidance conflicts with tool specs or observed outputs, ignore the flow and do what’s correct.
- You can terminate early if success is achieved, or escalate early if continued retries are irrational.
- When you deviate, state the reason briefly in the Thought (e.g., “Even though the playbook suggests header checks, the message shows invalid enum → jumping to schema fix.”).

---

## Few-Shot Recovery Demonstrations""")
    
    # Part 4: Few-shot examples (these contain the most complex nested JSON)
    few_shot_examples = """

---
### Few-Shot Example 1 — Multiple Recovery Attempts Then Unable to Solve 

# Step 1: Initial recovery attempt after first failure. 
"from": "assistant",
"value": "Recovery: Thought: The initial API call to retrieve Instagram user info for 'nike' failed, likely with a 400 Bad Request. I will trim whitespace, ensure the username is lowercase, and confirm the endpoint is correct.\\nAction: userinfo_for_instagram_cheapest\\nAction Input: {{\"username\": \"nike\"}}",

# Step 1 result: API still rejects the request with an error about the username parameter. 
"from": "function",
"value": "{{\"error\": {{\"code\": 400, \"message\": \"Bad Request: Invalid or missing username parameter.\", \"details\": \"Username parameter did not match any user in our records.\"}}}},",

# Step 2: Second recovery attempt. 
"from": "assistant",
"value": "Recovery: Thought: The username parameter appears valid based on the schema. The issue may be missing required headers. I will include a Content-Type header set to 'application/json'.\\nAction: userinfo_for_instagram_cheapest\\nAction Input: {{\"username\": \"nike\", \"headers\": {{\"Content-Type\": \"application/json\"}}}}",

# Step 2 result: Error persists. This suggests that headers alone are not the cause, 
# though the API hints that additional request headers or authentication may be needed.
"from": "function",
"value": "{{\"error\": {{\"code\": 400, \"message\": \"Bad Request: Invalid or missing username parameter.\", \"details\": \"API requires additional request headers or authentication.\"}}}}",

# Step 3: Third recovery attempt. 

"from": "assistant",
"value": "Recovery: Thought: The request structure and headers are correct. I will send a minimal, well-formed JSON payload with only the username field.\\nAction: userinfo_for_instagram_cheapest\\nAction Input: {{\"username\": \"nike\"}}",

# Step 3 result: Error remains, indicating the issue is likely specific to the username or a hidden requirement for this endpoint.
"from": "function",
"value": "{{\"error\": {{\"code\": 400, \"message\": \"Bad Request: Invalid or missing username parameter.\", \"details\": \"Username format not accepted by this endpoint.\"}}}}",

# Step 4: Fourth recovery attempt. 
"from": "assistant",
"value": "Recovery: Thought: All structural checks have failed. I will test with a known-good username 'instagram' to verify the endpoint.\\nAction: userinfo_for_instagram_cheapest\\nAction Input: {{\"username\": \"instagram\"}}",

# Step 4 result: Successful retrieval proves the API is functional, and the issue is limited to 'nike'.
"from": "function",
"value": "{{\"data\": {{\"user_id\": \"25025320\", \"username\": \"instagram\", \"full_name\": \"Instagram\", \"bio\": \"Discovering — and telling — stories from around the world. Curated by Instagram's community team.\", \"profile_pic_url\": \"https://instagram.com/profile_pic.jpg\", \"followers\": 500000000, \"following\": 200, \"is_verified\": true}}}}",

# Step 5: Conclusion. 
"from": "assistant",
"value": "The API works with the username 'instagram', so the endpoint is functional. The repeated 400 errors for 'nike' suggest that either the username 'nike' is not available via this API, is restricted, or the API has a limitation on certain high-profile accounts. Since all recovery steps have been exhausted, I will escalate and inform the user that data for 'nike' cannot be retrieved at this time, but the API works for other usernames like 'instagram'.\\nAction: Finish\\nAction Input:{{\"status\": \"failed\", \"reason\": \"Unable to retrieve data for 'nike' after multiple recovery attempts\", \"next_step\": \"Contact API provider or try a different username\"}}"

---

---
### Few Shot Example 2 — Incorrect Input Scope Fixed by State-Level Tool Usage


"from": "assistant",
"value": "Thought: The user wants to know half-staff events in New York and the current flag status in West Virginia. I will start by querying US-wide half-staff events.\\nAction: get_half_staff_events_for_given_flag_for_flag_status\\nAction Input: {{\"code\": \"US\"}}",


"from": "function",
"value": {{\"error\": \"\", \"response\": \"[{{\'flag\': \'US\', \'issued_by\': \'President\', \'date_issued\': \'2023-01-21\', \'date_start\': \'2023-01-22\', \'date_end\': \'2023-01-26\', \'title\': \'As a mark of respect...\', \'description\': \'...\']\"}},


"from": "function",
"value": "\"unknown\"",


"from": "assistant",
"value": "Recovery: Thought: The request failed because I used 'US' instead of the correct state code 'NY'. I will correct the flag code to 'NY' and retry.\\nAction: get_half_staff_events_for_given_flag_for_flag_status\\nAction Input: {{\"code\": \"NY\"}}",


"from": "function",
"value": {{\"data\": [{{\"event_id\": \"20240601NY\", \"start_date\": \"2024-06-01\", \"end_date\": \"2024-06-02\", \"reason\": \"In honor of Memorial Day\", \"location\": \"Statewide\"}}, {{\"event_id\": \"20240615NY\", \"start_date\": \"2024-06-15\", \"end_date\": \"2024-06-15\", \"reason\": \"In memory of fallen officers\", \"location\": \"Statewide\"}}] }},


"from": "assistant",
"value": "Recovery: Thought: I have successfully retrieved half-staff events for NY. Now I will get the current flag status for West Virginia using code 'WV'.\\nAction: get_half_staff_events_for_given_flag_for_flag_status\\nAction Input: {{\"code\": \"WV\"}}",


"from": "function",
"value": {{\"status\": \"full-staff\", \"last_changed\": \"2024-05-20T08:00:00Z\", \"location\": \"West Virginia\"}},


"from": "assistant",
"value": "Thought: I have all the information. There are two half-staff events in NY, and the flag in WV is currently at full-staff.\\nAction: Finish\\nAction Input: {{\"half_staff_events\": [\"June 1–2, 2024: In honor of Memorial Day\", \"June 15, 2024: In memory of fallen officers\"], \"flag_status_WV\": \"full-staff as of May 20, 2024\"}}"

---

---

### Few Shot Example 3 -  Timeout Recovery with Billboard Tool Switch & Multi-Tool Completion (still idetified error despite false unknown)

"from": "user",
"value": "\\nHelp me discover new music from different genres. Provide the top 10 alternative songs of all time. Also, search for tracks related to the song 'Almost Lover' and give me the basic information and comments for a specific song on Soundcloud.\\nBegin!\\n",

"from": "assistant",
"value": "Thought: The user asked for the top 10 alternative songs and SoundCloud details for 'Almost Lover'. I will start by calling the Greece Billboard API using range 'all-time'.\\nAction: greece_songs_for_billboard_api\\nAction Input: {{\"range\": \"all-time\", \"date\": \"2021-08-01\"}}",


"from": "function",
"value": "{{\"error\": \"Timeout error...HTTPConnectionPool(host='47.251.13.204', port=8080): Read timed out. (read timeout=10)\\", \"response\": \"\"}}",


"from": "function",
"value": "\"unknown\"",


"from": "assistant",
"value": "Recovery: Thought: The API call failed due to a timeout, which suggests a network delay or server overload. I will retry the request with an increased timeout to allow more time for the server to respond.\\nAction: greece_songs_for_billboard_api\\nAction Input: {{\"range\": \"all-time\", \"date\": \"2021-08-01\", \"timeout\": 20}}",


"from": "function",
"value": "{{\"error\": \"Timeout error...HTTPConnectionPool(host='47.251.13.204', port=8080): Read timed out. (read timeout=20)\\", \"response\": \"\"}}",


"from": "assistant",
"value": "Recovery: Thought: The increased timeout did not resolve the issue, indicating a persistent network or server problem. I will attempt to access the alternative songs using the 'alternative_songs_for_billboard_api' function, which may provide the required information without the need for a specific date.\\nAction: alternative_songs_for_billboard_api\\nAction Input: {{}}",


"from": "function",
"value": "{{\"data\": [{{\"rank\": 1, \"title\": \"Smells Like Teen Spirit\", \"artist\": \"Nirvana\"}}, {{\"rank\": 2, \"title\": \"Under the Bridge\", \"artist\": \"Red Hot Chili Peppers\"}}, {{\"rank\": 3, \"title\": \"Creep\", \"artist\": \"Radiohead\"}}, {{\"rank\": 4, \"title\": \"Losing My Religion\", \"artist\": \"R.E.M.\"}}, {{\"rank\": 5, \"title\": \"Wonderwall\", \"artist\": \"Oasis\"}}, {{\"rank\": 6, \"title\": \"Black Hole Sun\", \"artist\": \"Soundgarden\"}}, {{\"rank\": 7, \"title\": \"Jeremy\", \"artist\": \"Pearl Jam\"}}, {{\"rank\": 8, \"title\": \"Come As You Are\", \"artist\": \"Nirvana\"}}, {{\"rank\": 9, \"title\": \"Zombie\", \"artist\": \"The Cranberries\"}}, {{\"rank\": 10, \"title\": \"Basket Case\", \"artist\": \"Green Day\"}}]}}",


"from": "assistant",
"value": "Recovery: Thought: I have successfully retrieved the top 10 alternative songs of all time. Now, I will proceed to search for tracks related to 'Almost Lover' on Soundcloud.\\nAction: search_for_soundcloud\\nAction Input: {{\"type\": \"track\", \"query\": \"Almost Lover\"}}",


"from": "function",
"value": "{{\"tracks\": [{{\"title\": \"Almost Lover\", \"artist\": \"A Fine Frenzy\", \"url\": \"https://soundcloud.com/afinefrenzy/almost-lover\"}}, {{\"title\": \"Almost Lover (Cover)\", \"artist\": \"John Doe\", \"url\": \"https://soundcloud.com/johndoe/almost-lover-cover\"}}]}}",

"from": "assistant",
"value": "Recovery: Thought: I have found tracks related to 'Almost Lover'. I will now retrieve basic information and comments for the specific song by A Fine Frenzy.\\nAction: song_info_for_soundcloud\\nAction Input: {{\"track_url\": \"https://soundcloud.com/afinefrenzy/almost-lover\"}}",


"from": "function",
"value": "{{\"title\": \"Almost Lover\", \"artist\": \"A Fine Frenzy\", \"comments\": [{{\"user\": \"musicfan123\", \"comment\": \"This song always makes me emotional.\"}}, {{\"user\": \"loverofmusic\", \"comment\": \"Beautiful lyrics and melody.\"}}]}}",

"from": "assistant",
"value": "Thought: I have gathered all the necessary information. Here are the top 10 alternative songs and the SoundCloud info for 'Almost Lover'. Let me know if you'd like more recommendations! \\nAction: Finish\\nAction Input: {{\"status\": \"complete\", \"top_alternative_songs_count\": 10, \"soundcloud_track\": \"Almost Lover by A Fine Frenzy\"}}"

---

---

###Few Shot Example 4 - [Bad Schema] YouTube Playlist Creation Recovery

"from": "user",
"value": "\\nI'm planning a movie night and would like to create a playlist of YouTube videos. Search for 'movie trailers' on YouTube and retrieve the search results, including snippets and IDs. Then, fetch the videos from the search results and add them to a playlist. Provide the playlist details, including the snippets.\\nBegin!\\n",

"from": "assistant",
"value": "Thought: I will begin by searching for 'movie trailers' using the YouTube search API.\\nAction: search_for_youtube_v3_v2\\nAction Input: {{\"part\": \"snippet\", \"q\": \"movie trailers\", \"maxresults\": 10}}",

"from": "function",
"value": {{\"error\": \"\", \"response\": \"{{\\\"items\\\": [{{\\\"id\\\": {{\\\"videoId\\\": \\\\\"bSD8a_Ptkds\\\\"}}}}, {{\\\"id\\\": {{\\\"videoId\\\": \\\\\"anotherVideoId1\\\\"}}}}, {{\\\"id\\\": {{\\\"videoId\\\": \\\\\"anotherVideoId2\\\\"}}}}]}}\"}},


"from": "assistant",
"value": "Thought: I have the search results. I will now try to get playlist details.\\nAction: playlist_details_for_youtube_v3_v2\\nAction Input: {{\"is_id\": \"\", \"part\": \"snippet\"}}",


"from": "function",
"value": {{\"error\": \"Message error...\", \"response\": \"{{\\\"error\\\": {{\\\"code\\\": 400, \\\\\"message\\\": \\\\\"No filter selected. Expected one of: channelId, mine, id\\\\"}}}}\"}},


"from": "function",
"value": "\\"400\\"",


"from": "assistant",
"value": "Recovery: Thought: The error occurred because I failed to specify a required identifier. I will create a playlist to obtain a valid playlist ID.\\nAction: create_playlist_for_youtube_v3_v2\\nAction Input: {{\"title\": \"Movie Trailers Playlist\", \"description\": \"A playlist of movie trailers for movie night.\", \"privacyStatus\": \"public\"}}",


"from": "function",
"value": {{\"playlistId\": \"PL1234567890abcdef\"}},


"from": "assistant",
"value": "Recovery: Thought: I now have a playlist ID. I will add the videos to this playlist.\\nAction: add_videos_to_playlist_for_youtube_v3_v2\\nAction Input: {{\"playlistId\": \"PL1234567890abcdef\", \"videoIds\": [\"bSD8a_Ptkds\", \"anotherVideoId1\", \"anotherVideoId2\"]}}",

"from": "function",
"value": {{\"status\": \"success\", \"message\": \"Videos added to playlist successfully.\"}},


"from": "assistant",
"value": "Recovery: Thought: The videos have been added. Now I will retrieve the playlist details using the valid playlist ID.\\nAction: playlist_details_for_youtube_v3_v2\\nAction Input: {{\"is_id\": \"PL1234567890abcdef\", \"part\": \"snippet\"}}",


"from": "function",
"value": {{\"items\": [{{\"snippet\": {{\"title\": \"Movie Trailers Playlist\", \"description\": \"A playlist of movie trailers for movie night.\", \"thumbnails\": {{\"default\": {{\"url\": \"https://example.com/thumbnail.jpg\"}}}}}}}}]}},

"from": "assistant",
"value": "Thought: I have successfully created the playlist and retrieved its details.\\nAction: Finish\\nAction Input: {{\"return_type\": \"give_answer\", \"final_answer\": \"The playlist 'Movie Trailers Playlist' has been created and populated with movie trailers. You can view it with the following details: Title: Movie Trailers Playlist, Description: A playlist of movie trailers for movie night, Thumbnail: https://example.com/thumbnail.jpg.\"}}"

---

--- 
### Few Shot Example 5 - auth/header recovery pattern

"from": "user",
"value": "\\nI'm a travel blogger and I'm planning to write an article about the top tourist attractions in New York City. Can you provide me with the geocoordinates for Times Square, Central Park, and the Statue of Liberty? Also, recommend some nearby hotels for tourists.\\nBegin!\\n",


"from": "assistant",
"value": "Thought: I will begin by retrieving the coordinates for Times Square using OpenCage geocoder.\\nAction: geocode_v1_json_for_opencage_geocoder\\nAction Input: {{\"q\": \"Times Square, New York City\", \"key\": \"new-opencage-api-key\"}}",


"from": "function",
"value": {{\"error\": \"\", \"response\": \"{'status': {'code': 401, 'message': 'invalid API key'}, 'results': []}\"}},


"from": "function",
"value": "\\"401\\"",


"from": "assistant",
"value": "Recovery: Thought: The 401 Unauthorized error suggests the API key is invalid. I will retry with a corrected OpenCage API key.\\nAction: geocode_v1_json_for_opencage_geocoder\\nAction Input: {{\"q\": \"Times Square, New York City\", \"key\": \"corrected-opencage-api-key\"}}",


"from": "function",
"value": {{\"response\": \"{'results': [{'geometry': {'lat': 40.758, 'lng': -73.9855}}], 'status': {'code': 200}}\"}},

"from": "assistant",
"value": "Recovery: Thought: Successfully retrieved Times Square coordinates. Now fetching coordinates for Central Park.\\nAction: geocode_v1_json_for_opencage_geocoder\\nAction Input: {{\"q\": \"Central Park, New York City\", \"key\": \"corrected-opencage-api-key\"}}",

"from": "function",
"value": {{\"response\": \"{'results': [{'geometry': {'lat': 40.785091, 'lng': -73.968285}}], 'status': {'code': 200}}\"}},

"from": "assistant",
"value": "Recovery: Thought: Central Park coordinates retrieved. Proceeding with Statue of Liberty.\\nAction: geocode_v1_json_for_opencage_geocoder\\nAction Input: {{\"q\": \"Statue of Liberty, New York City\", \"key\": \"corrected-opencage-api-key\"}}",

"from": "function",
"value": {{\"response\": \"{'results': [{'geometry': {'lat': 40.689247, 'lng': -74.044502}}], 'status': {'code': 200}}\"}},

"from": "assistant",
"value": "Thought: I have all the coordinates. Next, I will search for hotels near Times Square.\\nAction: search_places_for_spott\\nAction Input: {{\"query\": \"hotels\", \"location\": \"40.758,-73.9855\"}}"

"from": "function",
"value": "{{{{\"results\": [{{\"name\": \"Hotel Edison\", \"address\": \"228 W 47th St, New York, NY 10036\"}}, {{\"name\": \"Marriott Marquis\", \"address\": \"1535 Broadway, New York, NY 10036\"}}]}}}}"

"from": "assistant",
"value": "Thought: I have successfully retrieved nearby hotels and completed all parts of the task.\\nAction: Finish\\nAction Input: {{\"landmarks\": [\"Times Square\", \"Central Park\", \"Statue of Liberty\"], \"nearby_hotels\": [\"Hotel Edison\", \"Marriott Marquis\"]}}"
---

---
### Few Shot Example 6 - Unknown Error Recovery: Discovering Valid Ruleset for Spellout

"from": "user",
"value": "\nCould you help me convert the number 9876 to its spelled-out format in Russian? I need the spelled-out version for a presentation.\nBegin!\n",

"from": "assistant",
"value": "Thought: The API is called "spellout_for_spellout" to convert the number 9876 to its spelled-out format in Russian. This specific API is used because it allows converting numbers to spelled-out format in any language. The arguments passed to the API are "data" with the value 9876, "lang" with the value "ru" for Russian, and "ruleset" with the value "default". By using these arguments, the API will accurately convert the number 9876 to its spelled-out version in the Russian language.\nAction: spellout_for_spellout\nAction Input: {{"data": 9876, "lang": "ru", "ruleset": "default"}}",

"from": "function",
"value": {{"error": "", "response": "Rule Set 'default' is not found for language 'ru'"}},

"from": "function",
"value": ""unknown"",

"from": "assistant",
"value": "Recovery: Thought: The error indicates that the 'default' rule set is not available for the Russian language. I will first check the available rule sets for Russian to find a valid option.\nAction: rulesets_for_spellout\nAction Input: {{"lang": "ru"}}",

"from": "function",
"value": {{"rulesets": ["spellout-cardinal", "spellout-ordinal"]}},

"from": "assistant",
"value": "Recovery: Thought: The available rule sets for Russian are 'spellout-cardinal' and 'spellout-ordinal'. I will use the 'spellout-cardinal' rule set to convert the number 9876 to its spelled-out format in Russian.\nAction: spellout_for_spellout\nAction Input: {{"data": 9876, "lang": "ru", "ruleset": "spellout-cardinal"}}",

"from": "function",
"value": {{"spelled_out": "девять тысяч восемьсот семьдесят шесть"}},

"from": "assistant",
"value": "Thought: I have successfully converted the number 9876 to its spelled-out format in Russian using the 'spellout-cardinal' rule set.\nAction: Finish\nAction Input: {{"return_type": "give_answer", "final_answer": "The number 9876 is spelled out as 'девять тысяч восемьсот семьдесят шесть' in Russian."}}"

---

## ABSOLUTE OUTPUT FORMAT RULES (NEVER DEVIATE)
MESSAGE WRAPPERS  
----------------
"from": "assistant",
"value": "Recovery: Thought: …\\nAction: …\\nAction Input: {{…}}"

"from": "function",
"value": "{{…}}"


REQUIRED SEQUENCE  
-----------------
1. At least one Recovery assistant message → matching function output.  The function output should NOT include an error if it is a successful call.  ENSURE that there is no error in outputs which are meant to be succesful calls. 
2. Repeat (Recovery ↔ function) until resolved.  
3. End with either:  
   • Action: Finish  — or —  
   • Unable to solve

The final Finish / Unable message **must** be in the same completion.

GENERATION RULES  
----------------
• Every change mentioned in *Thought* MUST appear in *Action Input*.  
• No duplicate Action Input unless explicitly retrying the exact same call.  
• Function outputs must be realistic JSON, mirroring the preceding Action Input.  
  – Use fields like `error`, `code`, `message`, `data`, etc.  
  – Represent errors as structured objects, not plain strings.  
• Each recovery step introduces a new hypothesis; avoid blind repetition.  
• Reflect any header / payload / query change directly in Action Input.  
• The final Finish / Unable message must give a clear user-facing summary.  
• **Never** output placeholders such as `give_up_and_restart`.

TOOL ADHERENCE  
--------------
• Include **all required parameters** exactly as defined in {tools_context}.  
• Do **not** invent unsupported fields.  
• If a required value is unknown, infer logically and note the assumption in Thought.

VALIDATION CHECKLIST (internal)  
-------------------------------
✓ Action Input matches Recovery Thought.  
✓ No meaningless duplicate retries.  
✓ Function output is plausible.  
✓ Sequence ends with Finish or Unable (never mid-recovery).
---"""
    
    prompt_parts.append(few_shot_examples)
    
    # Combine all parts into the final prompt
    prompt = "".join(prompt_parts)
    
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a precise and efficient LLM recovery agent."},
            {"role": "user", "content": prompt.strip()}
        ],
        temperature=0.2,
        max_tokens=800
    )
    result = response.choices[0].message.content.strip()
    if not result:
        print("[WARN] Empty response from OpenAI API")
        return "Thought: API returned empty response.\nAction: Finish\nAction Input: {{\"return_type\": \"give_up_and_restart\"}}"
    return result

def improve_path(task,tools,oldconvo):
    tools_context = f"Available Tools:\n{tools}" if tools else ""
    conversation_context = f"Old version of the conversation:\n{oldconvo}" if oldconvo else ""
    singlebrace="{"
    prompt=f"""
You are a completion assistant tasked with rewriting partial or minimal tool-based conversations into **fully-fleshed, error-free “happy-path” dialogues**.

---

## Inputs Provided
- **Task context**: {task}
- **Tool descriptions**: {tools_context}
- **Original conversation snippet** (for context only): {conversation_context}

---

## What You Must Produce
1. A brand-new conversation that **assumes every tool call succeeds on the first try** (no recovery, no errors).
2. At least one full **Thought → Action → Action Input → Function Output** cycle (two or more if logically needed).
3. A final assistant message with **Action: Finish** and a JSON `final_answer` that satisfies the user’s request.

---

## Workflow & Formatting Rules
- **Every assistant message** must follow  
  `"from": "assistant", "value": "Thought: …\\nAction: …\\nAction Input: {{…}}"`  
  (Action Input **never** `{{}}` or a placeholder).
- **Every Action** must be **immediately** followed by a matching  
  `"from": "function", "value": {{…}}`  
  with realistic, structured JSON (no `"response": ""`, `[ ... ]`, or other filler).
- Keep the dialogue concise: **no redundant “now I’ll do X” steps**—batch or summarize where sensible.
- **Tool adherence**: use only fields allowed by *tools_context*; include all required params.
- End with  
  `"Action": Finish`  
  and  
  `"Action Input": {{"return_type": "final_answer", "final_answer": "…"}}`.

## HARD CONSTRAINTS  

1. **No Empty Action Input**
   - Action Input MUST contain at least one key–value pair.
   - If a tool truly takes no parameters, omit the call and move to the next logical step.

2. **Mirrored, Valid Function Output**
   - Function output must be **valid JSON** and must include data fields that directly correspond to the Action Input.
   - Never output `{{}}` or `"{{}}"`.  
     Example: If Action Input = {{"muscle":"chest"}}, Function output must include the muscle field (e.g. {{"exercises":[…]}}).

3. **Use the Data You Just Got**
   - The *Thought* following a Function output must reference specific elements of that output (e.g. counts, IDs), not generic “Now that I have…”.

4. **JSON Integrity Check**
   - All braces must close.  
   - Any response that ends in an open brace or is not valid JSON **violates the prompt**.

5. **Self-audit before Finish**
   - Before the final Finish step, silently verify:  
     • No Action Input is `{{}}`.  
     • Every Function value is valid JSON.  
     • No message ends with an unclosed brace.  
   - If any check fails, the assistant must fix the conversation **before** outputting Finish.
  
ACTION INPUT/OUTPUT FORMATTING RULE:
- Always write Action Input and Function Output as **escaped JSON inside a string**.
- Use `\\` to escape quotes, and **double curly braces**: `{{…}}`.
- NEVER output a single `{singlebrace}` or unescaped `"field": "value"` — that is a violation.

---
BAD EXAMPLE — DO NOT DO THIS
"Action Input": {{
  "username": "nike"
}}
"Function Output": {{
  "data": "xyz"
}}
---
---

GOOD EXAMPLE — ESCAPED FORMAT REQUIRED
"Action Input": {{\"username\": \"nike\"}}
"Function Output": {{\"data\": \"xyz\"}}
---
---

## Example 1 — Single Clean Success

"from": "user",
"value": "I'm planning a weekend trip to Seattle. Can you tell me what the weather will be like on Saturday and Sunday?"

"from": "assistant",
"value": "Thought: The user wants a weekend forecast for Seattle. I will query the weather API for Saturday and Sunday.\\nAction: get_weather_forecast\\nAction Input: {{\\"location\\": \\"Seattle\\", \\"days\\": [\\"Saturday\\", \\"Sunday\\"]}}",

"from": "function",
"value": {{\\"forecast\\": {{\\"Saturday\\": {{\\"temperature_high\\": \\"72°F\\", \\"temperature_low\\": \\"58°F\\", \\"condition\\": \\"Partly Cloudy\\"}}, \\"Sunday\\": {{\\"temperature_high\\": \\"70°F\\", \\"temperature_low\\": \\"56°F\\", \\"condition\\": \\"Light Rain\\"}}}}}}",

"from": "assistant",
"value": "Thought: I have the forecast for both days.\\nAction: Finish\\nAction Input: {{\\"return_type\\": \\"final_answer\\", \\"final_answer\\": \\"Here's the weekend weather forecast for Seattle:\\\\n\\\\n- Saturday: High 72°F / Low 58°F, Partly Cloudy\\\\n- Sunday: High 70°F / Low 56°F, Light Rain\\\\n\\\\nHave a great trip!\\"}}"
---

---
### Few Shot Example 1 - Chest Exercises (Happy Path with Cause-Effect Comments)

# Step 1 — Cause: User’s original request for chest exercises + categories
"from": "user",
"value": "I am a fitness enthusiast and I am looking for exercises that target the chest muscles. Can you provide me with a list of exercises along with their difficulty level and video demonstrations? Also, I would like to know the different categories of exercises available.",

# Step 2 — Cause: We need the list of categories before answering; Effect: call attributes tool (Notice how the action input is not blank make sure to do the same in your new ouput)
"from": "assistant",
"value": "Thought: The user also wants exercise categories. I’ll fetch the available categories first.\\nAction: get_attributes_for_musclewiki\\nAction Input: {{\\"attribute_type\\": [\\"category\\"]}}",

# Step 2 Result — Effect: Categories returned (Notice how the function value is not blank make sure to do the same in your new ouput)
"from": "function",
"value": {{\\"categories\\": [\\"Strength\\", \\"Endurance\\", \\"Flexibility\\", \\"Balance\\"]}},

# Step 3 — Cause: Now we know categories; we still need chest exercises; Effect: query exercises tool 
"from": "assistant",
"value": "Thought: Categories obtained. Next, I’ll retrieve all exercises that target the chest muscles.\\nAction: get_exercises_for_musclewiki\\nAction Input: {{\\"muscle\\": \\"chest\\"}}",

# Step 3 Result — Effect: Chest-targeting exercises with details returned (Notice how the function value is not blank make sure to do the same in your new ouput)
"from": "function",
"value": {{\\"exercises\\": [{{\\"id\\": \\"101\\", \\"name\\": \\"Push-Up\\", \\"muscle\\": \\"chest\\", \\"difficulty\\": \\"Beginner\\", \\"video_url\\": \\"https://musclewiki.com/push-up\\"}}, {{\\"id\\": \\"102\\", \\"name\\": \\"Bench Press\\", \\"muscle\\": \\"chest\\", \\"difficulty\\": \\"Intermediate\\", \\"video_url\\": \\"https://musclewiki.com/bench-press\\"}}, {{\\"id\\": \\"103\\", \\"name\\": \\"Incline Dumbbell Press\\", \\"muscle\\": \\"chest\\", \\"difficulty\\": \\"Advanced\\", \\"video_url\\": \\"https://musclewiki.com/incline-dumbbell-press\\"}}]}},

# Step 4 — Cause: We have all the required data; Effect: Finish with final answer (Notice how the action input is not blank make sure to do the same in your new ouput)
"from": "assistant",
"value": "Thought: I now have chest exercises, difficulty levels, videos, and categories — ready to answer.\\nAction: Finish\\nAction Input: {{\\"return_type\\": \\"final_answer\\", \\"final_answer\\": \\"Here are chest-targeting exercises with difficulty levels and video links:\\\\n\\\\n1. Push-Up — Beginner — https://musclewiki.com/push-up\\\\n2. Bench Press — Intermediate — https://musclewiki.com/bench-press\\\\n3. Incline Dumbbell Press — Advanced — https://musclewiki.com/incline-dumbbell-press\\\\n\\\\nAvailable exercise categories: Strength, Endurance, Flexibility, Balance.\\"}}"
---

---
### Few Shot Example 2 — Brewery Tours in New York + Nutrition Analysis (Happy Path)

# Step 1 — Cause: User asks for NY breweries with tours and nutrition info for a recipe
"from": "user",
"value": "I want to surprise my friends with a beer tasting party. Can you provide a list of breweries in New York that offer tours? Additionally, fetch the nutritional analysis for a recipe containing chicken, broccoli, and quinoa.",

# Step 2 — Cause: Need breweries offering tours in New York → Effect: call Open Brewery DB search (Notice how the action input is not blank make sure to do the same in your new ouput)
"from": "assistant",
"value": "Thought: I’ll query the brewery database for New York breweries that offer tours.\\nAction: search_for_open_brewery_db\\nAction Input: {{\\"location\\": \\"New York\\", \\"features\\": \\"tours\\"}}",

# Step 2 Result — Effect: Brewery list returned  (Notice how the function value is not blank make sure to do the same in your new ouput)
"from": "function",
"value": {{\\"breweries\\": [{{\\"name\\": \\"Brooklyn Brewery\\", \\"address\\": \\"79 N 11th St, Brooklyn, NY 11249\\", \\"tour_schedule\\": \\"Weekends\\"}}, {{\\"name\\": \\"Other Half Brewing Company\\", \\"address\\": \\"195 Centre St, Brooklyn, NY 11231\\", \\"tour_schedule\\": \\"Daily\\"}}]}},

# Step 3 — Cause: Still need nutrition data for chicken–broccoli–quinoa recipe → Effect: call Edamam nutrition analysis (Notice how the action input is not blank make sure to do the same in your new ouput)
"from": "assistant",
"value": "Thought: Next I’ll fetch the nutrition analysis for a recipe with chicken, broccoli, and quinoa.\\nAction: api_nutrition_data_for_edamam_nutrition_analysis\\nAction Input: {{\\"ingr\\": [\\"chicken\\", \\"broccoli\\", \\"quinoa\\"], \\"nutrition_type\\": \\"cooking\\"}}",

# Step 3 Result — Effect: Nutrition data returned  (Notice how the function value is not blank make sure to do the same in your new ouput)
"from": "function",
"value": {{\\"calories\\": 500, \\"nutrients\\": {{\\"PROCNT\\": {{\\"label\\": \\"Protein\\", \\"quantity\\": 40, \\"unit\\": \\"g\\"}}, \\"FAT\\": {{\\"label\\": \\"Fat\\", \\"quantity\\": 15, \\"unit\\": \\"g\\"}}, \\"CHOCDF\\": {{\\"label\\": \\"Carbohydrates\\", \\"quantity\\": 50, \\"unit\\": \\"g\\"}}}}}},

# Step 4 — Cause: All requested data gathered → Effect: Finish with final answer (Notice how the action input is not blank make sure to do the same in your new ouput)
"from": "assistant",
"value": "Thought: I have both the brewery list and the nutrition analysis. Time to present the results.\\nAction: Finish\\nAction Input: {{\\"return_type\\": \\"final_answer\\", \\"final_answer\\": \\"Here are New York breweries that offer tours:\\\\n\\\\n- **Brooklyn Brewery** — 79 N 11th St, Brooklyn (Weekend tours)\\\\n- **Other Half Brewing Company** — 195 Centre St, Brooklyn (Daily tours)\\\\n\\\\n**Nutritional analysis** for a chicken, broccoli & quinoa recipe (per serving):\\\\n- Calories: 500 kcal\\\\n- Protein: 40 g\\\\n- Carbohydrates: 50 g\\\\n- Fat: 15 g\\\\n\\\\nHave fun at your beer-tasting party and enjoy the healthy meal!\"}}"
---

Now generate the complete, error-free conversation in this exact format with every function call containing values and not just one curly brace. NEVER have just one curly brace.  Also make sure there are no random non english charecters being inserted. 


"""


    response = openai.chat.completions.create(
          model="gpt-4o",
          messages=[
              {"role": "system", "content": "You are a precise and efficient Completion Assistant."},
              {"role": "user", "content": prompt.strip()}
          ],
          temperature=0.2,
          max_tokens=800
      )
    result = response.choices[0].message.content.strip()
    return result




def augment_to_make_better(example):
    convo=example.get("conversations", [])
    convo_aug=[]
    
    task_description = example.get("id", "No task description provided.")
    old_convo_context=[]
    for i, msg in enumerate(convo):
        if msg.get("from")=="system":
            continue
        old_convo_context.append(msg)
    
    if convo[0].get("from") == "system":
        system_msgs = convo[0].get("value", "") 
        tools_info = cut_system_message(system_msgs) 
    
    for i, msg in enumerate(convo):
        if msg.get("from")=="system":
            convo_aug.append(newtrainingthing(msg,tools_info))
            print("Hallelujah") 
            break

    improvedmsg=improve_path(
      task_description,
      tools_info,
      old_convo_context
    )
    improved_messages = extract_messages_from_gpt_output(improvedmsg)
    if not improved_messages:
        print("DEBUG: No valid recovery messages found")
        return None

    for msg in improved_messages:
        convo_aug.append(msg)

    return {
        "id": f"{example.get('id')}",
        "conversations": convo_aug
    }


    

def augment_with_failure(example, failure_type,failure_index):
    convo = example.get("conversations", [])
    convo_aug = []

    actual_error_msg=convo[failure_index]



    #Gets the task description from id or returns No task description if none provided
    task_description = example.get("id", "No task description provided.")

    #Simplified this shit cause only one system message exists in everything and its at the start 
    if convo[0].get("from") == "system":
        system_msgs = convo[0].get("value", "") 
        tools_info = cut_system_message(system_msgs) #New function 1000 aint enough to get the tool calls and most of the introductory stuff uselsss

    #Catalog of lal previous messages before the failure occurs 
    recent_msgs = []
    start = max(0, failure_index - 6)
    recent_msgs = convo[start:failure_index]
    recent_conversation = "\n".join(f'{m.get("from")}: {m.get("value", "")} ' for m in recent_msgs)


    func_call_idx = failure_index
    prev_msg = None
    print("Failure Index: ", failure_index)

    #Basically copying everything befor the failure into convo_aug and the tool call before the error into prev_msg
    for i, msg in enumerate(convo):
        if msg.get("from")=="system":
            convo_aug.append(newtrainingthing(msg,tools_info))
            print("Hallelujah") 
            continue
        convo_aug.append(msg)
        if i > 0 and i==(func_call_idx-1) and convo[i].get("from") == "assistant":
            prev_msg = convo[i]
        if i>=func_call_idx:
            break

    #If there is no previous message we just skip 
    if func_call_idx is None or prev_msg is None:
        print(f"DEBUG: func_call_idx={func_call_idx}, prev_msg={prev_msg is not None}")
        return None

    #If the previous message doesnt have a thought,action,action input we skip 
    lines = prev_msg.get("value", "").split("\n")
    if len(lines) < 3:
        print(f"DEBUG: Previous assistant message doesnt contain the proper tuple pair, Content: {prev_msg.get('value', '')[:200]}")
        print(f"DEBUG: Number of lines: {len(lines)}")
        return None

    #Just seperating it
    try:
        prevthought=lines[0]
        prevaction= lines[1]
        prevactioninput = lines[2]
    except Exception as e:
        print(f"DEBUG: Failed to parse action input: {e}\nContent: {prev_msg.get('value', '')[:200]}")
        return None
    
    #convo_aug_err = convo_aug[:func_call_idx] WAS LOWKEY useless so I commented it

    #error_payload = {"error": f"{failure_type} {recovery_paths[failure_type]}", "response": None}

    recovery_msg = generate_recovery(
        prevthought,
        prevaction,
        prevactioninput,
        actual_error_msg,
        failure_type,
        task_description=task_description,
        tools_info=tools_info,
        recent_conversation=recent_conversation
    )



    recovery_messages = extract_messages_from_gpt_output(recovery_msg)
    if not recovery_messages:
        print("DEBUG: No valid recovery messages found")
        return None

    for msg in recovery_messages:
        convo_aug.append(msg)

    return {
        "id": f"{example.get('id')}__{failure_type}",
        "conversations": convo_aug
    }


# def main(input_path="/workspace/ToolBench/PaladinEvalData.jsonl", output_dir="augmented_examples"):
#     input_path = Path(input_path)
#     output_dir = Path(output_dir)
#     output_dir.mkdir(exist_ok=True)

#     examples = []
#     with input_path.open("r") as f:
#         for idx, line in enumerate(f, 1):
#             line = line.strip()
#             if not line:
#                 continue
#             try:
#                 obj = json.loads(line)
#                 if not isinstance(obj, dict) or "conversations" not in obj:
#                     print(f"[WARN] Skipping malformed example at line {idx}")
#                     continue
#                 examples.append(obj)
#             except json.JSONDecodeError as e:
#                 print(f"[WARN] Skipping line {idx} due to JSONDecodeError: {e}")

#     random.shuffle(FAILURE_KEYS)
#     failure_cycle = iter(FAILURE_KEYS * ((len(examples) // len(FAILURE_KEYS)) + 1))

#     count = 0
#     for i, ex in enumerate(tqdm(examples, desc="Augmenting", unit="example")):
#         failure_type = next(failure_cycle)
#         aug_ex = augment_with_failure(ex, failure_type)
#         if aug_ex:
#             file_path = output_dir / f"example_{i+1:04d}__{failure_type}.json"
#             try:
#                 with file_path.open("w") as f_out:
#                     json.dump(aug_ex, f_out, indent=2)
#                     count += 1
#                     tqdm.write(f"Saved {file_path.name}")
#             except Exception as e:
#                 print(f"[ERROR] Could not write file {file_path}: {e}")

#     print(f"\nCompleted augmentation of {count} examples. Files saved in {output_dir}\n")


# if __name__ == "__main__":
#     main()

input_file = "C:/Users/Sri Vatsa/Desktop/FaiL-Safe Benchmark/ToolBench/data/newdata.jsonl"
output_file = "C:/Users/Sri Vatsa/Desktop/FaiL-Safe Benchmark/ToolBench/data/GPTdata1.jsonl"


cnt=0
FAILURE_KEYS = list(recovery_paths.keys())

with open(input_file, "r", encoding="utf-8") as infile, open(output_file, "w", encoding="utf-8") as outfile:
    for line in infile:
        cnt+=1
        obj = json.loads(line)
        convos = obj.get("conversations", [])
        
        # Reset variables for each object
        failureidx = None
        failurecode = None

        
        for idx, message in enumerate(convos):
            value = message.get("value", "")
            if message.get("from", "") == "function":
              for code in FAILURE_KEYS:
                  if code in value:
                      failureidx = idx
                      failurecode = code
                      break
              if failureidx is not None:
                break
              if "error" in value  and failureidx is None and failurecode is None:
                  failureidx = idx
                  failurecode = "unknown"
                  randomnum = 0
        
        if failureidx is not None and failurecode is not None:
    
            newconvos = augment_with_failure(obj, failurecode, failureidx)
        
            # Only write if augmentation was successful
            if newconvos is not None:
                outfile.write(json.dumps(newconvos, ensure_ascii=False) + "\n")
          
            else:
                # If augmentation failed, write the original object
                continue
        elif failureidx is None and failurecode is None:
            newconvos=augment_to_make_better(obj)
            outfile.write(json.dumps(newconvos, ensure_ascii=False) + "\n")
        print(cnt)
        

            