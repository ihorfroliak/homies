// Fails when the committed API types differ from a fresh generation
// (regenerate with `npm run gen:api` after changing docs/api/openapi.json).
import { readFileSync, rmSync } from "node:fs";

const [committed, fresh] = process.argv.slice(2);
const a = readFileSync(committed, "utf8").replace(/\r\n/g, "\n");
const b = readFileSync(fresh, "utf8").replace(/\r\n/g, "\n");
rmSync(fresh);
if (a !== b) {
  console.error(`${committed} is stale: run \`npm run gen:api\` and commit the result.`);
  process.exit(1);
}
console.log(`${committed} matches docs/api/openapi.json`);
