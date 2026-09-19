// Exercises the existing product fixture with transport refreshes, not live consent.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import path from "node:path";
const root = path.resolve(process.env.AIBENCHIE_CANVAS_ACCOUNT_ROOT, "frontend");
const require = createRequire(path.join(root, "package.json"));
const { createServer } = await import(pathToFileURL(path.join(path.dirname(require.resolve("vite/package.json")), "dist/node/index.js")));
const { chromium } = require(process.env.PLAYWRIGHT_MODULE);
const server = await createServer({ root, configFile: false, server: { host: "127.0.0.1", port: 0 }, plugins: [{
  name: "aibenchie-transport-refresh",
  enforce: "pre",
  transform(code, id) {
    if (!id.endsWith("/scripts/fixtures/account-links.jsx")) return;
    return code.replace("function Fixture() {", "function Fixture() { const [revision, bump] = useState(0);")
      .replace("<AccountLinks key={account} apiFetch={apiFetch}", "<button onClick={() => bump(revision+1)}>Refresh transport</button><AccountLinks key={account} apiFetch={(...args) => apiFetch(...args)}");
  },
}] });
await server.listen();
let browser;
try {
  browser = await chromium.launch({ headless: true, channel: "chrome" });
  const page = await browser.newPage();
  const origin = `http://127.0.0.1:${server.httpServer.address().port}`;
  const reviewId = "b".repeat(64), ticket = "a".repeat(64);
  const account = { issuer: "https://accounts.example.test", userId: "synthetic", username: "Synthetic Artistic" };
  const endpoint = { agentId: "Synthetic phone", fingerprint: "c".repeat(64) };
  let confirmed = false, calls = 0;
  await page.route("**/auth/nullbridge/account-links/**", route => {
    const action = route.request().url().split("/").at(-1);
    if (action === "review") return route.fulfill({ json: { reviewId, endpoint, account, expiresAt: Math.floor(Date.now()/1000)+90, grantsPermissions: false, copiesChatKeys: false } });
    assert.equal(action, "confirm"); calls++;
    return route.fulfill({ json: confirmed ? { linkId: reviewId, endpoint, account, grantsPermissions: false, isAuthorizationCredential: false }
      : { state: "awaiting_endpoint_confirmation", reviewId, grantsPermissions: false } });
  });
  await page.goto(origin+"/scripts/fixtures/account-links.html");
  await page.getByLabel("Temporary device setup code").fill(ticket);
  await page.getByRole("button", { name: "Review device link" }).click();
  await page.getByRole("region", { name: "Exact device link review" }).waitFor();
  await page.getByRole("button", { name: "Refresh transport" }).click();
  assert.ok(await page.getByRole("region", { name: "Exact device link review" }).isVisible());
  await page.getByRole("button", { name: "Confirm this account and device" }).click();
  await page.getByText("Now confirm this account on the device.", { exact: false }).waitFor();
  await page.getByRole("button", { name: "Refresh transport" }).click();
  confirmed = true;
  await page.getByText("Account and device linked.", { exact: false }).waitFor();
  assert.ok(calls >= 2);
  await page.getByLabel("Temporary device setup code").fill(ticket);
  await page.getByRole("button", { name: "Review device link" }).click();
  await page.getByRole("region", { name: "Exact device link review" }).waitFor();
  await page.getByRole("button", { name: "Switch synthetic account" }).click();
  assert.equal(await page.getByRole("region", { name: "Exact device link review" }).count(), 0);
  console.log("PASS: transport refresh preserves pending review; account change clears it. Synthetic only.");
} finally { await browser?.close(); await server.close(); }
