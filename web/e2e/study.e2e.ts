import { test } from "@e2e-dev/web";
import { expect } from "e2e";

test("keyword completion cites evidence, abstains without it, and recovers", async ({
  app,
  screen,
}) => {
  await app.open("/");
  await screen.getByRole("button", "Complete the note").click();
  await expect(screen.getByRole("status")).toContainText("Schema valid");
  await expect(screen.getByRole("status")).toContainText("The quote appears in the cited excerpt.");
  await expect(
    screen.getByText('{"answer":"is on the desk.","citation":"S1"}', { exact: true }),
  ).toBeVisible();

  await screen.getByRole("button", "Clear excerpts").click();
  await screen.getByRole("button", "Complete the note").click();
  await expect(
    screen.getByText('{"answer":"ABSTAIN","citation":"NONE"}', { exact: true }),
  ).toBeVisible();

  await screen.getByLabel("Excerpt S1").fill("The blue lamp is beside the chair.");
  await screen.getByRole("button", "Complete the note").click();
  await expect(
    screen.getByText('{"answer":"is beside the chair.","citation":"S1"}', { exact: true }),
  ).toBeVisible();
});

test("missing local experiments show an error and navigation recovers", async ({ app, screen }) => {
  await app.open("/qa");
  await expect(screen.getByRole("alert")).toContainText("unavailable or inconsistent");
  await screen.getByRole("link", "Sentence completion").click();
  await screen.getByRole("button", "Complete the note").click();
  await expect(screen.getByRole("status")).toContainText("Schema valid");
});
