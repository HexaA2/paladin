import json
import openai
from pathlib import Path
from tqdm import tqdm
import random
import re

# === CONFIG === #
openai.api_key = "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"

recovery_paths = {
  "400": [
    {
      "from": "Assistant",
      "value": "Thoughts: I just received a 400 Bad Request. This usually means the server couldn't understand my request due to malformed syntax or invalid data.\n Action: Carefully review the request URL and endpoint for any typos, double slashes, or illegal characters before resending the call."
    },
    {
      "from": "function",
      "value": "No syntax issues found in the URL or endpoint; server still returns 400."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: Since the URL looks fine, maybe the problem is with my request headers or required parameters.\n Action: Check every mandatory request header (such as Content-Type and Authorization) for correctness, spelling, values, and presence. Make sure required parameters are spelled and formatted exactly as in the API docs, then resend the request."
    },
    {
      "from": "function",
      "value": "Headers and parameters look correct. Resent request but still received a 400 error."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: With URL and headers good, it's likely an issue with my request body or JSON payload formatting.\n Action: Validate the structure of my payload (e.g., check that JSON is well-formed, has no trailing commas, and all required fields are present and of the correct type). Pretty-print and compare my payload against API schema or working examples, then resend corrected request."
    },
    {
      "from": "function",
      "value": "JSON and payload are now valid, but I still get a 400 error from the server."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: If all the values are now correct, maybe my payload is too large, or I'm sending extra/unexpected data.\n Action: Reduce payload size or remove optional fields; ensure there aren't any hidden or null values. Also clear any local cookies or session data that could be interfering, then try the request again."
    },
    {
      "from": "function",
      "value": "400 error persists after all structural checks."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: If I've ruled out all formatting issues and unnecessary data, perhaps the server expects a specific field format or special value that's not obvious in documentation.\n Action: Re-read official API documentation to verify required value formats (e.g., date format, string casing), hidden required fields, and example requests. Test with minimal, known-good sample data if available."
    },
    {
      "from": "function",
      "value": "If the API sample succeeds, incrementally add fields until the issue recurs. If unsuccessful after all checks, escalate with full request details."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: Automated corrections failed. This problem could require deeper investigation.\n Action: Log the full failed request, server response, and all troubleshooting steps taken so far. Escalate to a human developer or support team for further triage."
    },
    {
      "from": "function",
      "value": "Escalation/Hand-off complete."
    }
  ],
  "401": [
    {
      "from": "Assistant",
      "value": "Thoughts: I received a 401 Unauthorized error, indicating my credentials are invalid or missing for this API request.\n Action: Double-check if I included the Authorization or API key header, and verify its value is current and correctly formatted."
    },
    {
      "from": "function",
      "value": "Authorization header is present but request is still unauthorized."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: The key or token might be expired, revoked, or lacking required privileges.\n Action: Attempt to refresh or obtain a new API token and resend the request with updated credentials."
    },
    {
      "from": "function",
      "value": "Resent request with new credentials but still received 401 error."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: Credential updates failed; this probably requires manual intervention or admin help.\n Action: Log the failed request, notify the user to check account status or permissions, and request a credential reset if needed."
    },
    {
      "from": "function",
      "value": "Escalation/Hand-off complete."
    }
  ],
  "403": [
    {
      "from": "Assistant",
      "value": "Thoughts: 403 Forbidden means I am authenticated, but not allowed to access this resource.\n Action: Review the API docs and confirm my account, key, or token should have access to this endpoint."
    },
    {
      "from": "function",
      "value": "Confirmed that my permissions should allow access, but the request still returns 403."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: Maybe organization policy, resource-specific ACL, or account role restricts access.\n Action: Check for special resource access settings, and if possible, try with alternate credentials or request additional privileges."
    },
    {
      "from": "function",
      "value": "Still blocked from resource after all credential checks."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: I've exhausted my options. This restriction may be intentional or require admin intervention.\n Action: Report the 403 error with full request details and advise team or admin to review access rights or update roles."
    },
    {
      "from": "function",
      "value": "Escalation/Hand-off complete."
    }
  ],
  "404": [
    {
      "from": "Assistant",
      "value": "Thoughts: 404 Not Found means the resource or endpoint I requested does not exist or may have been moved or deleted.\n Action: Check for typos in the request URL and endpoint, and examine resource identifiers against the latest API docs."
    },
    {
      "from": "function",
      "value": "URL and identifiers look correct; still receiving 404."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: Resource could be renamed, deleted, or access is restricted by organization or account.\n Action: Search for similar resources, alternative endpoints, or use listing APIs to verify existence or find a replacement."
    },
    {
      "from": "function",
      "value": "No alternative resource found; 404 persists."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: This appears to be a permanent missing resource. Further automation will not help.\n Action: Log the details and notify the project owner or developer for confirmation, migration instructions, or recreation."
    },
    {
      "from": "function",
      "value": "Escalation/Hand-off complete."
    }
  ],
  "500": [
    {
      "from": "Assistant",
      "value": "Thoughts: 500 Internal Server Error is a server-side failure, often transient.\n Action: Retry the request using exponential backoff (wait 1s, 2s, 4s), up to 3 times."
    },
    {
      "from": "function",
      "value": "All retries exhausted; server still returns 500."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: Persistent 500 error signals a wider server problem.\n Action: Check the API provider's status page for outages or maintenance. Log the problem and defer this task until the service is back up."
    },
    {
      "from": "function",
      "value": "Escalation/Hand-off complete."
    }
  ],
  "503": [
    {
      "from": "Assistant",
      "value": "Thoughts: Received 503 Service Unavailable, meaning temporary server overload or maintenance.\n Action: Look for a Retry-After header in the response and wait that amount before retrying."
    },
    {
      "from": "function",
      "value": "No Retry-After header supplied; using default exponential backoff."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: Still no success. Service may have a prolonged outage.\n Action: Log multiple failed attempts and inform user or admin to check provider status or try later."
    },
    {
      "from": "function",
      "value": "Escalation/Hand-off complete."
    }
  ],
  "408": [
    {
      "from": "Assistant",
      "value": "Thoughts: Request timed out; the server did not respond promptly—could be a network or server delay.\n Action: Retry the request with exponential backoff, and if possible increase the timeout interval on subsequent attempts."
    },
    {
      "from": "function",
      "value": "Still timing out after multiple retries."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: Persistent timeouts may indicate a network issue or severe server overload.\n Action: Ping endpoint, check alternate server if available, or notify user to check application/network health."
    },
    {
      "from": "function",
      "value": "Escalation/Hand-off complete."
    }
  ],
  "DNS Resolution Error": [
    {
      "from": "Assistant",
      "value": "Thoughts: DNS Resolution Error means the hostname could not be resolved to an IP address.\n Action: Double-check the domain name for typos or outdated endpoints in the request."
    },
    {
      "from": "function",
      "value": "Domain is correct; error still persists."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: DNS problems could be temporary or depend on infrastructure issues.\n Action: Attempt to resolve a well-known public hostname to verify local DNS health. If custom domain still fails, retry later or escalate to admin."
    },
    {
      "from": "function",
      "value": "Escalation/Hand-off complete."
    }
  ],
  "429": [
    {
      "from": "Assistant",
      "value": "Thoughts: 429 Too Many Requests means I've hit the server's rate limit for this resource or API key.\n Action: Honor any Retry-After timeout in the response, and if it's missing, apply a backoff delay before trying again."
    },
    {
      "from": "function",
      "value": "Rate limit persists after waiting and retrying."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: Frequent rate limiting could mean my usage is too high or has exceeded my quota.\n Action: Reduce request volume, spread calls out, and notify user/admin to request higher quota if necessary."
    },
    {
      "from": "function",
      "value": "Escalation/Hand-off complete."
    }
  ],
  "Malformed JSON": [
    {
      "from": "Assistant",
      "value": "Thoughts: Server returned malformed JSON, indicating a parsing failure from a possible server bug or incomplete data.\n Action: Retry the same API request in case this was a temporary error."
    },
    {
      "from": "function",
      "value": "Response is still malformed after retry."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: Persistent JSON issues suggest a backend or integration bug.\n Action: Try to repair the response with tolerant parsing or reconstruct from partial data. If still unparseable, log details and escalate to API owner or user for support."
    },
    {
      "from": "function",
      "value": "Escalation/Hand-off complete."
    }
  ],
  "JSON Schema Violation": [
    {
      "from": "Assistant",
      "value": "Thoughts: I received a JSON Schema Violation which means the data returned or sent doesn't match the expected format or types.\n Action: Validate the offending JSON against the documented schema, identify which key or field is wrong, and try to coerce or correct invalid values before retrying the call."
    },
    {
      "from": "function",
      "value": "Schema fix attempted. Error persists for certain field(s)."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: Not all fields could be auto-corrected; this might be a server data issue or deep integration bug.\n Action: Log which field(s) are failing, omit or correct them if possible, and if still failing, escalate the error to development or support."
    },
    {
      "from": "function",
      "value": "Escalation/Hand-off complete."
    }
  ],
  "409": [
    {
      "from": "Assistant",
      "value": "Thoughts: 409 Conflict means my request clashes with the current state of the resource (e.g., editing a document that changed).\n Action: Retrieve the latest version or state of the resource, merge my changes accordingly, or refresh state before retrying the operation."
    },
    {
      "from": "function",
      "value": "Retried with updated resource state, but still encountering conflict."
    },
    {
      "from": "Assistant",
      "value": "Thoughts: The conflict might require manual intervention or a merge strategy.\n Action: Log the conflicting change, alert the user, and provide them the conflicting states to resolve manually."
    },
    {
      "from": "function",
      "value": "Escalation/Hand-off complete."
    }
  ],
  "410": [
    {
      "from": "Assistant",
      "value": "Thoughts: 410 Gone indicates the resource is permanently deleted and will not return in the future.\n Action: Notify the user that the resource is gone and suggest searching for alternatives or recreating if critical."
    },
    {
      "from": "function",
      "value": "User notified; action cannot continue without new or alternative resource."
    }
  ],
  "411": [
    {
      "from": "Assistant",
      "value": "Thoughts: 411 Length Required means the server needs to know the size of my payload but it was missing from my request.\n Action: Add an appropriate Content-Length header indicating the request's payload size and retry the request."
    },
    {
      "from": "function",
      "value": "Content-Length header added; request processed."
    }
  ],
  "412": [
    {
      "from": "Assistant",
      "value": "Thoughts: 412 Precondition Failed means the request had an If-* header or precondition that wasn't satisfied (e.g., ETag mismatch).\n Action: Fetch the latest state or version, adjust my preconditions, and try again only if they now match."
    },
    {
      "from": "function",
      "value": "Request succeeded with updated precondition."
    }
  ],
  "413": [
    {
      "from": "Assistant",
      "value": "Thoughts: 413 Payload Too Large means my data upload exceeds the server's limit.\n Action: Reduce payload size (compress, split, or chunk the data) and resend the request. If needed, request server for higher limits."
    },
    {
      "from": "function",
      "value": "Payload accepted after reduction."
    }
  ],
  "414": [
    {
      "from": "Assistant",
      "value": "Thoughts: 414 URI Too Long means the URL I sent exceeded what the server supports (usually thousands of characters).\n Action: Move data to the request body if possible, shorten the query, or switch from GET to POST where appropriate."
    },
    {
      "from": "function",
      "value": "Request with shortened URI processed successfully."
    }
  ],
  "415": [
    {
      "from": "Assistant",
      "value": "Thoughts: 415 Unsupported Media Type shows that my Content-Type is not accepted by the server.\n Action: Change the Content-Type header to a supported value per API docs and retry."
    },
    {
      "from": "function",
      "value": "Request accepted after changing Content-Type."
    }
  ],
  "416": [
    {
      "from": "Assistant",
      "value": "Thoughts: 416 Range Not Satisfiable means the byte-range I requested is outside the resource's available range (e.g., file ends at byte 1000, requested 1001-2000).\n Action: Adjust or remove the Range header to request valid or all available data, then resend."
    },
    {
      "from": "function",
      "value": "Valid range request accepted."
    }
  ],
  "417": [
    {
      "from": "Assistant",
      "value": "Thoughts: 417 Expectation Failed means my Expect header was not met by the server—possibly not supported or available.\n Action: Remove or modify the Expect header and retry the request."
    },
    {
      "from": "function",
      "value": "Request completed successfully without Expect header."
    }
  ],
  "418": [
    {
      "from": "Assistant",
      "value": "Thoughts: 418 I'm a Teapot is a playful HTTP code, not meant for real use, but can occasionally appear in test or poorly configured environments.\n Action: Record the occurrence for curiosity/documentation but do not retry; notify the user if the presence of this code is unexpected."
    },
    {
      "from": "function",
      "value": "No correction possible; humorous/test status code logged. No further action."
    }
  ],
  "421": [
    {
      "from": "Assistant",
      "value": "Thoughts: 421 Misdirected Request means my call was sent to a server that is not configured to serve it—could be a routing/load balancer error.\n Action: Review endpoint/server selection logic and reroute the request to the proper backend or API gateway."
    },
    {
      "from": "function",
      "value": "Request re-routed; now processed by the correct backend server."
    }
  ],
  "422": [
    {
      "from": "Assistant",
      "value": "Thoughts: 422 Unprocessable Entity indicates the server understood the request syntax but the semantic content is invalid (such as a missing or misformatted field).\n Action: Parse the error details, identify the problematic field or logic, correct it in the request payload, and resend."
    },
    {
      "from": "function",
      "value": "Updated request with validated data accepted."
    }
  ],
  "423": [
    {
      "from": "Assistant",
      "value": "Thoughts: 423 Locked means the resource is currently locked by another user or process.\n Action: Wait for a short period and attempt the request again; if still locked, notify the user and offer to retry or abandon."
    },
    {
      "from": "function",
      "value": "Resource lock released on retry; operation succeeded."
    }
  ],
  "424": [
    {
      "from": "Assistant",
      "value": "Thoughts: 424 Failed Dependency signals that a previous required operation failed, causing this request to fail as well.\n Action: Trace through dependency chain, resolve errors in required/preceding operations, then retry the current request."
    },
    {
      "from": "function",
      "value": "Dependency operation fixed; main request completed after dependencies resolved."
    }
  ],
  "425": [
    {
      "from": "Assistant",
      "value": "Thoughts: 425 Too Early means the server is unwilling to process a request that might be replayed (often during TLS negotiation).\n Action: Wait as suggested (if a Retry-After is present), then retry the request; otherwise, ensure no premature replays and try after a safety delay."
    },
    {
      "from": "function",
      "value": "Request accepted on delayed retry; operation completed."
    }
  ],
  "426": [
    {
      "from": "Assistant",
      "value": "Thoughts: 426 Upgrade Required is returned when the server demands I switch protocols for this request (e.g., from HTTP to HTTPS, or to a newer version).\n Action: Adjust my connection to use the server-requested protocol, updating headers and base URLs as needed, then retry."
    },
    {
      "from": "function",
      "value": "Request completed successfully using upgraded protocol."
    }
  ],
  "428": [
    {
      "from": "Assistant",
      "value": "Thoughts: 428 Precondition Required means the server demands preconditions (like If-Match or If-None-Match headers) to prevent accidental overwrites.\n Action: Add the required precondition headers to my request, referencing the latest resource state, and resend."
    },
    {
      "from": "function",
      "value": "Request completed after precondition headers added."
    }
  ],
  "431": [
    {
      "from": "Assistant",
      "value": "Thoughts: 431 Request Header Fields Too Large signals my headers or cookies are too big.\n Action: Reduce the size and number of headers or cookies in my request, then resend."
    },
    {
      "from": "function",
      "value": "Request succeeded after header/cookie reduction."
    }
  ],
  "444": [
    {
      "from": "Assistant",
      "value": "Thoughts: 444 No Response indicates the server closed the connection without sending a response, possibly due to firewall or load rules.\n Action: Log the occurrence, wait briefly, and retry; if repeated, notify the user or escalate to network admin for server investigation."
    },
    {
      "from": "function",
      "value": "Retried; connection is now established and response received."
    }
  ],
  "451": [
    {
      "from": "Assistant",
      "value": "Thoughts: 451 Unavailable For Legal Reasons means the server is blocking access to the resource due to legal requirements, such as copyright or local regulations.\n Action: Record this block, notify the user about the legal constraint, and suggest possible alternatives or advise contacting the provider if this is unexpected."
    },
    {
      "from": "function",
      "value": "User notified of legal restriction; no further automated action possible."
    }
  ],
  "498": [
    {
      "from": "Assistant",
      "value": "Thoughts: 498 Invalid Token indicates my authentication token is invalid, expired, or malformed.\n Action: Attempt to obtain a new valid token (refresh or re-authenticate), update the request, and try again."
    },
    {
      "from": "function",
      "value": "Token refreshed and request retried. If the error persists, user needs to check for token revocation or API changes."
    }
  ],
  "499": [
    {
      "from": "Assistant",
      "value": "Thoughts: 499 Token Required means the server expects an authentication token but none was provided.\n Action: Acquire a valid token via the authentication workflow; include it in the request headers, and resend the call."
    },
    {
      "from": "function",
      "value": "Request completed after token included."
    }
  ],
  "501": [
    {
      "from": "Assistant",
      "value": "Thoughts: 501 Not Implemented shows that the server does not support the method requested for the resource.\n Action: Check API documentation for supported methods and revise my request (e.g., switch from POST to GET or adjust endpoint)."
    },
    {
      "from": "function",
      "value": "Request succeeded with supported method."
    }
  ],
  "502": [
    {
      "from": "Assistant",
      "value": "Thoughts: 502 Bad Gateway means that a gateway or proxy received an invalid response from an upstream server.\n Action: Retry the request after a brief pause, check provider status pages, and if problem persists, consider using a backup server or inform the user."
    },
    {
      "from": "function",
      "value": "Request succeeded after retry or user notified of persistent upstream issues."
    }
  ],
  "504": [
    {
      "from": "Assistant",
      "value": "Thoughts: 504 Gateway Timeout indicates a proxy could not get a timely response from an upstream server.\n Action: Retry the request with increased timeout, and check upstream service health if failures persist."
    },
    {
      "from": "function",
      "value": "Request succeeded after retry or alert sent for upstream server downtime."
    }
  ],
  "505": [
    {
      "from": "Assistant",
      "value": "Thoughts: 505 HTTP Version Not Supported means the server will not accept the request using this HTTP protocol.\n Action: Update the request to use a supported HTTP version (such as HTTP/1.1 or HTTP/2), and resend."
    },
    {
      "from": "function",
      "value": "Request processed with updated protocol."
    }
  ],
  "507": [
    {
      "from": "Assistant",
      "value": "Thoughts: 507 Insufficient Storage means the server can't save new data due to lack of space.\n Action: Inform the user or admin, request to clear unused files or expand storage, then retry if possible."
    },
    {
      "from": "function",
      "value": "User notified and system admin alerted for storage expansion."
    }
  ],
  "508": [
    {
      "from": "Assistant",
      "value": "Thoughts: 508 Loop Detected means the server found an infinite loop in request processing (like WebDAV collections).\n Action: Alter the resource's references to break the loop and retry the operation; if not possible, log full state for review."
    },
    {
      "from": "function",
      "value": "Loop resolved; resource updated successfully or escalated for manual fix."
    }
  ],
  "510": [
    {
      "from": "Assistant",
      "value": "Thoughts: 510 Not Extended means further resources, options, or headers are needed to fulfill this request.\n Action: Check the error details and API documentation for required extensions or headers, add them, and resend."
    },
    {
      "from": "function",
      "value": "Request succeeded after required options or extensions included."
    }
  ],
  "511": [
    {
      "from": "Assistant",
      "value": "Thoughts: 511 Network Authentication Required means I need to authenticate to the network (such as logging into a captive portal) before my request can proceed.\n Action: Attempt to complete the necessary network authentication (login or acknowledge terms), and then retry the request."
    },
    {
      "from": "function",
      "value": "Network authentication completed; request processed successfully."
    }
  ],
  "529": [
    {
      "from": "Assistant",
      "value": "Thoughts: 529 Site is Overloaded indicates the server or service is currently experiencing heavy traffic and cannot process my request right now.\n Action: Wait a few minutes, retry with exponential backoff, and inform the user if high load persists."
    },
    {
      "from": "function",
      "value": "Service stabilized and request processed after delay."
    }
  ],
  "530": [
    {
      "from": "Assistant",
      "value": "Thoughts: 530 Site is Frozen means access to this resource is suspended, usually for billing or policy reasons.\n Action: Notify the user or admin about the suspension and suggest contacting support or resolving outstanding issues."
    },
    {
      "from": "function",
      "value": "User notified of frozen account or resource."
    }
  ],
  "540": [
    {
      "from": "Assistant",
      "value": "Thoughts: 540 Temporarily Disabled indicates that this service or endpoint is intentionally disabled for maintenance or other reasons.\n Action: Inform the user, log the downtime, and suggest retrying after maintenance is complete."
    },
    {
      "from": "function",
      "value": "Maintenance ongoing; user notified to check again later."
    }
  ],
  "598": [
    {
      "from": "Assistant",
      "value": "Thoughts: 598 Network Read Timeout (Proxy) means the proxy timed out waiting for a response from upstream.\n Action: Retry the request, optionally increasing the timeout, and if the error persists, check network or proxy health."
    },
    {
      "from": "function",
      "value": "Request succeeded after increased timeout or network issue reported."
    }
  ],
  "599": [
    {
      "from": "Assistant",
      "value": "Thoughts: 599 Network Connect Timeout (Proxy) means the proxy failed to establish a connection to the upstream server.\n Action: Retry connection after a short delay; if it fails repeatedly, escalate to network administrator or user."
    },
    {
      "from": "function",
      "value": "Connection re-established and request processed or user escalated for persistent failures."
    }
  ],
  "NoSuchToolError": [
    {
      "from": "Assistant",
      "value": "Thoughts: NoSuchToolError indicates I tried to invoke a tool or function that is not registered or available in the environment.\n Action: Double-check tool names for typos, consult tool registry or docs, and retry with the correct tool identifier."
    },
    {
      "from": "function",
      "value": "Request processed after fixing tool name or selection."
    }
  ],
  "InvalidToolArgumentsError": [
    {
      "from": "Assistant",
      "value": "Thoughts: InvalidToolArgumentsError means I provided arguments to a tool/function that are missing, misspelled, or of the wrong type.\n Action: Review tool usage documentation, correct the arguments or data types, and re-issue the tool call."
    },
    {
      "from": "function",
      "value": "Tool executed successfully with corrected arguments."
    }
  ],
  "ToolExecutionError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ToolExecutionError signals an internal failure or exception during tool or command execution.\n Action: Capture and log detailed tool output or error trace, retry the call if transient, or advise user if it is a persistent fault."
    },
    {
      "from": "function",
      "value": "Either resolved on retry or escalated for user troubleshooting."
    }
  ],
  "ToolCallRepairError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ToolCallRepairError means a previous attempt to automatically recover/repair a failed tool call did not work.\n Action: Switch strategy (e.g., reset tool state, try a different tool, or escalate for developer intervention if repeated repairs fail)."
    },
    {
      "from": "function",
      "value": "Recovery succeeded after alternative strategy or escalation performed."
    }
  ],
  "RuntimeError": [
    {
      "from": "Assistant",
      "value": "Thoughts: RuntimeError means an unexpected issue occurred during execution, possibly due to a logic or flow problem in my code or in an underlying library.\n Action: Examine the error message for cause, check recent changes or external dependencies, and reset internal state or variables as needed before retrying the failing process."
    },
    {
      "from": "function",
      "value": "Error persists or is resolved based on cause; error details logged."
    }
  ],
  "DataError": [
    {
      "from": "Assistant",
      "value": "Thoughts: DataError signals that data retrieved or provided is invalid, missing, or malformed for the expected operation.\n Action: Validate and clean the data; identify missing or out-of-schema values, attempt to fill or correct bad values, and retry processing."
    },
    {
      "from": "function",
      "value": "Process completes with corrected data or fails and is logged for human review."
    }
  ],
  "ConnectionError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ConnectionError means there was a failure establishing or maintaining a network connection (such as a broken pipe or dropped socket).\n Action: Test network reachability, retry with exponential backoff, switch to backup connection or endpoint if available."
    },
    {
      "from": "function",
      "value": "Request sent successfully on retry or escalated for persistent connectivity issues."
    }
  ],
  "TypeError": [
    {
      "from": "Assistant",
      "value": "Thoughts: TypeError means I attempted to process or pass a value of the wrong type to a function or operation.\n Action: Check input variable and argument types, cast or convert as needed per API requirements, then re-run the operation."
    },
    {
      "from": "function",
      "value": "Request or calculation succeeds with correct types."
    }
  ],
  "NullPointerException": [
    {
      "from": "Assistant",
      "value": "Thoughts: NullPointerException shows I tried to operate on a variable, object, or value that was not set (null).\n Action: Trace back in logic to ensure object/variable initialization, add checks for null/None, and retry after correction."
    },
    {
      "from": "function",
      "value": "Operation completed successfully after null-check or variable/object initialization."
    }
  ],
  "IndexOutOfBoundsException": [
    {
      "from": "Assistant",
      "value": "Thoughts: IndexOutOfBoundsException means I accessed an array or list using an index that's too high or negative.\n Action: Verify variable lengths/range, add bounds checks, and adjust loop logic or input indices before retrying."
    },
    {
      "from": "function",
      "value": "Access corrected; operation successful with valid indices."
    }
  ],
  "ClassCastException": [
    {
      "from": "Assistant",
      "value": "Thoughts: ClassCastException signals an invalid type conversion attempt (e.g., casting a string to an integer where inappropriate).\n Action: Check types before casting, enforce strict type checking and validation, and fix source data or logic if needed."
    },
    {
      "from": "function",
      "value": "Conversion corrected and operation retried successfully."
    }
  ],
  "StackOverflowError": [
    {
      "from": "Assistant",
      "value": "Thoughts: StackOverflowError is caused by excessive or infinite recursion, exhausting the stack space.\n Action: Review recursion base cases and loop logic, refactor to iterative methods if possible, and retry."
    },
    {
      "from": "function",
      "value": "Process completed after recursion/logic correction."
    }
  ],
  "OutOfMemoryError": [
    {
      "from": "Assistant",
      "value": "Thoughts: OutOfMemoryError means the program asked for more memory than available.\n Action: Free unused resources, reduce data load or batch sizes, and advise user/admin to increase system memory if needed."
    },
    {
      "from": "function",
      "value": "Operation completes after memory issue resolved or logged for environment adjustment."
    }
  ],
  "ResourceLimitExceeded": [
    {
      "from": "Assistant",
      "value": "Thoughts: ResourceLimitExceeded shows my agent exceeded its allowed limits (CPU, requests, handles, etc).\n Action: Pause execution, monitor and decrease load, and retry after some time or after resource quota reset."
    },
    {
      "from": "function",
      "value": "Request processed on retry after pause or admin notification sent for quota increase."
    }
  ],
  "QuotaExceeded": [
    {
      "from": "Assistant",
      "value": "Thoughts: QuotaExceeded means I've hit the system's usage or resource allocation limit (such as daily API calls or storage).\n Action: Notify the user or admin of quota reached and recommend waiting until quotas reset, or applying/requesting for higher limits if possible."
    },
    {
      "from": "function",
      "value": "Request processed after quota reset or user notified about quota exhaustion."
    }
  ],
  "RateLimitExceeded": [
    {
      "from": "Assistant",
      "value": "Thoughts: RateLimitExceeded signals my requests are too frequent for the service's policies.\n Action: Slow down request frequency, apply backoff strategies, and if needed, coordinate to spread operations over time."
    },
    {
      "from": "function",
      "value": "Service resumes accepting requests after rate reduced."
    }
  ],
  "PermissionDeniedError": [
    {
      "from": "Assistant",
      "value": "Thoughts: PermissionDeniedError means I lack appropriate rights to access the file or resource.\n Action: Check current permissions, request escalation from user or admin, or select an alternative location with correct access."
    },
    {
      "from": "function",
      "value": "Access granted after permission change or alternative path used."
    }
  ],
  "CertificateError": [
    {
      "from": "Assistant",
      "value": "Thoughts: CertificateError means there was a problem with server-side SSL/TLS certificates during secure connection setup.\n Action: Re-check URL for typos, trust settings, or expired/self-signed certificates, and consult documentation for accepted certificate authorities."
    },
    {
      "from": "function",
      "value": "Secure connection successful after correcting certificate or trust settings."
    }
  ],
  "ModuleNotFoundError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ModuleNotFoundError signals that a required software or Python module is missing.\n Action: Verify package install, pip/conda dependencies, and sys.path; install or update as necessary."
    },
    {
      "from": "function",
      "value": "Module successfully imported after installation or environment fix."
    }
  ],
  "ImportError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ImportError means code attempted to import something not present or misspelled in the module or path.\n Action: Check spelling, dependency installation, and verify correct import syntax, then retry."
    },
    {
      "from": "function",
      "value": "Import succeeded after correction."
    }
  ],
  "AttributeError": [
    {
      "from": "Assistant",
      "value": "Thoughts: AttributeError means I tried to access a property or method that doesn't exist on the object.\n Action: Double-check object type and available attributes, update code to match correct API or object structure."
    },
    {
      "from": "function",
      "value": "Operation completes after correcting attribute usage."
    }
  ],
  "KeyError": [
    {
      "from": "Assistant",
      "value": "Thoughts: KeyError means a requested dictionary key is missing from the data structure.\n Action: Safely check for key existence before accessing, provide defaults, or repair/validate input data."
    },
    {
      "from": "function",
      "value": "Success after ensuring all accessed keys exist or providing defaults."
    }
  ],
  "ValueError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ValueError signals a function got an argument of right type but inappropriate value (e.g., out-of-range number).\n Action: Validate and adjust arguments/ranges before retrying operation."
    },
    {
      "from": "function",
      "value": "Process completes successfully with correct values."
    }
  ],
  "FileNotFoundError": [
    {
      "from": "Assistant",
      "value": "Thoughts: FileNotFoundError means a file or directory was not found during an operation.\n Action: Double-check file path and name, and create or request the missing file if necessary."
    },
    {
      "from": "function",
      "value": "File operation succeeds with valid path or after recreating missing file."
    }
  ],
  "IOError": [
    {
      "from": "Assistant",
      "value": "Thoughts: IOError signals a failure in reading, writing, or otherwise handling input/output operations due to device or system problems.\n Action: Re-check device readiness, ensure files/disks/network are available, and retry operation or notify user for manual inspection."
    },
    {
      "from": "function",
      "value": "I/O operation completes after environment or device reset, or user escalation if persistent."
    }
  ],
  "UncaughtException": [
    {
      "from": "Assistant",
      "value": "Thoughts: UncaughtException means an error was raised but not properly handled by the code or system.\n Action: Review error trace, add appropriate exception handling with try/except/finally blocks, and rerun after logic is improved."
    },
    {
      "from": "function",
      "value": "Process runs with error caught, or escalated if error source could not be corrected."
    }
  ],
  "AuthenticationTimeout": [
    {
      "from": "Assistant",
      "value": "Thoughts: AuthenticationTimeout happened; the login sequence did not succeed within allotted time, often due to network or server load.\n Action: Increase timeout window if allowed, retry authentication, and advise user or switch endpoints if repeated."
    },
    {
      "from": "function",
      "value": "Authentication completes or user switched endpoint/sought support for persistent timeout."
    }
  ],
  "WritePermissionError": [
    {
      "from": "Assistant",
      "value": "Thoughts: WritePermissionError means the agent doesn't have rights to write to the desired output location.\n Action: Request or assign correct permissions, change output location, or inform admin for elevated writes."
    },
    {
      "from": "function",
      "value": "Write completes after permissions fixed or safe destination selected."
    }
  ],
  "ReadError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ReadError points to a failure reading from file, stream, or socket—could be corruption, access, or network issues.\n Action: Retry with error correction, open alternatives or backups if available, and notify user/admin if persistent."
    },
    {
      "from": "function",
      "value": "Read successful on retry, fallback, or reported for further repair."
    }
  ],
  "BrokenPipeError": [
    {
      "from": "Assistant",
      "value": "Thoughts: BrokenPipeError shows a data connection was closed or lost during transmission.\n Action: Attempt to reestablish the pipe or network connection, and resume the interrupted operation."
    },
    {
      "from": "function",
      "value": "Transmission successful after reconnection."
    }
  ],
  "BadGatewayError": [
    {
      "from": "Assistant",
      "value": "Thoughts: BadGatewayError means the gateway/proxy received an invalid response from an upstream server.\n Action: Retry, check service health, use a backup server if available, or escalate to admin if persistent."
    },
    {
      "from": "function",
      "value": "Gateway functioning after fix or backup server."
    }
  ],
  "ParseError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ParseError occurs when I can't correctly process server data, such as malformed or unexpected formats.\n Action: Check server output, apply tolerant parsing if possible, or notify user if unresolvable."
    },
    {
      "from": "function",
      "value": "Parsed data after correction or user notified of format incompatibility."
    }
  ],
  "InvalidContentType": [
    {
      "from": "Assistant",
      "value": "Thoughts: InvalidContentType means the received data type doesn't match what I expected for the operation.\n Action: Request the correct format from the server, adjust handling logic, or negotiate for compatible format."
    },
    {
      "from": "function",
      "value": "Data processed after content type match or fallback."
    }
  ],
  "ServiceDependencyFailure": [
    {
      "from": "Assistant",
      "value": "Thoughts: ServiceDependencyFailure signals that a required upstream or dependent service failed and caused cascading issues.\n Action: Identify which service is down, alert infrastructure or admin, and retry only once dependency is healthy."
    },
    {
      "from": "function",
      "value": "Operation resumed after dependency recovery or escalated for ongoing failure."
    }
  ],
  "ResourceLimitExceeded": [
    {
      "from": "Assistant",
      "value": "Thoughts: ResourceLimitExceeded shows my agent exceeded its allowed limits (CPU, requests, handles, etc).\n Action: Pause execution, monitor and decrease load, and retry after some time or after resource quota reset."
    },
    {
      "from": "function",
      "value": "Request processed on retry after pause or admin notification sent for quota increase."
    }
  ],
  "QuotaExceeded": [
    {
      "from": "Assistant",
      "value": "Thoughts: QuotaExceeded means I've hit the system's usage or resource allocation limit (such as daily API calls or storage).\n Action: Notify the user or admin of quota reached and recommend waiting until quotas reset, or applying/requesting for higher limits if possible."
    },
    {
      "from": "function",
      "value": "Request processed after quota reset or user notified about quota exhaustion."
    }
  ],
  "RateLimitExceeded": [
    {
      "from": "Assistant",
      "value": "Thoughts: RateLimitExceeded signals my requests are too frequent for the service's policies.\n Action: Slow down request frequency, apply backoff strategies, and if needed, coordinate to spread operations over time."
    },
    {
      "from": "function",
      "value": "Service resumes accepting requests after rate reduced."
    }
  ],
  "PermissionDeniedError": [
    {
      "from": "Assistant",
      "value": "Thoughts: PermissionDeniedError means I lack appropriate rights to access the file or resource.\n Action: Check current permissions, request escalation from user or admin, or select an alternative location with correct access."
    },
    {
      "from": "function",
      "value": "Access granted after permission change or alternative path used."
    }
  ],
  "CertificateError": [
    {
      "from": "Assistant",
      "value": "Thoughts: CertificateError means there was a problem with server-side SSL/TLS certificates during secure connection setup.\n Action: Re-check URL for typos, trust settings, or expired/self-signed certificates, and consult documentation for accepted certificate authorities."
    },
    {
      "from": "function",
      "value": "Secure connection successful after correcting certificate or trust settings."
    }
  ],
  "ModuleNotFoundError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ModuleNotFoundError signals that a required software or Python module is missing.\n Action: Verify package install, pip/conda dependencies, and sys.path; install or update as necessary."
    },
    {
      "from": "function",
      "value": "Module successfully imported after installation or environment fix."
    }
  ],
  "ImportError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ImportError means code attempted to import something not present or misspelled in the module or path.\n Action: Check spelling, dependency installation, and verify correct import syntax, then retry."
    },
    {
      "from": "function",
      "value": "Import succeeded after correction."
    }
  ],
  "AttributeError": [
    {
      "from": "Assistant",
      "value": "Thoughts: AttributeError means I tried to access a property or method that doesn't exist on the object.\n Action: Double-check object type and available attributes, update code to match correct API or object structure."
    },
    {
      "from": "function",
      "value": "Operation completes after correcting attribute usage."
    }
  ],
  "KeyError": [
    {
      "from": "Assistant",
      "value": "Thoughts: KeyError means a requested dictionary key is missing from the data structure.\n Action: Safely check for key existence before accessing, provide defaults, or repair/validate input data."
    },
    {
      "from": "function",
      "value": "Success after ensuring all accessed keys exist or providing defaults."
    }
  ],
  "ValueError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ValueError signals a function got an argument of right type but inappropriate value (e.g., out-of-range number).\n Action: Validate and adjust arguments/ranges before retrying operation."
    },
    {
      "from": "function",
      "value": "Process completes successfully with correct values."
    }
  ],
  "FileNotFoundError": [
    {
      "from": "Assistant",
      "value": "Thoughts: FileNotFoundError means a file or directory was not found during an operation.\n Action: Double-check file path and name, and create or request the missing file if necessary."
    },
    {
      "from": "function",
      "value": "File operation succeeds with valid path or after recreating missing file."
    }
  ],
  "IOError": [
    {
      "from": "Assistant",
      "value": "Thoughts: IOError signals a failure in reading, writing, or otherwise handling input/output operations due to device or system problems.\n Action: Re-check device readiness, ensure files/disks/network are available, and retry operation or notify user for manual inspection."
    },
    {
      "from": "function",
      "value": "I/O operation completes after environment or device reset, or user escalation if persistent."
    }
  ],
  "UncaughtException": [
    {
      "from": "Assistant",
      "value": "Thoughts: UncaughtException means an error was raised but not properly handled by the code or system.\n Action: Review error trace, add appropriate exception handling with try/except/finally blocks, and rerun after logic is improved."
    },
    {
      "from": "function",
      "value": "Process runs with error caught, or escalated if error source could not be corrected."
    }
  ],
  "AuthenticationTimeout": [
    {
      "from": "Assistant",
      "value": "Thoughts: AuthenticationTimeout happened; the login sequence did not succeed within allotted time, often due to network or server load.\n Action: Increase timeout window if allowed, retry authentication, and advise user or switch endpoints if repeated."
    },
    {
      "from": "function",
      "value": "Authentication completes or user switched endpoint/sought support for persistent timeout."
    }
  ],
  "WritePermissionError": [
    {
      "from": "Assistant",
      "value": "Thoughts: WritePermissionError means the agent doesn't have rights to write to the desired output location.\n Action: Request or assign correct permissions, change output location, or inform admin for elevated writes."
    },
    {
      "from": "function",
      "value": "Write completes after permissions fixed or safe destination selected."
    }
  ],
  "ReadError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ReadError points to a failure reading from file, stream, or socket—could be corruption, access, or network issues.\n Action: Retry with error correction, open alternatives or backups if available, and notify user/admin if persistent."
    },
    {
      "from": "function",
      "value": "Read successful on retry, fallback, or reported for further repair."
    }
  ],
  "BrokenPipeError": [
    {
      "from": "Assistant",
      "value": "Thoughts: BrokenPipeError shows a data connection was closed or lost during transmission.\n Action: Attempt to reestablish the pipe or network connection, and resume the interrupted operation."
    },
    {
      "from": "function",
      "value": "Transmission successful after reconnection."
    }
  ],
  "BadGatewayError": [
    {
      "from": "Assistant",
      "value": "Thoughts: BadGatewayError means the gateway/proxy received an invalid response from an upstream server.\n Action: Retry, check service health, use a backup server if available, or escalate to admin if persistent."
    },
    {
      "from": "function",
      "value": "Gateway functioning after fix or backup server."
    }
  ],
  "ParseError": [
    {
      "from": "Assistant",
      "value": "Thoughts: ParseError occurs when I can't correctly process server data, such as malformed or unexpected formats.\n Action: Check server output, apply tolerant parsing if possible, or notify user if unresolvable."
    },
    {
      "from": "function",
      "value": "Parsed data after correction or user notified of format incompatibility."
    }
  ],
  "InvalidContentType": [
    {
      "from": "Assistant",
      "value": "Thoughts: InvalidContentType means the received data type doesn't match what I expected for the operation.\n Action: Request the correct format from the server, adjust handling logic, or negotiate for compatible format."
    },
    {
      "from": "function",
      "value": "Data processed after content type match or fallback."
    }
  ],
  "ServiceDependencyFailure": [
    {
      "from": "Assistant",
      "value": "Thoughts: ServiceDependencyFailure signals that a required upstream or dependent service failed and caused cascading issues.\n Action: Identify which service is down, alert infrastructure or admin, and retry only once dependency is healthy."
    },
    {
      "from": "function",
      "value": "Operation resumed after dependency recovery or escalated for ongoing failure."
    }
  ]
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
    prompt_parts.append(f"""- The failure type and general recovery protocols: {failure_type} in {recovery_paths_str}
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

## Output Examples

### Example 1 — Single Recovery Then Success
"from": "assistant",
"value": "Recovery: Thought: The API call failed due to a timeout. I will retry with a smaller dataset to speed up the response.\\nAction: get_data\\nAction Input: {{\"dataset_id\": 42, \"limit\": 100}}",

"from": "function",
"value": "{{\"data\": [ ... ]}}",

"from": "assistant",
"value": "Thought: I have retrieved the required data successfully.\\nAction: Finish\\nAction Input: {{}}",

---

### Example 2 — Multiple Recovery Attempts
"from": "assistant",
"value": "Recovery: Thought: The request failed with a 404 Not Found. I will adjust the endpoint to use the correct resource ID.\\nAction: fetch_user\\nAction Input: {{\"user_id\": 12345}}",

"from": "function",
"value": "{{\"error\": \"User not found\"}}",

"from": "assistant",
"value": "Recovery: Thought: The ID still appears invalid. I will search for the correct ID using the username.\\nAction: find_user_by_name\\nAction Input: {{\"username\": \"johndoe\"}}",

"from": "function",
"value": "{{\"user_id\": 67890}}",

"from": "assistant",
"value": "Recovery: Thought: Now that I have the correct ID, I will retry the fetch.\\nAction: fetch_user\\nAction Input: {{\"user_id\": 67890}}",

"from": "function",
"value": "{{\"name\": \"John Doe\", \"email\": \"john@example.com\"}}",

"from": "assistant",
"value": "Thought: I have retrieved the user details successfully.\\nAction: Finish\\nAction Input: {{}}",

---

### Example 3 — Unsolvable
"from": "assistant",
"value": "Recovery: Thought: The API endpoint has been deprecated and no alternative is available.\\nAction: none\\nAction Input: {{}}",

"from": "assistant",
"value": "Unable to solve: No valid recovery action exists for this tool in the current environment."

---

## Few-Shot Recovery Demonstrations""")
    
    # Part 4: Few-shot examples (these contain the most complex nested JSON)
    few_shot_examples = """

---
### Few-Shot Example 1 — Multiple Recovery Attempts Then Unable to Solve 

# Step 1: Initial recovery attempt after first failure. 
# Reason: The first API call returned an error suggesting a possible formatting issue with the username. 
# Action: Retry after trimming whitespace and converting to lowercase, as some APIs are case/whitespace sensitive.
"from": "assistant",
"value": "Recovery: Thought: The initial API call to retrieve Instagram user info for 'nike' failed, likely with a 400 Bad Request. I will trim whitespace, ensure the username is lowercase, and confirm the endpoint is correct.\\nAction: userinfo_for_instagram_cheapest\\nAction Input: {{\"username\": \"nike\"}}",

# Step 1 result: API still rejects the request with an error about the username parameter. 
# This indicates trimming/lowercasing did not fix the problem.
"from": "function",
"value": "{{\"error\": {{\"code\": 400, \"message\": \"Bad Request: Invalid or missing username parameter.\", \"details\": \"Username parameter did not match any user in our records.\"}}}},",

# Step 2: Second recovery attempt. 
# Reason: The username looks correct, so the failure may be due to missing headers required by the API.
# Action: Include 'Content-Type: application/json' header to ensure proper request format.
"from": "assistant",
"value": "Recovery: Thought: The username parameter appears valid based on the schema. The issue may be missing required headers. I will include a Content-Type header set to 'application/json'.\\nAction: userinfo_for_instagram_cheapest\\nAction Input: {{\"username\": \"nike\", \"headers\": {{\"Content-Type\": \"application/json\"}}}}",

# Step 2 result: Error persists. This suggests that headers alone are not the cause, 
# though the API hints that additional request headers or authentication may be needed.
"from": "function",
"value": "{{\"error\": {{\"code\": 400, \"message\": \"Bad Request: Invalid or missing username parameter.\", \"details\": \"API requires additional request headers or authentication.\"}}}}",

# Step 3: Third recovery attempt. 
# Reason: The request structure and headers appear correct. The error could be caused by unexpected or extra fields in the payload.
# Action: Send a minimal JSON payload with only the required 'username' field.
"from": "assistant",
"value": "Recovery: Thought: The request structure and headers are correct. I will send a minimal, well-formed JSON payload with only the username field.\\nAction: userinfo_for_instagram_cheapest\\nAction Input: {{\"username\": \"nike\"}}",

# Step 3 result: Error remains, indicating the issue is likely specific to the username or a hidden requirement for this endpoint.
"from": "function",
"value": "{{\"error\": {{\"code\": 400, \"message\": \"Bad Request: Invalid or missing username parameter.\", \"details\": \"Username format not accepted by this endpoint.\"}}}}",

# Step 4: Fourth recovery attempt. 
# Reason: To confirm whether the API itself is working or if the issue is specific to 'nike', test with a known-good username.
# Action: Use 'instagram' as a control test case.
"from": "assistant",
"value": "Recovery: Thought: All structural checks have failed. I will test with a known-good username 'instagram' to verify the endpoint.\\nAction: userinfo_for_instagram_cheapest\\nAction Input: {{\"username\": \"instagram\"}}",

# Step 4 result: Successful retrieval proves the API is functional, and the issue is limited to 'nike'.
"from": "function",
"value": "{{\"data\": {{\"user_id\": \"25025320\", \"username\": \"instagram\", \"full_name\": \"Instagram\", \"bio\": \"Discovering — and telling — stories from around the world. Curated by Instagram's community team.\", \"profile_pic_url\": \"https://instagram.com/profile_pic.jpg\", \"followers\": 500000000, \"following\": 200, \"is_verified\": true}}}}",

# Step 5: Conclusion. 
# Reason: The API works for 'instagram' but not for 'nike', indicating 'nike' may be restricted, private, or inaccessible via this API.
# Action: End with a Finish step, informing the user that the task cannot be completed for 'nike' but the API is working.
"from": "assistant",
"value": "The API works with the username 'instagram', so the endpoint is functional. The repeated 400 errors for 'nike' suggest that either the username 'nike' is not available via this API, is restricted, or the API has a limitation on certain high-profile accounts. Since all recovery steps have been exhausted, I will escalate and inform the user that data for 'nike' cannot be retrieved at this time, but the API works for other usernames like 'instagram'.\\nAction: Finish\\nAction Input:{{\"status\": \"failed\", \"reason\": \"Unable to retrieve data for 'nike' after multiple recovery attempts\", \"next_step\": \"Contact API provider or try a different username\"}}"

---

---
### Few Shot Example 2 — Incorrect Input Scope Fixed by State-Level Tool Usage

// Reason: User asked for half-staff events in New York and current flag status in West Virginia.
// Action: First attempt uses 'US' code to try to get half-staff info, assuming it covers NY.
"from": "assistant",
"value": "Thought: The user wants to know half-staff events in New York and the current flag status in West Virginia. I will start by querying US-wide half-staff events.\\nAction: get_half_staff_events_for_given_flag_for_flag_status\\nAction Input: {{\"code\": \"US\"}}",

// Result: Function runs, returns full JSON of US event info — valid but possibly not NY-specific.
"from": "function",
"value": {{\"error\": \"\", \"response\": \"[{{\'flag\': \'US\', \'issued_by\': \'President\', \'date_issued\': \'2023-01-21\', \'date_start\': \'2023-01-22\', \'date_end\': \'2023-01-26\', \'title\': \'As a mark of respect...\', \'description\': \'...\']\"}},

// Result: Function system unexpectedly returns "unknown" (maybe internal error or fallback)
"from": "function",
"value": "\"unknown\"",

// Reason: Recovery triggered due to malformed or overly broad input.
// Action: Adjust tool input to use correct state-level code ('NY' instead of 'US').
"from": "assistant",
"value": "Recovery: Thought: The request failed because I used 'US' instead of the correct state code 'NY'. I will correct the flag code to 'NY' and retry.\\nAction: get_half_staff_events_for_given_flag_for_flag_status\\nAction Input: {{\"code\": \"NY\"}}",

// Result: Recovery successful — gets the correct NY state events.
"from": "function",
"value": {{\"data\": [{{\"event_id\": \"20240601NY\", \"start_date\": \"2024-06-01\", \"end_date\": \"2024-06-02\", \"reason\": \"In honor of Memorial Day\", \"location\": \"Statewide\"}}, {{\"event_id\": \"20240615NY\", \"start_date\": \"2024-06-15\", \"end_date\": \"2024-06-15\", \"reason\": \"In memory of fallen officers\", \"location\": \"Statewide\"}}] }},

// Reason: Next, fulfill second part of user query — WV flag status.
// Action: Query tool with state code 'WV'.
"from": "assistant",
"value": "Recovery: Thought: I have successfully retrieved half-staff events for NY. Now I will get the current flag status for West Virginia using code 'WV'.\\nAction: get_half_staff_events_for_given_flag_for_flag_status\\nAction Input: {{\"code\": \"WV\"}}",

// Result: WV status successfully retrieved.
"from": "function",
"value": {{\"status\": \"full-staff\", \"last_changed\": \"2024-05-20T08:00:00Z\", \"location\": \"West Virginia\"}},

// Reason: All sub-tasks complete — proceed to final assistant wrap-up.
// Action: Provide user with event data and WV status summary.
"from": "assistant",
"value": "Thought: I have all the information. There are two half-staff events in NY, and the flag in WV is currently at full-staff.\\nAction: Finish\\nAction Input: {{\"half_staff_events\": [\"June 1–2, 2024: In honor of Memorial Day\", \"June 15, 2024: In memory of fallen officers\"], \"flag_status_WV\": \"full-staff as of May 20, 2024\"}}"

---

---

### Few Shot Example 3 -  Timeout Recovery with Billboard Tool Switch & Multi-Tool Completion (still idetified error despite false unknown)
// Reason: User asked for top 10 alternative songs and SoundCloud data related to "Almost Lover".
// Action: Attempt to retrieve chart data using Greece endpoint with 'all-time' range.
"from": "user",
"value": "\\nHelp me discover new music from different genres. Provide the top 10 alternative songs of all time. Also, search for tracks related to the song 'Almost Lover' and give me the basic information and comments for a specific song on Soundcloud.\\nBegin!\\n",

"from": "assistant",
"value": "Thought: The user asked for the top 10 alternative songs and SoundCloud details for 'Almost Lover'. I will start by calling the Greece Billboard API using range 'all-time'.\\nAction: greece_songs_for_billboard_api\\nAction Input: {{\"range\": \"all-time\", \"date\": \"2021-08-01\"}}",

// Result: Function call fails with a timeout.
"from": "function",
"value": "{{\"error\": \"Timeout error...HTTPConnectionPool(host='47.251.13.204', port=8080): Read timed out. (read timeout=10)\\", \"response\": \"\"}}",

// Result: System returns 'unknown' placeholder.
"from": "function",
"value": "\"unknown\"",

// Reason: Recovery triggered due to timeout failure (408).
// Action: Retry same call with longer timeout window.
"from": "assistant",
"value": "Recovery: Thought: The API call failed due to a timeout, which suggests a network delay or server overload. I will retry the request with an increased timeout to allow more time for the server to respond.\\nAction: greece_songs_for_billboard_api\\nAction Input: {{\"range\": \"all-time\", \"date\": \"2021-08-01\", \"timeout\": 20}}",

// Result: Second timeout failure.
"from": "function",
"value": "{{\"error\": \"Timeout error...HTTPConnectionPool(host='47.251.13.204', port=8080): Read timed out. (read timeout=20)\\", \"response\": \"\"}}",

// Reason: Persistent timeout suggests endpoint is unstable or blocked.
// Action: Switch to a more reliable alternative-specific Billboard API.
"from": "assistant",
"value": "Recovery: Thought: The increased timeout did not resolve the issue, indicating a persistent network or server problem. I will attempt to access the alternative songs using the 'alternative_songs_for_billboard_api' function, which may provide the required information without the need for a specific date.\\nAction: alternative_songs_for_billboard_api\\nAction Input: {{}}",

// Result: Alternative songs successfully retrieved.
"from": "function",
"value": "{{\"data\": [{{\"rank\": 1, \"title\": \"Smells Like Teen Spirit\", \"artist\": \"Nirvana\"}}, {{\"rank\": 2, \"title\": \"Under the Bridge\", \"artist\": \"Red Hot Chili Peppers\"}}, {{\"rank\": 3, \"title\": \"Creep\", \"artist\": \"Radiohead\"}}, {{\"rank\": 4, \"title\": \"Losing My Religion\", \"artist\": \"R.E.M.\"}}, {{\"rank\": 5, \"title\": \"Wonderwall\", \"artist\": \"Oasis\"}}, {{\"rank\": 6, \"title\": \"Black Hole Sun\", \"artist\": \"Soundgarden\"}}, {{\"rank\": 7, \"title\": \"Jeremy\", \"artist\": \"Pearl Jam\"}}, {{\"rank\": 8, \"title\": \"Come As You Are\", \"artist\": \"Nirvana\"}}, {{\"rank\": 9, \"title\": \"Zombie\", \"artist\": \"The Cranberries\"}}, {{\"rank\": 10, \"title\": \"Basket Case\", \"artist\": \"Green Day\"}}]}}",

// Reason: Billboard task is now complete.
// Action: Proceed to search for 'Almost Lover' on SoundCloud.
"from": "assistant",
"value": "Recovery: Thought: I have successfully retrieved the top 10 alternative songs of all time. Now, I will proceed to search for tracks related to 'Almost Lover' on Soundcloud.\\nAction: search_for_soundcloud\\nAction Input: {{\"type\": \"track\", \"query\": \"Almost Lover\"}}",

// Result: SoundCloud tracks returned.
"from": "function",
"value": "{{\"tracks\": [{{\"title\": \"Almost Lover\", \"artist\": \"A Fine Frenzy\", \"url\": \"https://soundcloud.com/afinefrenzy/almost-lover\"}}, {{\"title\": \"Almost Lover (Cover)\", \"artist\": \"John Doe\", \"url\": \"https://soundcloud.com/johndoe/almost-lover-cover\"}}]}}",

// Reason: Need to get more details for the original 'Almost Lover' track.
// Action: Query SoundCloud for track info and comments.
"from": "assistant",
"value": "Recovery: Thought: I have found tracks related to 'Almost Lover'. I will now retrieve basic information and comments for the specific song by A Fine Frenzy.\\nAction: song_info_for_soundcloud\\nAction Input: {{\"track_url\": \"https://soundcloud.com/afinefrenzy/almost-lover\"}}",

// Result: Song info and user comments successfully retrieved.
"from": "function",
"value": "{{\"title\": \"Almost Lover\", \"artist\": \"A Fine Frenzy\", \"comments\": [{{\"user\": \"musicfan123\", \"comment\": \"This song always makes me emotional.\"}}, {{\"user\": \"loverofmusic\", \"comment\": \"Beautiful lyrics and melody.\"}}]}}",

// Reason: All subtasks complete.
// Action: Summarize song results and end task.
"from": "assistant",
"value": "Thought: I have gathered all the necessary information. Here are the top 10 alternative songs and the SoundCloud info for 'Almost Lover'. Let me know if you'd like more recommendations! \\nAction: Finish\\nAction Input: {{\"status\": \"complete\", \"top_alternative_songs_count\": 10, \"soundcloud_track\": \"Almost Lover by A Fine Frenzy\"}}"

---

---

###Few Shot Example 4 - [Bad Schema] YouTube Playlist Creation Recovery

# Reason: User asked to search YouTube for movie trailers, build a playlist, and retrieve its details.
# Action: Assistant initiates search using YouTube v3 search API.
"from": "user",
"value": "\\nI'm planning a movie night and would like to create a playlist of YouTube videos. Search for 'movie trailers' on YouTube and retrieve the search results, including snippets and IDs. Then, fetch the videos from the search results and add them to a playlist. Provide the playlist details, including the snippets.\\nBegin!\\n",

"from": "assistant",
"value": "Thought: I will begin by searching for 'movie trailers' using the YouTube search API.\\nAction: search_for_youtube_v3_v2\\nAction Input: {{\"part\": \"snippet\", \"q\": \"movie trailers\", \"maxresults\": 10}}",

# Result: Video search successful.
"from": "function",
"value": {{\"error\": \"\", \"response\": \"{{\\\"items\\\": [{{\\\"id\\\": {{\\\"videoId\\\": \\\\\"bSD8a_Ptkds\\\\"}}}}, {{\\\"id\\\": {{\\\"videoId\\\": \\\\\"anotherVideoId1\\\\"}}}}, {{\\\"id\\\": {{\\\"videoId\\\": \\\\\"anotherVideoId2\\\\"}}}}]}}\"}},

# Reason: Assistant attempts to get playlist details prematurely, with a malformed schema.
# Action: Makes an invalid call missing required filter field like `id`, `mine`, or `channelId`.
"from": "assistant",
"value": "Thought: I have the search results. I will now try to get playlist details.\\nAction: playlist_details_for_youtube_v3_v2\\nAction Input: {{\"is_id\": \"\", \"part\": \"snippet\"}}",

# Result: Tool fails due to missing required parameter (bad schema).
"from": "function",
"value": {{\"error\": \"Message error...\", \"response\": \"{{\\\"error\\\": {{\\\"code\\\": 400, \\\\\"message\\\": \\\\\"No filter selected. Expected one of: channelId, mine, id\\\\"}}}}\"}},

# Result: Tool reports HTTP 400 error.
"from": "function",
"value": "\\"400\\"",

# Reason: Assistant recognizes bad schema input.
# Action: Creates a new playlist to obtain valid ID.
"from": "assistant",
"value": "Recovery: Thought: The error occurred because I failed to specify a required identifier. I will create a playlist to obtain a valid playlist ID.\\nAction: create_playlist_for_youtube_v3_v2\\nAction Input: {{\"title\": \"Movie Trailers Playlist\", \"description\": \"A playlist of movie trailers for movie night.\", \"privacyStatus\": \"public\"}}",

# Result: Playlist created successfully.
"from": "function",
"value": {{\"playlistId\": \"PL1234567890abcdef\"}},

# Reason: Assistant can now proceed with video upload.
# Action: Adds previously retrieved videos to the new playlist.
"from": "assistant",
"value": "Recovery: Thought: I now have a playlist ID. I will add the videos to this playlist.\\nAction: add_videos_to_playlist_for_youtube_v3_v2\\nAction Input: {{\"playlistId\": \"PL1234567890abcdef\", \"videoIds\": [\"bSD8a_Ptkds\", \"anotherVideoId1\", \"anotherVideoId2\"]}}",

# Result: Videos added successfully.
"from": "function",
"value": {{\"status\": \"success\", \"message\": \"Videos added to playlist successfully.\"}},

# Reason: Ready to retry failed playlist details call with valid ID.
# Action: Fetch playlist details for user.
"from": "assistant",
"value": "Recovery: Thought: The videos have been added. Now I will retrieve the playlist details using the valid playlist ID.\\nAction: playlist_details_for_youtube_v3_v2\\nAction Input: {{\"is_id\": \"PL1234567890abcdef\", \"part\": \"snippet\"}}",

# Result: Playlist info returned successfully.
"from": "function",
"value": {{\"items\": [{{\"snippet\": {{\"title\": \"Movie Trailers Playlist\", \"description\": \"A playlist of movie trailers for movie night.\", \"thumbnails\": {{\"default\": {{\"url\": \"https://example.com/thumbnail.jpg\"}}}}}}}}]}},

# Reason: All subtasks are complete.
# Action: Assistant summarizes and finishes.
"from": "assistant",
"value": "Thought: I have successfully created the playlist and retrieved its details.\\nAction: Finish\\nAction Input: {{\"return_type\": \"give_answer\", \"final_answer\": \"The playlist 'Movie Trailers Playlist' has been created and populated with movie trailers. You can view it with the following details: Title: Movie Trailers Playlist, Description: A playlist of movie trailers for movie night, Thumbnail: https://example.com/thumbnail.jpg.\"}}"

---

--- 
### Few Shot Example 5 - auth/header recovery pattern
// Reason: User asked for geocoordinates of NYC landmarks and nearby hotels.
// Action: Assistant initiates call to geocode Times Square using OpenCage API.
"from": "user",
"value": "\\nI'm a travel blogger and I'm planning to write an article about the top tourist attractions in New York City. Can you provide me with the geocoordinates for Times Square, Central Park, and the Statue of Liberty? Also, recommend some nearby hotels for tourists.\\nBegin!\\n",

// Reason: Begin with first location — Times Square.
// Action: Call geocode tool with new API key.
"from": "assistant",
"value": "Thought: I will begin by retrieving the coordinates for Times Square using OpenCage geocoder.\\nAction: geocode_v1_json_for_opencage_geocoder\\nAction Input: {{\"q\": \"Times Square, New York City\", \"key\": \"new-opencage-api-key\"}}",

// Reason: API call failed — unauthorized.
// Action: Return error response indicating invalid API key.
"from": "function",
"value": {{\"error\": \"\", \"response\": \"{'status': {'code': 401, 'message': 'invalid API key'}, 'results': []}\"}},

// Reason: Internal system surfaced error code 401.
// Action: Return system-recognized HTTP code.
"from": "function",
"value": "\\"401\\"",

// Reason: Recovery triggered due to 401 Unauthorized.
// Action: Retry with a corrected API key.
"from": "assistant",
"value": "Recovery: Thought: The 401 Unauthorized error suggests the API key is invalid. I will retry with a corrected OpenCage API key.\\nAction: geocode_v1_json_for_opencage_geocoder\\nAction Input: {{\"q\": \"Times Square, New York City\", \"key\": \"corrected-opencage-api-key\"}}",

// Reason: Correct API key used — request succeeds.
// Action: Return Times Square coordinates.
"from": "function",
"value": {{\"response\": \"{'results': [{'geometry': {'lat': 40.758, 'lng': -73.9855}}], 'status': {'code': 200}}\"}},

// Reason: Proceed to fetch Central Park coordinates.
// Action: Make request for Central Park using same valid API key.
"from": "assistant",
"value": "Recovery: Thought: Successfully retrieved Times Square coordinates. Now fetching coordinates for Central Park.\\nAction: geocode_v1_json_for_opencage_geocoder\\nAction Input: {{\"q\": \"Central Park, New York City\", \"key\": \"corrected-opencage-api-key\"}}",

// Reason: Valid key used — Central Park coordinates retrieved.
// Action: Return success response.
"from": "function",
"value": {{\"response\": \"{'results': [{'geometry': {'lat': 40.785091, 'lng': -73.968285}}], 'status': {'code': 200}}\"}},

// Reason: Proceed to third landmark — Statue of Liberty.
// Action: Request geocoordinates for Statue of Liberty.
"from": "assistant",
"value": "Recovery: Thought: Central Park coordinates retrieved. Proceeding with Statue of Liberty.\\nAction: geocode_v1_json_for_opencage_geocoder\\nAction Input: {{\"q\": \"Statue of Liberty, New York City\", \"key\": \"corrected-opencage-api-key\"}}",

// Reason: Final location processed — all geocoordinates collected.
// Action: Return Statue of Liberty data.
"from": "function",
"value": {{\"response\": \"{'results': [{'geometry': {'lat': 40.689247, 'lng': -74.044502}}], 'status': {'code': 200}}\"}},

// Reason: Now transition to hotel search using retrieved coordinates.
// Action: Call hotel search tool using Times Square location.
"from": "assistant",
"value": "Thought: I have all the coordinates. Next, I will search for hotels near Times Square.\\nAction: search_places_for_spott\\nAction Input: {{\"query\": \"hotels\", \"location\": \"40.758,-73.9855\"}}"

"from": "function",
"value": "{{{{\"results\": [{{\"name\": \"Hotel Edison\", \"address\": \"228 W 47th St, New York, NY 10036\"}}, {{\"name\": \"Marriott Marquis\", \"address\": \"1535 Broadway, New York, NY 10036\"}}]}}}}"

"from": "assistant",
"value": "Thought: I have successfully retrieved nearby hotels and completed all parts of the task.\\nAction: Finish\\nAction Input: {{\"landmarks\": [\"Times Square\", \"Central Park\", \"Statue of Liberty\"], \"nearby_hotels\": [\"Hotel Edison\", \"Marriott Marquis\"]}}"
---

---
### Few Shot Example 6 - Unknown Error Recovery: Discovering Valid Ruleset for Spellout

// Reason: User asked to convert 9876 into Russian spelled-out format using spellout tool.
// Action: Assistant starts by calling spellout tool with rule set "default".
"from": "user",
"value": "\nCould you help me convert the number 9876 to its spelled-out format in Russian? I need the spelled-out version for a presentation.\nBegin!\n",

"from": "assistant",
"value": "Thought: The API is called "spellout_for_spellout" to convert the number 9876 to its spelled-out format in Russian. This specific API is used because it allows converting numbers to spelled-out format in any language. The arguments passed to the API are "data" with the value 9876, "lang" with the value "ru" for Russian, and "ruleset" with the value "default". By using these arguments, the API will accurately convert the number 9876 to its spelled-out version in the Russian language.\nAction: spellout_for_spellout\nAction Input: {{"data": 9876, "lang": "ru", "ruleset": "default"}}",

// Result: Tool returns structured error indicating rule set "default" not found for Russian.
"from": "function",
"value": {{"error": "", "response": "Rule Set 'default' is not found for language 'ru'"}},

// Result: System reports unknown due to unrecognized rule set.
"from": "function",
"value": ""unknown"",

// Reason: Recovery triggered due to invalid ruleset for selected language.
// Action: Query API for valid rulesets for Russian using rulesets_for_spellout.
"from": "assistant",
"value": "Recovery: Thought: The error indicates that the 'default' rule set is not available for the Russian language. I will first check the available rule sets for Russian to find a valid option.\nAction: rulesets_for_spellout\nAction Input: {{"lang": "ru"}}",

// Result: API returns valid rule sets: "spellout-cardinal" and "spellout-ordinal".
"from": "function",
"value": {{"rulesets": ["spellout-cardinal", "spellout-ordinal"]}},

// Reason: Assistant selects appropriate fallback rule set for cardinal numbers.
// Action: Retry with rule set "spellout-cardinal".
"from": "assistant",
"value": "Recovery: Thought: The available rule sets for Russian are 'spellout-cardinal' and 'spellout-ordinal'. I will use the 'spellout-cardinal' rule set to convert the number 9876 to its spelled-out format in Russian.\nAction: spellout_for_spellout\nAction Input: {{"data": 9876, "lang": "ru", "ruleset": "spellout-cardinal"}}",

// Result: API returns correct spelled-out number.
"from": "function",
"value": {{"spelled_out": "девять тысяч восемьсот семьдесят шесть"}},

// Reason: All recovery steps successful — task complete.
// Action: Finish with final user-facing output.
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
1. At least one Recovery assistant message → matching function output.  
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

Now generate the complete, error-free conversation in this exact format.


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

input_file = "C:/Users/Sri Vatsa/Desktop/FaiL-Safe Benchmark/ToolBench/data/Newdata.jsonl"
output_file = "C:/Users/Sri Vatsa/Desktop/FaiL-Safe Benchmark/ToolBench/data/PaladinEvalData_modified.jsonl"



FAILURE_KEYS = list(recovery_paths.keys())

with open(input_file, "r", encoding="utf-8") as infile, open(output_file, "w", encoding="utf-8") as outfile:
    for line in infile:
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
            print(f"Processing object {obj.get('id', 'unknown')} with failure {failurecode} at index {failureidx}")
            newconvos = augment_with_failure(obj, failurecode, failureidx)
        
            # Only write if augmentation was successful
            if newconvos is not None:
                outfile.write(json.dumps(newconvos, ensure_ascii=False) + "\n")
                print(f"Successfully augmented object {obj.get('id', 'unknown')}")
            else:
                # If augmentation failed, write the original object
                continue
        elif failureidx is None and failurecode is None:
            newconvos=augment_to_make_better(obj)
            outfile.write(json.dumps(newconvos, ensure_ascii=False) + "\n")
        

            