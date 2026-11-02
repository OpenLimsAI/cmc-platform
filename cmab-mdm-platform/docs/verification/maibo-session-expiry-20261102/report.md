# Maibo MDM: expired signing bootstrap hidden by a generic SSO error

## Confirmed failure

The real Maibo MDM page displayed “无法确认当前登录配置或会话，请重试。未切换认证方式。” after the user's normal Casdoor login. The inspected Thinkpad tab was on `/mdm/projects`; the user also reported the same failure on `/mdm/auth-complete?return_to=%2Fprojects`. These are the same bootstrap guard, not evidence that the exact reported tab was inspected.

On 2026-11-02, clicking the visible Recheck button captured:

| UTC response time | Endpoint | Actual response |
| --- | --- | --- |
| 22:57:44.581 | `/mdm/api/v1/auth/oidc/config` | 200, JSON |
| 22:57:45.044 | `/mdm/api/v1/auth/oidc/session` | 403, JSON, code **40308**, “临时密码已过期，请联系管理员重新发放”, data=null |

No login form was resubmitted and no password, cookie or token was read or recorded. See [response summary](browser-response-summary.json) and [actual page before the fix](actual-error-before-fix.jpg). The temporary network observation was disabled after capture. Only the relevant records were retained; the broader event buffer reported truncation.

The backend's current-user guard raises `TemporaryPasswordExpiredError` after resolving and validating the OIDC user. Its code is 40308. Fresh non-secret account metadata confirms that the nominated administrator still requires the initial signing-password change and that its bootstrap deadline was already in the past. Thus the observed response is an authenticated lifecycle refusal, not a guessed diagnosis from the expiry timestamp. It is distinct from the earlier `oidc_mapping` failures and the already-corrected path/callback configuration.

The 23:04 UTC read-only server check confirms the nominated account's successful OIDC login at 22:54:41 UTC and one currently unrevoked, unexpired MDM session. Its original numeric user ID and single active identity mapping remain unchanged. The account's expired signing initialization blocks the subsequent session endpoint, rather than a missing cookie or a failed identity mapping.

The frontend's `restoreOidcAuth` previously caught every non-401 config/session error and replaced it with the generic notice. The actual backend refusal was therefore lost.

## Minimal code change

Only a session-loading failure with HTTP 403 and numeric application code 40308 receives the fixed expiry explanation. It still ends bootstrap with an error: no identity is restored, no business page is opened, no native login/refresh is enabled, and no server-provided free text is displayed. Config failures, other session failures, malformed lookalikes and network failures retain the fail-closed generic behavior.

SSO-only deployments describe the separate initial signing password; compatible deployments describe their MDM temporary password without claiming it is signing-only. No backend policy, password, mapping, role, issuer, client, callback or route changes are included.

## TDD and local verification

Tests ran in a new disposable local frontend container using the existing dependency image, a byte-identical lockfile, a read-only source mount, no network, no database and no published port.

- **Red:** 37 tests ran; 35 passed and the two new expiry-message tests failed with the original generic notice. This was executed before implementing the fix.
- **Green:** all 37 tests passed after the change.
- `pnpm build` passed TypeScript project compilation and the production Vite build.
- `pnpm lint` passed with `--max-warnings 0`.
- Regression cases include rejection without granting a session, legacy identity clearing, compatible-deployment wording, config-stage misclassification, unknown/malformed errors and existing native/SSO/logout safety behavior.

These are unit/contract tests. They do not represent a successful administrator business login or a deployed fixed-UI browser acceptance.

## Operational limits and remaining work

- The real failed response is independently confirmed. The new frontend message has not yet been deployed or observed in the live browser. PR/CI/release status is reported separately rather than pre-written as passed here.
- No password was reset, renewed, generated or delivered. The nominated identity scope remains unchanged.
- Restoring actual use requires an explicitly approved, audited reissue of the nominated user's initial **MDM signing** credential and the user's own final password entry. The empty-database `sso_bootstrap` CLI is intentionally idempotent and refuses existing identities; it must not be repurposed or rerun as a reset mechanism. No renewal mechanism was executed as part of this UI fix.
- A bounded read of recent web/backend container logs succeeded, but the fixed-route parser found no matching access-log records. This is a logging/capture limitation, not evidence of absent requests. The browser response body is the decisive error-code evidence.
- No Maibo service/configuration change, database migration, user/role change, Cloudflare operation or production deployment occurred during this diagnosis and local code change.

Recovery after a future approved credential reissue still needs a fresh real session/business check. This report does not mark the entire integration complete.
