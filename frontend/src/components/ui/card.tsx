/**
 * Molecule: Card / CardHeader / CardBody
 *
 * Generic white card container matching mockup's .card, .card-header, .card-body.
 * Composable — use CardHeader and CardBody as children of Card.
 *
 * Usage:
 *   <Card>
 *     <CardHeader title="DM Template Library" action={<span>12 templates</span>} />
 *     <CardBody>...</CardBody>
 *   </Card>
 */

interface CardProps {
  children: React.ReactNode;
  className?: string;
  /** Optional left border color for accent (e.g., offer cards) */
  borderLeftColor?: string;
  /** Opacity — used for draft (0.85) or archived (0.6) states */
  opacity?: number;
}

export function Card({ children, className = "", borderLeftColor, opacity }: CardProps) {
  return (
    <div
      className={`bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden ${className}`}
      style={{
        ...(borderLeftColor ? { borderLeftWidth: 3, borderLeftColor } : {}),
        ...(opacity ? { opacity } : {}),
      }}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  title: string;
  /** Right-side element: count, button, badge, etc. */
  action?: React.ReactNode;
  className?: string;
  noBorder?: boolean;
}

export function CardHeader({ title, action, className = "", noBorder = false }: CardHeaderProps) {
  return (
    <div
      className={`flex items-center justify-between px-5 py-4 ${noBorder ? "" : "border-b border-gray-100"} ${className}`}
    >
      <h2 className="text-sm font-bold text-gray-800">{title}</h2>
      {action && <div className="flex items-center gap-2">{action}</div>}
    </div>
  );
}

interface CardBodyProps {
  children: React.ReactNode;
  className?: string;
  noPadding?: boolean;
}

export function CardBody({ children, className = "", noPadding = false }: CardBodyProps) {
  return (
    <div className={noPadding ? className : `px-5 py-4 ${className}`}>
      {children}
    </div>
  );
}
