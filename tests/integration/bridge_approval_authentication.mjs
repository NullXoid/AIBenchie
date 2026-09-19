import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import path from "node:path";

const root = process.env.AIBENCHIE_CANVAS_ACCOUNT_ROOT;
assert.ok(root, "Explicit account candidate required");
const { approvalAuthenticationReady: ready, accountApprovalRoute } = await import(pathToFileURL(path.join(root, "frontend/src/lib/accountApprovalState.mjs")));
assert.equal(ready({ role: "master", recentPasskey: true }), true);
assert.equal(ready({ role: "master", recentPasskey: false, approvalAuthenticationReady: true }), true);
assert.equal(ready({ role: "master", recentPasskey: true, approvalAuthenticationReady: false }), false);
for (const role of ["administrator", "user", "beta", undefined]) {
  assert.equal(ready({ role, recentPasskey: true, approvalAuthenticationReady: true }), false);
}
assert.equal(ready(null), false);
assert.equal(ready({ role: "master", approvalAuthenticationReady: "true" }), false);
const ticket = "a".repeat(64);
assert.deepEqual(accountApprovalRoute(`#account-approvals?link=${ticket}`), { requestId: null, linkTicket: ticket });
for (const hash of [`#account-approvals?link=${ticket}&approve=true`, "#account-approvals?link=bad", `#account-approvals?link=${ticket}/`]) {
  assert.equal(accountApprovalRoute(hash), null);
}
console.log("Approval UI authentication-policy checks passed");
