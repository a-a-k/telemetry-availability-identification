# Original AINA audit v2: authenticated draft access

The v1 run34231434522/head9452a33912150581f76965ca814d449dedb054d6 stopped at GET release asset550517536 with HTTP403 before original payload download or parsing. Exact compact failure and resource usage are retained. No original data audit result was produced, and no scientific conclusion follows from this infrastructure failure.

GitHub documents that draft release visibility requires push access: [REST releases](https://docs.github.com/en/rest/releases/releases). V1 contents:read did not grant that access to the Actions token. V2 sets contents:write only on the single audit job, disables checkout credential persistence, and uses the same frozen v1 GET-only audit code through a versioned config adapter. No code publishes or modifies a release, tag, asset or repository. The existing source release remains an unpublished draft. No personal token is stored or passed to Actions.

All scientific scope, input bytes, census, exact controls, MC diagnostic family, enumeration/resource limits and outputs in ORIGINAL_AINA_AUDIT_PROTOCOL_V1.md remain identical. V1 files stay frozen. New workflow, adapter, correction and exact config locks are committed before dispatch. This is a technical repeat, not a new independent sample.
