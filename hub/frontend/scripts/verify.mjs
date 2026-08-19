#!/usr/bin/env node
// Real-browser smoke test for the dashboard, via Playwright (already a
// devDependency -- installed with a cached Chromium in this environment,
// see `npx playwright install chromium`). Exists because this project has
// repeatedly hit "can't verify in a real browser, no display in this
// sandbox" as a documented gap (see knowledge-graph/dashboard-ui.md) --
// this closes that gap for the parts a headless browser can check:
// does it render without console/page errors, does real data show up,
// do the collapsible forms open, does anything overflow horizontally on
// a phone-width viewport. It can NOT tell you if something looks good --
// pair it with the screenshots it saves for that.
//
// Usage: node scripts/verify.mjs [base_url] [admin_password]
// Requires the hub running with a matching GRIDKEEPER_ADMIN_PASSWORD
// and `npm run build` already done (serves from app/static/dist/).

import { chromium } from 'playwright'

const baseUrl = process.argv[2] || 'http://127.0.0.1:8000'
const password = process.argv[3] || process.env.GRIDKEEPER_ADMIN_PASSWORD
if (!password) {
  console.error('Usage: node scripts/verify.mjs [base_url] [admin_password]')
  console.error('(or set GRIDKEEPER_ADMIN_PASSWORD)')
  process.exit(1)
}

const errors = []
const consoleErrors = []

const browser = await chromium.launch()

// Login is a real form now (session cookie, not HTTP Basic -- see
// hub/app/auth.py's comment on why: some real mobile browsers, Firefox
// Focus confirmed, never show Basic Auth's native prompt at all).
async function login(page) {
  await page.goto(baseUrl, { waitUntil: 'networkidle' })
  await page.getByPlaceholder('Admin password').fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await page.waitForTimeout(500)
}

const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } })
const page = await context.newPage()
page.on('pageerror', (err) => errors.push(err.message))
page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push(msg.text())
})

await login(page)
await page.waitForTimeout(2000) // let the first round of polling fire

const title = await page.title()
const nodeCardCount = await page.locator('.ant-card').count()

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

// Mobile viewport pass -- the actual bug report this exists to catch:
// sections overflowing horizontally, Card titles squeezed to nothing by
// long `extra` content. iPhone SE width (375px) since it's the narrowest
// common real device -- if it doesn't overflow there, it won't on
// anything wider either.
const mobileContext = await browser.newContext({ viewport: { width: 375, height: 812 } })
const mobilePage = await mobileContext.newPage()
mobilePage.on('pageerror', (err) => errors.push(`[mobile] ${err.message}`))
await login(mobilePage)
await mobilePage.waitForTimeout(2000)

const overflowsHorizontally = await mobilePage.evaluate(
  () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
)
const cardTitleWidths = await mobilePage.evaluate(() =>
  Array.from(document.querySelectorAll('.ant-card-head-title')).map((el) => ({
    text: el.textContent.trim(),
    width: el.getBoundingClientRect().width,
  })),
)
const squeezedTitles = cardTitleWidths.filter((t) => t.text.length > 3 && t.width < 20)

const mobileScreenshotPath = new URL('../verify-screenshot-mobile.png', import.meta.url).pathname
await mobilePage.screenshot({ path: mobileScreenshotPath, fullPage: true })

await browser.close()

console.log(`title: ${title}`)
console.log(`ant-design cards rendered: ${nodeCardCount}`)
console.log(`BOINC attach form opens: ${attachFormOk}`)
console.log(`FAH config form opens: ${fahFormOk}`)
console.log(`page errors: ${errors.length ? errors.join('; ') : 'none'}`)
console.log(`console errors: ${consoleErrors.length ? consoleErrors.join('; ') : 'none'}`)
console.log(`screenshot: ${screenshotPath}`)
console.log(`--- mobile (375x812) ---`)
console.log(`horizontal overflow: ${overflowsHorizontally}`)
console.log(`card titles: ${cardTitleWidths.map((t) => `"${t.text}" (${t.width.toFixed(0)}px)`).join(', ')}`)
console.log(`squeezed titles (<20px, real text): ${squeezedTitles.length ? JSON.stringify(squeezedTitles) : 'none'}`)
console.log(`mobile screenshot: ${mobileScreenshotPath}`)

if (errors.length || title !== 'GridKeeper' || overflowsHorizontally || squeezedTitles.length) {
  console.error('\nFAILED')
  process.exit(1)
}
console.log('\nOK')
