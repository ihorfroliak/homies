import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { limits } from "./limits";
import { refusalCopy } from "./copy";
import { engagementRoute } from "./analytics";
const contract = JSON.parse(readFileSync("../../docs/api/openapi.json", "utf8"));
it("pins form limits to the generated backend schema", () => {
  const s = contract.components.schemas;
  expect(limits).toEqual({ message: s.MessageIn.properties.body.maxLength, report: s.MessageReportIn.properties.text.anyOf[0].maxLength, viewingNote: s.ViewingRequest.properties.note.anyOf[0].maxLength, attendeesMin: s.ViewingRequest.properties.attendee_count.minimum, attendeesMax: s.ViewingRequest.properties.attendee_count.maximum, searchName: s.SavedSearchCreate.properties.name.maxLength });
});
it("has Polish copy for every stable engagement refusal documented in generated OpenAPI", () => {
  const codes = new Set<string>();
  for (const [path, operations] of Object.entries(contract.paths)) {
    if (!engagementRoute(path.replace(/\{[^}]+\}/g, "sample-id"))) continue;
    for (const operation of Object.values(operations as Record<string, { responses?: Record<string, { description?: string }> }>)) {
      for (const response of Object.values(operation.responses ?? {})) {
        const description = response.description ?? "";
        const pattern = /stable code/i.test(description) ? /`([A-Z][A-Z_]+)`/g : /`([A-Z][A-Z_]+)`:/g;
        for (const match of description.matchAll(pattern)) codes.add(match[1]!);
      }
    }
  }
  expect(codes.size).toBeGreaterThan(15);
  expect([...codes].filter(code => !refusalCopy[code])).toEqual([]);
  expect(Object.keys(refusalCopy).filter(code => !codes.has(code))).toEqual([]);
});
