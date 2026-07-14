"use client";

/**
 * Atom: MarkdownContent
 *
 * Renders LLM-generated markdown (headings, lists, GFM tables, blockquotes)
 * with the app's typography instead of dumping raw `#`/`**`/`|` source in a
 * <pre>. Component mapping keeps sizes on the app's 13px/sm scale — deliberate
 * instead of the typography plugin's prose defaults.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownContent({ markdown }: { markdown: string }) {
  return (
    <div className="min-w-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h3 className="text-base font-bold text-gray-900 mt-5 mb-2 first:mt-0">{children}</h3>
          ),
          h2: ({ children }) => (
            <h3 className="text-sm font-bold text-gray-900 mt-5 mb-2 first:mt-0">{children}</h3>
          ),
          h3: ({ children }) => (
            <h4 className="text-[13px] font-bold text-gray-800 mt-4 mb-1.5 first:mt-0">{children}</h4>
          ),
          p: ({ children }) => (
            <p className="text-sm text-gray-700 leading-relaxed mb-2.5 last:mb-0">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 mb-2.5 space-y-1.5 text-sm text-gray-700">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 mb-2.5 space-y-1.5 text-sm text-gray-700">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent-600 underline">
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-accent-300 bg-accent-50/50 pl-3 py-1 my-2.5 text-sm text-gray-600">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-4 border-gray-100" />,
          code: ({ children }) => (
            <code className="rounded bg-gray-100 px-1 py-0.5 text-[12px] text-gray-800">{children}</code>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-2.5">
              <table className="w-full text-sm border border-gray-200 rounded-md">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
          th: ({ children }) => (
            <th className="px-3 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide text-gray-500 border-b border-gray-200">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 align-top text-gray-700 border-b border-gray-100">{children}</td>
          ),
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
