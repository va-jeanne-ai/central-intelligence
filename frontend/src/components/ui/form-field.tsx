/**
 * Atom: FormField
 *
 * Consistent form inputs, selects, and textareas.
 * Matches mockup's .form-group, .form-label, .form-input, .form-textarea, .filter-select.
 */

interface FormFieldProps {
  label: string;
  htmlFor?: string;
  children: React.ReactNode;
  className?: string;
}

export function FormField({ label, htmlFor, children, className = "" }: FormFieldProps) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label
        htmlFor={htmlFor}
        className="text-[11px] font-bold uppercase tracking-wider text-gray-500"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

const INPUT_CLASSES =
  "text-[13px] border border-gray-200 rounded-md px-3 py-2 bg-white text-gray-700 placeholder:text-gray-400 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors";

export function FormInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${INPUT_CLASSES} ${props.className ?? ""}`} />;
}

export function FormSelect(props: React.SelectHTMLAttributes<HTMLSelectElement> & { children: React.ReactNode }) {
  return (
    <select
      {...props}
      className={`${INPUT_CLASSES} cursor-pointer ${props.className ?? ""}`}
    >
      {props.children}
    </select>
  );
}

export function FormTextarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`${INPUT_CLASSES} resize-none ${props.className ?? ""}`}
    />
  );
}
