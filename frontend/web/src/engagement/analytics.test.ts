import { expect, it } from "vitest";
import { engagementRoute } from "./analytics";
it("reduces resource IDs and query data to approved templates and refuses unknown paths", () => {
  expect(engagementRoute("/v1/conversations/550e8400-e29b-41d4-a716-446655440000/messages?text=private")).toBe("/v1/conversations/[id]/messages");
  expect(engagementRoute("/v1/me/saved-searches?query=private")).toBe("/v1/me/saved-searches");
  expect(engagementRoute("/v1/private/email@example.com")).toBeUndefined();
  expect(engagementRoute("https://private.invalid/v1/me/viewings")).toBeUndefined();
});
