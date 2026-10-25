import type { Listing } from "./api";
import { monthlyLabel } from "@/components/listing/format";
import { formatMoney, t } from "@/i18n";
import styles from "@/app/oferta/[id]/detail.module.css";

/** Totals are authoritative API fields, never sums calculated in the UI. */
export function CostBreakdown({ listing: l }: { listing: Pick<Listing, "rent_amount" | "admin_fee" | "utilities_basis" | "utilities_amount" | "parking_fee" | "monthly_total_estimate" | "deposit_amount" | "move_in_total" | "currency" | "other_costs"> }) {
  return (
<section className={styles.costs}>
            <h2 >{t.detail.costs}</h2>
            <p className={styles.total}>{monthlyLabel(l)}</p>
            <dl className={styles.breakdown}>
              <Cost term={t.detail.rent} value={formatMoney(l.rent_amount, l.currency)} />
              {l.admin_fee > 0 ? <Cost term={t.detail.adminFee} value={formatMoney(l.admin_fee, l.currency)} /> : null}
              <Cost
                term={t.detail.utilities}
                value={l.utilities_basis === "INCLUDED" ? t.detail.utilitiesIncluded : l.utilities_basis === "ESTIMATED" ? `${formatMoney(l.utilities_amount, l.currency)} (${t.detail.utilitiesEstimated})` : t.detail.utilitiesNotStated}
              />
              {l.parking_fee > 0 ? <Cost term={t.detail.parkingFee} value={formatMoney(l.parking_fee, l.currency)} /> : null}
              <Cost term={t.detail.monthlyTotal} value={formatMoney(l.monthly_total_estimate, l.currency)} strong />
            </dl>
            {l.utilities_basis === "NOT_STATED" ? <p className="small muted">{t.detail.lowerBoundNote}</p> : null}
            {l.other_costs ? (
              <p className="small">
                <strong>{t.detail.otherCosts}:</strong> {l.other_costs}
              </p>
            ) : null}
            <dl className={styles.breakdown}>
              {l.deposit_amount > 0 ? <Cost term={t.detail.deposit} value={formatMoney(l.deposit_amount, l.currency)} /> : null}
              <Cost term={t.detail.moveInTotal} value={formatMoney(l.move_in_total, l.currency)} strong />
            </dl>
            <p className="small muted">{t.detail.moveInNote}</p>
          </section>
  );
}

function Cost({ term, value, strong = false }: { term: string; value: string; strong?: boolean }) {
  return (
    <div className={strong ? styles.strong : undefined}>
      <dt>{term}</dt>
      <dd>{value}</dd>
    </div>
  );
}
