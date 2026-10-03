// maplibre-gl 6 loads its worker as a module from "./maplibre-gl-worker.mjs"
// next to the bundled chunk, which the bundler does not emit. Serve the
// package's own worker (and the shared chunk it imports) as same-origin static
// files instead; the map sets this URL explicitly (map-canvas.tsx).
import { copyFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pkg = JSON.parse(readFileSync(join(root, "node_modules/maplibre-gl/package.json"), "utf8"));
const target = join(root, "public/vendor", `maplibre-gl-${pkg.version}`);
mkdirSync(target, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(root, "node_modules/maplibre-gl/dist", file), join(target, file));
}
console.log(`map worker → public/vendor/maplibre-gl-${pkg.version}/`);
