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
      "value": "Thoughts: If I’ve ruled out all formatting issues and unnecessary data, perhaps the server expects a specific field format or special value that's not obvious in documentation.\n Action: Re-read official API documentation to verify required value formats (e.g., date format, string casing), hidden required fields, and example requests. Test with minimal, known-good sample data if available."
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
      "value": "Thoughts: 429 Too Many Requests means I've hit the server’s rate limit for this resource or API key.\n Action: Honor any Retry-After timeout in the response, and if it's missing, apply a backoff delay before trying again."
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
      "value": "Thoughts: I received a JSON Schema Violation which means the data returned or sent doesn’t match the expected format or types.\n Action: Validate the offending JSON against the documented schema, identify which key or field is wrong, and try to coerce or correct invalid values before retrying the call."
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
      "value": "Thoughts: 411 Length Required means the server needs to know the size of my payload but it was missing from my request.\n Action: Add an appropriate Content-Length header indicating the request’s payload size and retry the request."
    },
    {
      "from": "function",
      "value": "Content-Length header added; request processed."
    }
  ],
  "412": [
    {
      "from": "Assistant",
      "value": "Thoughts: 412 Precondition Failed means the request had an If-* header or precondition that wasn’t satisfied (e.g., ETag mismatch).\n Action: Fetch the latest state or version, adjust my preconditions, and try again only if they now match."
    },
    {
      "from": "function",
      "value": "Request succeeded with updated precondition."
    }
  ],
  "413": [
    {
      "from": "Assistant",
      "value": "Thoughts: 413 Payload Too Large means my data upload exceeds the server’s limit.\n Action: Reduce payload size (compress, split, or chunk the data) and resend the request. If needed, request server for higher limits."
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
      "value": "Thoughts: 416 Range Not Satisfiable means the byte-range I requested is outside the resource’s available range (e.g., file ends at byte 1000, requested 1001-2000).\n Action: Adjust or remove the Range header to request valid or all available data, then resend."
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
    marker = "Specifically, you have access to the following APIs:"
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
            value = bytes(value, "utf-8").decode("unicode_escape")
            current["value"] = value

    # append last block if complete
    if current and "from" in current and "value" in current:
        blocks.append(current)

    return blocks

def newtrainingthing(message):
    message["value"]="xxx"
    return message


def generate_recovery(Last_thought, Last_decided_action, Last_inpure, failure_type, task_description=None, tools_info=None, recent_conversation=None):
    
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

    prompt = f"""
You are a recovery assistant for LLM agents using tools/APIs in a multi-step workflow. In this situation you will encounter a situation where a tool call has failed and will be directed to solve it. 

Make sure to label each step as "Recovery: " and then start initiating recovery actions in this format:

Thought: Briefly explain the failure and intended recovery strategy in 1-2 sentences.
Action: The function to retry + the chnages you implemented or an alternate fallback tool.
Action Input: Valid JSON input for the action.

For recovery follow the recovery protocols for the given error ({failure_type}) in {recovery_paths}. These recovery protocols are very generalized so use them as a basis as you fix the very specific problem that is occuring for each specific situation.
In the event of the error "unknown" look through {recovery_paths} and determine what the error most likley is and initiate the recovery protocols for said error.


An example of a recovery output may look like this:
(Disclaimer: When generating a recovery step, use realistic and plausible values for all tool parameters. Do not use placeholders like (example VIN) or (expected output). If exact values are unknown, infer likely values using context and general knowledge. When providing the expected function output, return a complete and specific JSON object with values consistent with what the tool would return in a real-world case.)

"from": "assistant"
"value": "Recovery: Thoughts: (fill with relevant thoughts) \n Action: (fill with relevant action) \n Action Input: (fill with relevant json input)  Which You fill out based on the given context.",

After creating this format you will then create an expected output from the function in the form of a JSON output.

An example of a succesful function output may look like this:


"from": "function",
"value": "(the succesful JSON output)",


Finally you will send another message upon succesfully correcting the error providing the user with the information that they needed. In this output ALWAYS include "Finish" in the action part.  This output will also use the Thought, Action, Action Input format:

An example of a final output may look like this (MAKE SURE TO ALWAYS HAVE A FINAL OUTPUT):

"from": "assistant",
"value": "Thoughts: (Provide User with information here) \n Action: Finish \n Action Input:",

ALWAYS follow the eample formats for every correction

In the case that a correction may take multiple back and forths between the system use this format.

"from": "assistant"
"value": "Recovery: Thoughts: (fill with relevant info) \n Action: (fill with relevant info) \n Action Input: (fill with relevant info)  Which You fill out based on the given context.",

"from": "function",
"value": "(the expected JSON output)",

"from": "assistant"
"value": "Recovery: Thoughts: (fill with relevant info) \n Action: (fill with relevant info) \n Action Input: (fill with relevant info)  Which You fill out based on the given context.",

Do this until you get the succesful function output and finish with a final output.

In the event that you find an error to be unsolvable end it of with a unable to solve output:

"from":"assistance"
"value": "Unable to solve"

Use only the information below for context. Do not add unrelated content.

This is the task context: {task_context}

These are the tools you have on hand for the given task and their parameteres and how they work: {tools_context}
Make sure your actions follow the guidelines for the tools here.

This is all the previous messages building up to the error: {conversation_context}

This is the information regarding the most recent action by the LLM agent which caused the error:

    Most recent thought: {Last_thought}
    Most recent action: {Last_decided_action}
    Most recent input: {Last_inpure}

ALWAYS DO THESE THINGS DO NOT SKIP ANY OF THEM:
Ensure all Action Input and function outputs are complete JSON. Do not end responses mid-key or mid-string. Always finish closing braces, brackets, and quotes.
Make sure you ALWAYS finish a task.  Dont just end with a few calls.  If a task is unsolvable then end it of with an unable to solve output and explain why it is unsolvable.
"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a precise and efficient LLM recovery agent."},
                {"role": "user", "content": prompt.strip()}
            ],
            temperature=0.2,
            max_tokens=200
        )
        result = response.choices[0].message.content.strip()
        if not result:
            print("[WARN] Empty response from OpenAI API")
            return "Thought: API returned empty response.\nAction: Finish\nAction Input: {\"return_type\": \"give_up_and_restart\"}"
        return result
    except openai.error.OpenAIError as e:
        print(f"[OpenAI API Error] {e}")
        return "Thought: API call failed.\nAction: Finish\nAction Input: {\"return_type\": \"give_up_and_restart\"}"
    except Exception as e:
        print(f"[Unexpected Error in generate_recovery] {e}")
        return "Thought: Unexpected error occurred.\nAction: Finish\nAction Input: {\"return_type\": \"give_up_and_restart\"}"


def augment_with_failure(example, failure_type,failure_index):
    convo = example.get("conversations", [])
    convo_aug = []

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
            convo_aug.append(newtrainingthing(msg))
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

    error_payload = {"error": f"{failure_type} {recovery_paths[failure_type]}", "response": None}

    convo_aug.append({"from": "function", "value": json.dumps(failure_type)})

    recovery_msg = generate_recovery(
        prevthought,
        prevaction,
        prevactioninput,
        failure_type,
        task_description=task_description,
        tools_info=tools_info,
        recent_conversation=recent_conversation
    )

    print(f"\n[GPT Recovery for {failure_type}]:\n{recovery_msg}\n")


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
        randomnum = random.randint(1, 10)
        
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
        
        if randomnum <= 8 and failureidx is not None and failurecode is not None:
            print(f"Processing object {obj.get('id', 'unknown')} with failure {failurecode} at index {failureidx}")
            newconvos = augment_with_failure(obj, failurecode, failureidx)
            
            # Only write if augmentation was successful
            if newconvos is not None:
                outfile.write(json.dumps(newconvos, ensure_ascii=False) + "\n")
                print(f"Successfully augmented object {obj.get('id', 'unknown')}")
            else:
                # If augmentation failed, write the original object
                outfile.write(json.dumps(obj, ensure_ascii=False) + "\n")
                print(f"Augmentation failed for object {obj.get('id', 'unknown')}, writing original")
        else:
            outfile.write(json.dumps(obj, ensure_ascii=False) + "\n")
            if failureidx is None or failurecode is None:
                print(f"No failure found in object {obj.get('id', 'unknown')}")
            else:
                print(f"Random number {randomnum} > 8, skipping augmentation for object {obj.get('id', 'unknown')}")
        

            