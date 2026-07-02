# Jira Data Center REST reference (for `jira_issue.py`)

What the fetch script relies on, and how to reason about failures. **Data Center / Server only** —
this is not Jira Cloud.

## Auth

Jira Data Center uses a **Personal Access Token as a bearer token**:

```
Authorization: Bearer <PAT>
```

This is different from Jira **Cloud**, which uses Basic auth with `email:api_token`. PATs are
supported on Jira Core/Software **8.14+** (Jira Service Management 4.15+). Create one under
Profile → **Personal access tokens**.

## Endpoint

```
GET {baseUrl}/rest/api/2/issue/{issueIdOrKey}
```

- Use **`api/2`** (or `api/latest`). `api/3` + ADF is **Cloud-only** — Data Center has no `api/3`.
- `{baseUrl}` must include any **context path** the instance is mounted under (commonly `/jira`), e.g. `https://host/jira`. The script preserves whatever is in `JIRA_BASE_URL`.

### Query params the script sends
- `fields=summary,issuetype,status,priority,description,comment,issuelinks,subtasks,attachment` — whitelist to keep the payload small.
- `expand=renderedFields` — adds a top-level `renderedFields` object mirroring `fields`, with rich-text fields **server-rendered to HTML** (macros, mentions, dates resolved).

## Rich text: rendered HTML vs raw wiki markup

Data Center stores `description` and comment `body` as **Jira wiki-markup strings** (`h2.`, `*bold*`,
`{code}` …) — **not** ADF JSON. The script therefore:
1. Prefers `renderedFields.description` (HTML) and strips it to plain text.
2. Falls back to the raw `fields.description` wiki-markup string when `renderedFields` is empty.

Same pattern for comments (`renderedFields.comment.comments[].body` → fall back to `fields.comment.comments[].body`).

## Fields the script reads

| Section | JSON path |
|---------|-----------|
| Summary | `fields.summary` |
| Type / status / priority | `fields.issuetype.name`, `fields.status.name`, `fields.priority.name` |
| Description | `renderedFields.description` ?? `fields.description` |
| Comments | `fields.comment.comments[]` (`author.displayName`, `created`, `body`) |
| Linked issues | `fields.issuelinks[]` (`type.name`, `inwardIssue`/`outwardIssue` → `key`, `fields.summary`, `fields.status.name`) |
| Subtasks | `fields.subtasks[]` (`key`, `fields.summary`, `fields.status.name`) |
| Attachments (names only) | `fields.attachment[]` (`filename`, `size`, `mimeType`; `content` is the authenticated download URL — not fetched) |

## Failure modes

| Status | Meaning | What to do |
|--------|---------|------------|
| **401** | PAT missing, invalid, or **expired** | Create a new token; expired PATs can't be reactivated. |
| **403** | Authenticated but **lacks permission**, or CAPTCHA after failed logins | Check project permissions / `X-Authentication-Denied-Reason`. |
| **404** | Issue doesn't exist **or** no Browse permission | Jira returns 404 (not 403) to avoid leaking existence — could be a permissions issue. |
| **400** | Bad key or `fields`/`expand` value | Check the issue key. |
| **429** | Rate limited (if admin enabled it) | Honor `Retry-After`. |
| non-JSON / 302 / login HTML | Base URL hit an SSO/login page, not the API | Verify the **context path** and that the Bearer header reaches Jira (reverse proxy/SSO can strip it). |

## Official docs

- [Using Personal Access Tokens — Atlassian Data Center](https://confluence.atlassian.com/enterprise/using-personal-access-tokens-1026032365.html)
- [Personal access token — Jira Data Center (developer.atlassian.com)](https://developer.atlassian.com/server/jira/platform/personal-access-token/)
- [The Jira Data Center REST API — issue group](https://developer.atlassian.com/server/jira/platform/rest/v10000/api-group-issue/)
- [Jira REST API examples (Server/DC)](https://developer.atlassian.com/server/jira/platform/jira-rest-api-examples/)
- [About the Jira Server REST APIs](https://developer.atlassian.com/server/jira/platform/about-the-jira-server-rest-apis/)

## Note on MCP

The official Atlassian (Rovo) MCP server is **Cloud/OAuth-only** and does not support Data Center +
PAT, which is why this skill ships a small stdlib script instead. If you prefer an MCP, the community
`sooperset/mcp-atlassian` supports DC via `JIRA_PERSONAL_TOKEN`.
