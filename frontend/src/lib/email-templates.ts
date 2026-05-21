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
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#ecfdf5;padding:40px 0;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <tr><td align="center">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="620" style="background-color:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 4px 20px rgba(6,95,70,0.08);">
      <tr><td style="background:linear-gradient(135deg,#10b981 0%,#047857 100%);padding:48px 40px 40px 40px;text-align:left;">
        <p style="margin:0 0 8px 0;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:rgba(255,255,255,0.85);font-weight:700;">Issue 42 · April 2026</p>
        <h1 style="margin:0;font-size:34px;line-height:40px;color:#ffffff;font-weight:800;letter-spacing:-0.5px;">This Week in Coaching</h1>
        <p style="margin:12px 0 0 0;font-size:16px;line-height:24px;color:rgba(255,255,255,0.92);max-width:480px;">Insights, client wins, and the one thing we'd try this week if we were you.</p>
      </td></tr>
      <tr><td style="padding:36px 40px 8px 40px;">
        <p style="margin:0 0 8px 0;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#10b981;font-weight:700;">Lead Story</p>
        <h2 style="margin:0 0 16px 0;font-size:24px;line-height:32px;color:#111827;font-weight:700;letter-spacing:-0.3px;">The pattern we're seeing across every discovery call this month</h2>
        <p style="margin:0 0 16px 0;font-size:16px;line-height:26px;color:#374151;">Open with a short, punchy paragraph that gives the reader a reason to keep reading. Two or three sentences — what's the one thing they'll get out of this issue?</p>
        <p style="margin:0 0 24px 0;font-size:16px;line-height:26px;color:#374151;">Build on it. Pose a question, share a specific story from last week, or call out a stat that surprised you.</p>
      </td></tr>
      <tr><td style="padding:0 40px 28px 40px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#ecfdf5;border-left:4px solid #10b981;border-radius:6px;">
          <tr><td style="padding:20px 24px;">
            <p style="margin:0;font-size:17px;line-height:26px;color:#065f46;font-style:italic;font-weight:500;">"The quote or stat that anchors this issue. Make it strong enough to stand on its own."</p>
            <p style="margin:10px 0 0 0;font-size:13px;color:#047857;font-weight:600;">— Source / client name</p>
          </td></tr>
        </table>
      </td></tr>
      <tr><td style="padding:0 40px 28px 40px;">
        <h3 style="margin:0 0 14px 0;font-size:15px;letter-spacing:0.5px;text-transform:uppercase;color:#111827;font-weight:700;">What's inside</h3>
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
          <tr><td style="padding:10px 0;border-bottom:1px solid #e5e7eb;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
              <td valign="top" style="padding-right:14px;"><span style="display:inline-block;width:28px;height:28px;background-color:#10b981;color:#ffffff;border-radius:50%;text-align:center;line-height:28px;font-weight:700;font-size:13px;">1</span></td>
              <td valign="top"><p style="margin:0;font-size:15px;line-height:22px;color:#374151;"><strong style="color:#111827;">One actionable insight</strong> from this week's calls.</p></td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:10px 0;border-bottom:1px solid #e5e7eb;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
              <td valign="top" style="padding-right:14px;"><span style="display:inline-block;width:28px;height:28px;background-color:#10b981;color:#ffffff;border-radius:50%;text-align:center;line-height:28px;font-weight:700;font-size:13px;">2</span></td>
              <td valign="top"><p style="margin:0;font-size:15px;line-height:22px;color:#374151;"><strong style="color:#111827;">A client win</strong> worth celebrating.</p></td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:10px 0;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
              <td valign="top" style="padding-right:14px;"><span style="display:inline-block;width:28px;height:28px;background-color:#10b981;color:#ffffff;border-radius:50%;text-align:center;line-height:28px;font-weight:700;font-size:13px;">3</span></td>
              <td valign="top"><p style="margin:0;font-size:15px;line-height:22px;color:#374151;"><strong style="color:#111827;">Something to try</strong> before next Monday.</p></td>
            </tr></table>
          </td></tr>
        </table>
      </td></tr>
      <tr><td align="center" style="padding:8px 40px 40px 40px;">
        <a href="#" style="display:inline-block;background:linear-gradient(135deg,#10b981 0%,#047857 100%);color:#ffffff;text-decoration:none;padding:16px 36px;border-radius:8px;font-weight:700;font-size:16px;letter-spacing:0.3px;box-shadow:0 4px 12px rgba(16,185,129,0.3);">Read the full breakdown →</a>
        <p style="margin:14px 0 0 0;font-size:13px;color:#6b7280;">Takes about 4 minutes.</p>
      </td></tr>
      <tr><td style="padding:24px 40px;background-color:#f9fafb;border-top:1px solid #e5e7eb;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"><tr>
          <td style="font-size:12px;color:#6b7280;line-height:20px;">
            <p style="margin:0 0 6px 0;"><strong style="color:#374151;">Central Intelligence</strong> · Coaching insights, every Friday.</p>
            <p style="margin:0;">You're getting this because you opted in. <a href="#" style="color:#10b981;text-decoration:none;font-weight:600;">Unsubscribe</a> · <a href="#" style="color:#10b981;text-decoration:none;font-weight:600;">Forward to a friend</a></p>
          </td>
        </tr></table>
      </td></tr>
    </table>
  </td></tr>
</table>
`.trim();

const PROMOTIONAL_HTML = `
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#1f2937;padding:40px 0;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <tr><td align="center">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="620" style="background-color:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.4);">
      <tr><td align="center" style="background:linear-gradient(135deg,#dc2626 0%,#f59e0b 100%);padding:56px 40px 48px 40px;color:#ffffff;">
        <p style="margin:0 0 16px 0;display:inline-block;background-color:rgba(0,0,0,0.18);color:#ffffff;padding:8px 16px;border-radius:999px;font-size:11px;letter-spacing:3px;text-transform:uppercase;font-weight:800;">⏰ Limited Time</p>
        <h1 style="margin:0;font-size:54px;line-height:58px;color:#ffffff;font-weight:900;letter-spacing:-1.5px;text-shadow:0 2px 8px rgba(0,0,0,0.18);">Save 30%<br/>This Week Only</h1>
        <p style="margin:16px 0 0 0;font-size:18px;line-height:26px;color:rgba(255,255,255,0.95);max-width:440px;">The one-line promise that makes the offer impossible to scroll past.</p>
      </td></tr>
      <tr><td align="center" style="padding:40px 40px 8px 40px;">
        <h2 style="margin:0 0 18px 0;font-size:26px;line-height:34px;color:#111827;font-weight:800;letter-spacing:-0.4px;">Here's what you get</h2>
        <p style="margin:0 0 24px 0;font-size:16px;line-height:26px;color:#374151;max-width:480px;">One short paragraph explaining what the offer is and why it matters right now. Be specific — what do they get, what does it cost, and why is the deadline real?</p>
      </td></tr>
      <tr><td style="padding:0 40px 24px 40px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
          <tr><td style="padding:14px 18px;background-color:#fef3c7;border-radius:8px;margin-bottom:10px;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"><tr>
              <td valign="top" width="32" style="padding-right:14px;font-size:22px;color:#d97706;">✓</td>
              <td valign="top"><p style="margin:0;font-size:15px;line-height:22px;color:#92400e;"><strong style="color:#78350f;">Tangible benefit</strong> — describe one specific outcome they get.</p></td>
            </tr></table>
          </td></tr>
          <tr><td height="8"></td></tr>
          <tr><td style="padding:14px 18px;background-color:#fef3c7;border-radius:8px;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"><tr>
              <td valign="top" width="32" style="padding-right:14px;font-size:22px;color:#d97706;">✓</td>
              <td valign="top"><p style="margin:0;font-size:15px;line-height:22px;color:#92400e;"><strong style="color:#78350f;">Another concrete thing</strong> — keep these short and specific.</p></td>
            </tr></table>
          </td></tr>
          <tr><td height="8"></td></tr>
          <tr><td style="padding:14px 18px;background-color:#fef3c7;border-radius:8px;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"><tr>
              <td valign="top" width="32" style="padding-right:14px;font-size:22px;color:#d97706;">✓</td>
              <td valign="top"><p style="margin:0;font-size:15px;line-height:22px;color:#92400e;"><strong style="color:#78350f;">The unexpected bonus</strong> — the one that tips them over.</p></td>
            </tr></table>
          </td></tr>
        </table>
      </td></tr>
      <tr><td align="center" style="padding:8px 40px 16px 40px;">
        <a href="#" style="display:inline-block;background:linear-gradient(135deg,#dc2626 0%,#f59e0b 100%);color:#ffffff;text-decoration:none;padding:20px 48px;border-radius:10px;font-weight:800;font-size:18px;letter-spacing:0.5px;box-shadow:0 6px 20px rgba(220,38,38,0.4);">Claim 30% off →</a>
        <p style="margin:14px 0 0 0;font-size:13px;color:#6b7280;">No code needed. Discount applies at checkout.</p>
      </td></tr>
      <tr><td align="center" style="padding:24px 40px;background-color:#fef3c7;border-top:3px dashed #f59e0b;">
        <p style="margin:0;font-size:15px;line-height:22px;color:#78350f;font-weight:700;">⏰ Offer ends Sunday at midnight. No extensions, no exceptions.</p>
      </td></tr>
      <tr><td align="center" style="padding:24px 40px;background-color:#1f2937;">
        <p style="margin:0;font-size:12px;line-height:20px;color:rgba(255,255,255,0.6);">Questions? Just hit reply — these go straight to my inbox.<br/><a href="#" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:600;">Unsubscribe</a></p>
      </td></tr>
    </table>
  </td></tr>
</table>
`.trim();

const WELCOME_HTML = `
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f5f3ff;padding:40px 0;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <tr><td align="center">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="620" style="background-color:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 4px 24px rgba(76,29,149,0.1);">
      <tr><td align="center" style="background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 50%,#ec4899 100%);padding:64px 40px 56px 40px;">
        <div style="display:inline-block;width:96px;height:96px;background-color:#ffffff;border-radius:50%;line-height:96px;font-size:48px;box-shadow:0 8px 24px rgba(0,0,0,0.15);margin-bottom:24px;">👋</div>
        <h1 style="margin:8px 0 0 0;font-size:38px;line-height:46px;color:#ffffff;font-weight:800;letter-spacing:-0.5px;">Welcome aboard</h1>
        <p style="margin:14px 0 0 0;font-size:17px;line-height:26px;color:rgba(255,255,255,0.95);max-width:440px;">We're so glad you're here. Let's get you set up in under five minutes.</p>
      </td></tr>
      <tr><td style="padding:40px 40px 8px 40px;">
        <p style="margin:0 0 18px 0;font-size:17px;line-height:28px;color:#374151;">Hey — quick personal note before we dive in.</p>
        <p style="margin:0 0 18px 0;font-size:17px;line-height:28px;color:#374151;">Thanks for joining. Here's the very first thing I'd love you to do — it takes about 90 seconds and unlocks the rest of what's coming.</p>
        <p style="margin:0 0 28px 0;font-size:17px;line-height:28px;color:#374151;">Replace this with the one specific action you want them to take. The clearer the ask, the higher the response rate.</p>
      </td></tr>
      <tr><td align="center" style="padding:0 40px 40px 40px;">
        <a href="#" style="display:inline-block;background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:#ffffff;text-decoration:none;padding:18px 40px;border-radius:10px;font-weight:700;font-size:17px;letter-spacing:0.3px;box-shadow:0 6px 18px rgba(99,102,241,0.35);">Do the first thing →</a>
        <p style="margin:14px 0 0 0;font-size:13px;color:#6b7280;">About 90 seconds. Promise.</p>
      </td></tr>
      <tr><td style="padding:32px 40px;background:linear-gradient(180deg,#faf5ff 0%,#ffffff 100%);border-top:1px solid #e9d5ff;">
        <p style="margin:0 0 4px 0;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#7c3aed;font-weight:700;">What's Next</p>
        <h3 style="margin:0 0 20px 0;font-size:20px;color:#111827;font-weight:700;letter-spacing:-0.3px;">Here's what to expect this week</h3>
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
          <tr><td style="padding-bottom:16px;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
              <td valign="top" style="padding-right:16px;"><span style="display:inline-block;width:36px;height:36px;background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:#ffffff;border-radius:50%;text-align:center;line-height:36px;font-weight:800;font-size:14px;box-shadow:0 4px 10px rgba(99,102,241,0.25);">1</span></td>
              <td valign="top"><p style="margin:0;font-size:15px;line-height:24px;color:#1f2937;"><strong>Tomorrow:</strong> a short note about the most common stuck point.</p></td>
            </tr></table>
          </td></tr>
          <tr><td style="padding-bottom:16px;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
              <td valign="top" style="padding-right:16px;"><span style="display:inline-block;width:36px;height:36px;background:linear-gradient(135deg,#8b5cf6 0%,#a855f7 100%);color:#ffffff;border-radius:50%;text-align:center;line-height:36px;font-weight:800;font-size:14px;box-shadow:0 4px 10px rgba(139,92,246,0.25);">2</span></td>
              <td valign="top"><p style="margin:0;font-size:15px;line-height:24px;color:#1f2937;"><strong>In a few days:</strong> the one resource that made the biggest difference for past clients.</p></td>
            </tr></table>
          </td></tr>
          <tr><td>
            <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
              <td valign="top" style="padding-right:16px;"><span style="display:inline-block;width:36px;height:36px;background:linear-gradient(135deg,#a855f7 0%,#ec4899 100%);color:#ffffff;border-radius:50%;text-align:center;line-height:36px;font-weight:800;font-size:14px;box-shadow:0 4px 10px rgba(236,72,153,0.25);">3</span></td>
              <td valign="top"><p style="margin:0;font-size:15px;line-height:24px;color:#1f2937;"><strong>End of week:</strong> an invitation to the next live session.</p></td>
            </tr></table>
          </td></tr>
        </table>
      </td></tr>
      <tr><td style="padding:32px 40px;text-align:center;background-color:#ffffff;">
        <p style="margin:0 0 8px 0;font-size:16px;line-height:24px;color:#374151;">Got questions? Just hit reply.</p>
        <p style="margin:0;font-size:14px;line-height:22px;color:#6b7280;">These go straight to my inbox — I read every one.</p>
        <p style="margin:24px 0 0 0;font-size:15px;color:#111827;font-weight:600;">— Greg</p>
      </td></tr>
      <tr><td style="padding:20px 40px;background-color:#f5f3ff;text-align:center;">
        <p style="margin:0;font-size:12px;color:#7c3aed;"><a href="#" style="color:#7c3aed;text-decoration:none;font-weight:600;">Unsubscribe</a> · <a href="#" style="color:#7c3aed;text-decoration:none;font-weight:600;">Update preferences</a></p>
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
