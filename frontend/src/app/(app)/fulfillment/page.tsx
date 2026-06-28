import { redirect } from "next/navigation";

// /fulfillment was a thin summary (KPIs + tools + director CTA) that /members
// now covers in full — same KPIs, plus the member table, and the tools +
// Fulfillment Director CTA were moved onto /members. Redirect so old links work.
export default function FulfillmentPage() {
  redirect("/members");
}
