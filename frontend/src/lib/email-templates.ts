/**
 * Starter email templates for the compose flow.
 *
 * Each `html` is a self-contained, Gmail-safe HTML string:
 *   - Tables for layout (Gmail strips floats, ignores most flexbox)
 *   - Inline styles only (Gmail strips <style> blocks for some senders)
 *   - No external CSS, no JS, no <script>
 *   - Web-safe fonts; specific fonts named for clients that support them
 *
 * The compose page loads `html` into a TipTap editor; the user edits text,
 * colors, images. The edited HTML lands in email_campaigns.body_html.
 *
 * Adding a template: append to EMAIL_TEMPLATES. No registry sync needed —
 * the compose page reads this array directly.
 */

export interface EmailTemplate {
  id: string;
  name: string;
  description: string;
  thumbnail: string; // emoji
  html: string;
}

const NEWSLETTER_HTML = `
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f6f7f9;padding:24px 0;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <tr><td align="center">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="background-color:#ffffff;border-radius:8px;overflow:hidden;">
      <tr><td style="padding:32px 32px 16px 32px;border-bottom:1px solid #e5e7eb;">
        <h1 style="margin:0;font-size:24px;line-height:32px;color:#111827;">This Week in Coaching</h1>
        <p style="margin:8px 0 0 0;font-size:14px;color:#6b7280;">Issue #42 · Insights, wins, and what's next</p>
      </td></tr>
      <tr><td style="padding:24px 32px;">
        <h2 style="margin:0 0 12px 0;font-size:18px;line-height:24px;color:#111827;">Headline goes here</h2>
        <p style="margin:0 0 16px 0;font-size:16px;line-height:24px;color:#374151;">Open with a short, punchy paragraph that gives the reader a reason to keep reading. Two or three sentences — what's the one thing they'll get out of this issue?</p>
        <p style="margin:0 0 16px 0;font-size:16px;line-height:24px;color:#374151;">Add a follow-up paragraph. Build on the first idea. Maybe pose a question, or share a specific story from last week.</p>
      </td></tr>
      <tr><td style="padding:0 32px 24px 32px;">
        <h3 style="margin:0 0 8px 0;font-size:16px;color:#111827;">What you'll find inside</h3>
        <ul style="margin:0;padding-left:20px;font-size:15px;line-height:22px;color:#374151;">
          <li>One actionable insight from this week's calls</li>
          <li>A client win worth celebrating</li>
          <li>Something to try before next Monday</li>
        </ul>
      </td></tr>
      <tr><td align="center" style="padding:8px 32px 32px 32px;">
        <a href="#" style="display:inline-block;background-color:#10b981;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:15px;">Read the full breakdown →</a>
      </td></tr>
      <tr><td style="padding:16px 32px;background-color:#f9fafb;border-top:1px solid #e5e7eb;text-align:center;">
        <p style="margin:0;font-size:12px;color:#9ca3af;">You're receiving this because you opted in. <a href="#" style="color:#9ca3af;">Unsubscribe</a></p>
      </td></tr>
    </table>
  </td></tr>
</table>
`.trim();

const PROMOTIONAL_HTML = `
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#fffbeb;padding:24px 0;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <tr><td align="center">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="background-color:#ffffff;border-radius:8px;overflow:hidden;border:2px solid #f59e0b;">
      <tr><td align="center" style="padding:40px 32px 24px 32px;background-color:#f59e0b;color:#ffffff;">
        <p style="margin:0;font-size:14px;letter-spacing:2px;text-transform:uppercase;">Limited Time Offer</p>
        <h1 style="margin:8px 0 0 0;font-size:32px;line-height:40px;">Save 30% This Week</h1>
      </td></tr>
      <tr><td align="center" style="padding:32px;">
        <h2 style="margin:0 0 16px 0;font-size:22px;line-height:30px;color:#111827;">The headline that makes them stop scrolling</h2>
        <p style="margin:0 0 16px 0;font-size:16px;line-height:24px;color:#374151;">One paragraph explaining what the offer is and why it matters right now. Be specific — what do they get, what does it cost, and why is the deadline real?</p>
      </td></tr>
      <tr><td align="center" style="padding:0 32px 16px 32px;">
        <a href="#" style="display:inline-block;background-color:#f59e0b;color:#ffffff;text-decoration:none;padding:16px 40px;border-radius:6px;font-weight:700;font-size:17px;letter-spacing:0.5px;">Claim the offer →</a>
      </td></tr>
      <tr><td style="padding:16px 32px;border-top:1px solid #fde68a;">
        <p style="margin:0;font-size:14px;line-height:20px;color:#92400e;text-align:center;">⏰ Offer ends Sunday at midnight. No extensions.</p>
      </td></tr>
      <tr><td style="padding:24px 32px;">
        <h3 style="margin:0 0 12px 0;font-size:16px;color:#111827;">What's included</h3>
        <ul style="margin:0;padding-left:20px;font-size:15px;line-height:24px;color:#374151;">
          <li>Bullet one — describe a tangible benefit</li>
          <li>Bullet two — another concrete thing they get</li>
          <li>Bullet three — the bonus or unexpected extra</li>
        </ul>
      </td></tr>
      <tr><td style="padding:16px 32px;background-color:#fffbeb;text-align:center;">
        <p style="margin:0;font-size:12px;color:#92400e;"><a href="#" style="color:#92400e;">Unsubscribe</a> · Questions? Just reply.</p>
      </td></tr>
    </table>
  </td></tr>
</table>
`.trim();

const WELCOME_HTML = `
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#eef2ff;padding:24px 0;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <tr><td align="center">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="background-color:#ffffff;border-radius:8px;overflow:hidden;">
      <tr><td align="center" style="padding:48px 32px 24px 32px;">
        <div style="font-size:48px;line-height:48px;margin-bottom:8px;">👋</div>
        <h1 style="margin:8px 0 0 0;font-size:28px;line-height:36px;color:#111827;">Welcome aboard</h1>
        <p style="margin:8px 0 0 0;font-size:16px;line-height:24px;color:#6b7280;">Let's get you set up in under five minutes.</p>
      </td></tr>
      <tr><td style="padding:0 32px 24px 32px;">
        <p style="margin:0 0 16px 0;font-size:16px;line-height:24px;color:#374151;">Thanks for joining. Here's the very first thing I'd love you to do — it takes about 90 seconds and unlocks the rest of what's coming.</p>
        <p style="margin:0 0 24px 0;font-size:16px;line-height:24px;color:#374151;">Replace this paragraph with the one specific action you want them to take in this first email. The clearer the ask, the higher the response rate.</p>
      </td></tr>
      <tr><td align="center" style="padding:0 32px 32px 32px;">
        <a href="#" style="display:inline-block;background-color:#6366f1;color:#ffffff;text-decoration:none;padding:14px 32px;border-radius:6px;font-weight:600;font-size:16px;">Do the first thing →</a>
      </td></tr>
      <tr><td style="padding:24px 32px;background-color:#f9fafb;border-top:1px solid #e5e7eb;">
        <h3 style="margin:0 0 12px 0;font-size:15px;color:#111827;">What to expect next</h3>
        <ol style="margin:0;padding-left:20px;font-size:14px;line-height:22px;color:#4b5563;">
          <li>Tomorrow: a short note about the most common stuck point</li>
          <li>In a few days: the one resource that made the biggest difference for past clients</li>
          <li>End of week: an invitation to the next live session</li>
        </ol>
      </td></tr>
      <tr><td style="padding:24px 32px;text-align:center;">
        <p style="margin:0;font-size:14px;line-height:20px;color:#374151;">Got questions? Just hit reply — these go straight to my inbox.</p>
      </td></tr>
      <tr><td style="padding:16px 32px;background-color:#f9fafb;text-align:center;border-top:1px solid #e5e7eb;">
        <p style="margin:0;font-size:12px;color:#9ca3af;"><a href="#" style="color:#9ca3af;">Unsubscribe</a></p>
      </td></tr>
    </table>
  </td></tr>
</table>
`.trim();

export const EMAIL_TEMPLATES: EmailTemplate[] = [
  {
    id: "newsletter",
    name: "Newsletter",
    description: "Recurring update with a headline, two short paragraphs, a bulleted highlight list, and one CTA.",
    thumbnail: "📰",
    html: NEWSLETTER_HTML,
  },
  {
    id: "promotional",
    name: "Promotional / Sale",
    description: "Time-limited offer with an amber accent bar, big headline, prominent CTA, and a deadline reminder.",
    thumbnail: "🏷️",
    html: PROMOTIONAL_HTML,
  },
  {
    id: "welcome",
    name: "Welcome / Re-engagement",
    description: "Friendly first-touch with a single clear ask, what-to-expect-next checklist, and reply prompt.",
    thumbnail: "👋",
    html: WELCOME_HTML,
  },
];

export function getTemplate(id: string): EmailTemplate | undefined {
  return EMAIL_TEMPLATES.find((t) => t.id === id);
}
