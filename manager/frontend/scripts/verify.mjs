#!/usr/bin/env node
// Real-browser smoke test for the dashboard, via Playwright (already a
// devDependency -- installed with a cached Chromium in this environment,
// see `npx playwright install chromium`). Exists because this project has
// repeatedly hit "can't verify in a real browser, no display in this
// sandbox" as a documented gap (see knowledge-graph/dashboard-ui.md) --
// this closes that gap for the parts a headless browser can check:
// does it render without console/page errors, does real data show up,
// do the collapsible forms open. It can NOT tell you if something looks
// good -- pair it with the screenshot it saves for that.
//
// Usage: node scripts/verify.mjs [base_url] [admin_password]
// Requires the manager running with a matching GRID_MANAGER_ADMIN_PASSWORD
// and `npm run build` already done (serves from app/static/dist/).

import { chromium } from 'playwright'

const baseUrl = process.argv[2] || 'http://127.0.0.1:8000'
const password = process.argv[3] || process.env.GRID_MANAGER_ADMIN_PASSWORD
if (!password) {
  console.error('Usage: node scripts/verify.mjs [base_url] [admin_password]')
  console.error('(or set GRID_MANAGER_ADMIN_PASSWORD)')
  process.exit(1)
}

const errors = []
const consoleErrors = []

const browser = await chromium.launch()
const context = await browser.newContext({
  httpCredentials: { username: 'admin', password },
  viewport: { width: 1400, height: 1000 },
})
const page = await context.newPage()
page.on('pageerror', (err) => errors.push(err.message))
page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push(msg.text())
})

await page.goto(baseUrl, { waitUntil: 'networkidle' })
await page.waitForTimeout(2000) // let the first round of polling fire

const title = await page.title()
const workerCardCount = await page.locator('.ant-card').count()

// Exercise the two collapsible forms -- these are the parts most likely
// to silently break (antd Collapse/Form wiring), not just static render.
let attachFormOk = false
let fahFormOk = false
try {
  await page.getByText('Attach a project…').click({ timeout: 3000 })
  attachFormOk = await page.getByPlaceholder('https://example.org/project/').isVisible()
} catch {
  /* no BOINC block on this deployment -- fine */
}
try {
  await page.getByText('Account & cause…').click({ timeout: 3000 })
  fahFormOk = await page.getByText('Fold anonymously').isVisible()
} catch {
  /* no FAH block on this deployment -- fine */
}

const screenshotPath = new URL('../verify-screenshot.png', import.meta.url).pathname
await page.screenshot({ path: screenshotPath, fullPage: true })

await browser.close()

console.log(`title: ${title}`)
console.log(`ant-design cards rendered: ${workerCardCount}`)
console.log(`BOINC attach form opens: ${attachFormOk}`)
console.log(`FAH config form opens: ${fahFormOk}`)
console.log(`page errors: ${errors.length ? errors.join('; ') : 'none'}`)
console.log(`console errors: ${consoleErrors.length ? consoleErrors.join('; ') : 'none'}`)
console.log(`screenshot: ${screenshotPath}`)

if (errors.length || title !== 'Grid Manager') {
  console.error('\nFAILED')
  process.exit(1)
}
console.log('\nOK')
