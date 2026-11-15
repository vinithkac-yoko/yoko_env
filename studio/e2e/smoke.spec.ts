import { expect, test } from "@playwright/test";

test("the owner sets up, starts an item, inspects a point at two sizes, adds a maker", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Make the owner account" })).toBeVisible();
  await page.getByLabel("Studio token").fill("e2e-token");
  await page.getByLabel("Your name").fill("Kasi");
  await page.getByLabel("Email").fill("kasi@example.com");
  await page.getByLabel("Password").fill("owner-password-1");
  await page.getByRole("button", { name: "Make the account" }).click();

  await expect(page.getByRole("heading", { name: "Work items" })).toBeVisible();
  await page.getByRole("button", { name: "New item" }).click();
  const form = page.getByTestId("new-item");
  await form.getByRole("combobox", { name: /Recipe \(pick/ }).fill("lengthen_or_shorten");
  await form.getByLabel("Title").fill("A longer skirt");
  await form.getByLabel("A - Skirt Back").check();
  await form.getByRole("button", { name: "Start" }).click();

  await expect(page.getByText("A longer skirt")).toBeVisible();
  const canvas = page.getByTestId("canvas");
  await expect(canvas.locator("[data-point='A7']")).toHaveCount(1);
  await canvas.locator("[data-point='A7'] circle").first().dispatchEvent("mousedown");
  await canvas.locator("[data-point='A7'] circle").first().dispatchEvent("mouseup");
  const inspector = page.getByTestId("inspector");
  await expect(inspector.getByRole("heading", { name: "A7" })).toBeVisible();
  await expect(inspector.getByText("(hip_circ/4)+1.5*#CM")).toBeVisible();
  const at6 = await inspector.getByText(/^x [\d.]+ cm/).textContent();
  await page.getByTestId("size").selectOption({ label: "UK 14 (size 42)" });
  await expect(inspector.getByText(/^x [\d.]+ cm/)).not.toHaveText(at6 ?? "");
  await page.screenshot({ path: "e2e/out/item-uk14.png" });

  await page.getByRole("link", { name: "People" }).click();
  await expect(page.getByRole("heading", { name: "People" })).toBeVisible();
  await page.getByLabel("Name", { exact: true }).fill("Rani");
  await page.getByLabel("Email").fill("rani@example.com");
  await page.getByLabel("Password").fill("maker-password-1");
  await page.getByRole("button", { name: "Add" }).click();
  await expect(page.getByRole("cell", { name: "rani@example.com" })).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("Email").fill("rani@example.com");
  await page.getByLabel("Password").fill("maker-password-1");
  await page.getByRole("button", { name: "Sign in" }).click();
  // Kasi's recipe example stays hidden from Rani until both have finished their own
  await expect(page.getByText(/1 other version is hidden/)).toBeVisible();
});
