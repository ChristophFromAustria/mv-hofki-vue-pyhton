import { test, expect } from "@playwright/test";

test("homepage loads and displays title", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("mv_hofki");
});

test("navbar is visible with brand link", async ({ page }) => {
  await page.goto("/");
  const nav = page.locator("nav");
  await expect(nav).toBeVisible();
  await expect(nav).toContainText("mv_hofki");
});

test("home link navigates to homepage", async ({ page }) => {
  await page.goto("/");
  await page.click('nav a[href="/"]');
  await expect(page.locator("h1")).toContainText("mv_hofki");
});
