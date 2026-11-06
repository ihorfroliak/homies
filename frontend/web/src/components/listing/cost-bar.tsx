import type { components } from "@/api/schema";

import styles from "./cost-bar.module.css";

type Classified = components["schemas"]["ClassifiedOut"];
export type CostParts = Pick<Classified, "rent_amount" | "admin_fee" | "utilities_basis" | "utilities_amount" | "parking_fee">;

/**
 * The 001C cost signature: proportions of the monthly amounts the API returned.
 * Decorative only (the amounts are always written next to it) and it computes no
 * total. Media are hatched when estimated; a basis without an amount draws nothing.
 */
export function CostBar({ listing: l, className }: { listing: CostParts; className?: string }) {
  const utilities = l.utilities_basis === "ESTIMATED" ? l.utilities_amount ?? 0 : 0;
  const parts = [
    { key: "rent", value: l.rent_amount },
    { key: "admin", value: l.admin_fee },
    { key: "parking", value: l.parking_fee },
    { key: "utilities", value: utilities },
  ].filter((p) => p.value > 0);
  if (parts.length < 2) return null;
  return (
    <div className={`${styles.bar} ${className ?? ""}`} aria-hidden="true">
      {parts.map((p) => (
        <span key={p.key} className={styles[p.key]} style={{ flexGrow: p.value }} />
      ))}
    </div>
  );
}
