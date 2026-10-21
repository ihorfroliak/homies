import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { CostBreakdown } from "./cost-breakdown";
import { monthlyLabel } from "@/components/listing/format";

it("renders authoritative totals and currency even when components are deliberately non-additive", () => {
  const listing = { rent_amount: 100000, admin_fee: 20000, utilities_basis: "ESTIMATED", utilities_amount: 30000, parking_fee: 40000, deposit_amount: 50000, monthly_total_estimate: 987600, move_in_total: 1234500, currency: "EUR", other_costs: "" } as const;
  render(<CostBreakdown listing={listing} />);
  const text = document.body.textContent!.replace(/[\u00a0\u202f]/g, " ");
  expect(text).toContain("9 876"); expect(text).toContain("12 345"); expect(text).toContain("€");
  expect(text).not.toContain("1 900"); expect(text).not.toContain("2 400");
  expect(screen.getByText(monthlyLabel(listing).replace(/[\u00a0\u202f]/g, " "))).toBeVisible();
});
