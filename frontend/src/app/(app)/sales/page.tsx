import { redirect } from "next/navigation";

// /sales was a duplicate of /leads (same KPIs, charts, funnel, and table).
// /leads is the canonical Leads Dashboard — it additionally has filtering,
// pagination, and row→detail. Redirect so any old /sales links keep working.
export default function SalesPage() {
  redirect("/leads");
}
