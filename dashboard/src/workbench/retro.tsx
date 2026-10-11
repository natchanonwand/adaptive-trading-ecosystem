import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from 'react';

export function StatusBadge({ status, className = '' }: { status: string; className?: string }) {
  const normalized = status.toUpperCase().replaceAll(' ', '_');
  const tone = /BLOCKED|FAILED|FAILURE|DENIED/.test(normalized)
    ? 'danger'
    : /UNKNOWN/.test(normalized)
      ? 'unknown'
      : /FROZEN|LOCKED/.test(normalized)
        ? 'frozen'
        : /RUNNING/.test(normalized)
          ? 'running'
          : /VERIFIED|COMPLETE|PUBLISHED/.test(normalized)
            ? 'success'
            : /READY/.test(normalized)
              ? 'ready'
              : /WARNING|PENDING/.test(normalized)
                ? 'warning'
                : 'info';
  return (
    <span className={`rt-status ${className}`} data-tone={tone}>
      <span aria-hidden="true">■</span> {status.replaceAll('_', ' ')}
    </span>
  );
}
export function Button({
  variant = 'secondary',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
}) {
  return (
    <button {...props} className={`rt-button rt-button--${variant} ${props.className ?? ''}`} />
  );
}
export function SectionHeader({
  title,
  eyebrow,
  actions,
}: {
  title: string;
  eyebrow?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="rt-section-header">
      <div>
        {eyebrow && <p className="rt-label">{eyebrow}</p>}
        <h3>{title}</h3>
      </div>
      {actions}
    </div>
  );
}
export function RetroPanel({
  title,
  icon = '▣',
  status,
  actions,
  footer,
  children,
}: {
  title: string;
  icon?: ReactNode;
  status?: string;
  actions?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rt-window" aria-label={title}>
      <header className="rt-window-title">
        <h3>
          <span aria-hidden="true">{icon}</span> {title}
        </h3>
        <div>
          {status && <StatusBadge status={status} />}
          {actions}
        </div>
      </header>
      <div className="rt-window-body">{children}</div>
      {footer && <footer>{footer}</footer>}
    </section>
  );
}
export const RetroWindow = RetroPanel;
export function Field({
  label,
  help,
  error,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; help?: string; error?: string }) {
  return (
    <label className="rt-field">
      {label}
      <input {...props} aria-invalid={error ? true : props['aria-invalid']} />
      {help && <span className="rt-help">{help}</span>}
      {error && <span role="alert">{error}</span>}
    </label>
  );
}
export function Select({
  label,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  return (
    <label className="rt-field">
      {label}
      <select {...props}>{children}</select>
    </label>
  );
}
export function Checkbox({
  label,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="rt-check">
      <input {...props} type="checkbox" />
      {label}
    </label>
  );
}
export function Tabs({
  items,
  current,
  onChange,
}: {
  items: string[];
  current: string;
  onChange: (value: string) => void;
}) {
  return (
    <nav className="rt-tabs" aria-label="Sections">
      {items.map((name) => (
        <Button
          key={name}
          aria-current={current === name ? 'page' : undefined}
          onClick={() => onChange(name)}
        >
          {name}
        </Button>
      ))}
    </nav>
  );
}
export function MonoValue({ value }: { value: string | number | null }) {
  return (
    <code className="rt-mono" aria-label={value === null ? 'Unavailable' : undefined}>
      {value === null ? '—' : value}
    </code>
  );
}
export function IdentityField({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rt-identity">
      <dt>{label}</dt>
      <dd>
        <MonoValue value={value} />
      </dd>
    </div>
  );
}
export function MetricCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string | number | null;
  note?: string;
}) {
  return (
    <div className="rt-metric">
      <dt>{label}</dt>
      <dd className="rt-numeric" aria-label={value === null ? 'Unavailable' : undefined}>
        {value === null ? '—' : value}
      </dd>
      {note && <small>{note}</small>}
    </div>
  );
}
export function MetricStrip({ children }: { children: ReactNode }) {
  return <dl className="rt-metric-strip">{children}</dl>;
}
export function DataTable({
  caption,
  columns,
  children,
}: {
  caption: string;
  columns: string[];
  children: ReactNode;
}) {
  return (
    <div className="rt-table-scroll" role="region" aria-label={caption} tabIndex={0}>
      <table className="rt-table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            {columns.map((name) => (
              <th scope="col" key={name}>
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
export function Callout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <aside className="rt-callout">
      <strong>{title}</strong>
      <p>{children}</p>
    </aside>
  );
}
export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rt-empty">
      <h3>{title}</h3>
      {children}
    </div>
  );
}
