/** OpenAPI schema bounds; contract.test.ts reads the generated API JSON to pin parity. */
export const limits = { message: 4000, report: 2000, viewingNote: 1000, attendeesMin: 1, attendeesMax: 10, searchName: 80 } as const;
