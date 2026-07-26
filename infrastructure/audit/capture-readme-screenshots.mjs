import { chromium } from 'playwright'

const output = process.env.SCREENSHOT_OUTPUT || '/screenshots'
const username = process.env.SCREENSHOT_USERNAME
const password = process.env.SCREENSHOT_PASSWORD
if (!username || !password) {
  throw new Error('SCREENSHOT_USERNAME and SCREENSHOT_PASSWORD are required')
}

const browser = await chromium.launch()
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  ignoreHTTPSErrors: true,
  locale: 'en-GB',
})
const page = await context.newPage()
const screenshot = async (name) => {
  await page.keyboard.press('Home')
  await page.evaluate(() => {
    document.documentElement.scrollTop = 0
    document.body.scrollTop = 0
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
  })
  await page.waitForTimeout(200)
  await page.screenshot({ path: `${output}/${name}.png` })
}

await page.goto('https://localhost', { waitUntil: 'networkidle' })
await page.selectOption('select', 'en')
await page.getByRole('link', { name: /sign in/i }).click()

await page.locator('#username').fill(username)
await page.locator('#password').fill(password)
await page.locator('#kc-login').click()
await page.waitForURL('https://localhost/**', { timeout: 10000 })
if (page.url().includes('/oidc/')) throw new Error('The evaluation account could not sign in')

await page.waitForLoadState('networkidle')
await page.getByRole('button', { name: /dashboard/i }).click()
await page.waitForTimeout(500)
await screenshot('dashboard')

await page.getByRole('button', { name: /supported people/i }).click()
await page.waitForTimeout(500)
await screenshot('supported-people')

await page.getByRole('button', { name: /schedule/i }).click()
await page.waitForTimeout(500)
await screenshot('schedule')

await browser.close()
