"use client";

import type { ChatMessage } from "@/types";

// ─── Types ────────────────────────────────────────────────────────────────────

interface AgentIdentity {
  name: string;
  icon: string;
  gradient: string;
}

const CENTRAL_INTELLIGENCE: AgentIdentity = {
  name: "Central Intelligence",
  icon: "👑",
  gradient: "linear-gradient(135deg, #F59E0B 0%, #D97706 100%)",
};

interface MessageBubbleProps {
  message: ChatMessage;
  agent?: AgentIdentity;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTime(date: Date): string {
  return date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

/**
 * Markdown renderer for AI chat responses.
 * Handles: headers, bold, italic, inline code, fenced code blocks,
 * bullet/numbered lists, blockquotes, tables, and horizontal rules.
 */
function renderMarkdown(raw: string): string {
  let html = raw
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Fenced code blocks (``` … ```)
  html = html.replace(
    /```([a-z]*)\n?([\s\S]*?)```/g,
    (_match, _lang, code: string) =>
      `<pre class="bg-gray-100 rounded-md px-3 py-2 my-2 text-sm font-mono overflow-x-auto whitespace-pre-wrap break-words"><code>${code.trim()}</code></pre>`,
  );

  // Tables — detect lines with pipes and convert to HTML table
  html = html.replace(
    /(?:^\|.+\|[ \t]*\n)+/gm,
    (block) => {
      const rows = block.trim().split("\n");
      if (rows.length < 2) return block;

      // Check if second row is separator (|---|---|)
      const isSeparator = (row: string) => /^\|[\s\-:]+\|/.test(row);
      const hasSep = rows.length >= 2 && isSeparator(rows[1]);

      const parseRow = (row: string) =>
        row.split("|").slice(1, -1).map((c) => c.trim());

      let tableHtml = '<div class="overflow-x-auto my-3"><table class="w-full text-sm border-collapse">';

      if (hasSep) {
        // Header row
        const headers = parseRow(rows[0]);
        tableHtml += '<thead><tr class="border-b-2 border-gray-200">';
        headers.forEach((h) => {
          tableHtml += `<th class="text-left px-3 py-2 font-semibold text-gray-700">${h}</th>`;
        });
        tableHtml += "</tr></thead><tbody>";

        // Data rows (skip separator)
        for (let i = 2; i < rows.length; i++) {
          const cells = parseRow(rows[i]);
          tableHtml += '<tr class="border-b border-gray-100 hover:bg-gray-50">';
          cells.forEach((c) => {
            tableHtml += `<td class="px-3 py-2 text-gray-600">${c}</td>`;
          });
          tableHtml += "</tr>";
        }
        tableHtml += "</tbody>";
      } else {
        tableHtml += "<tbody>";
        rows.forEach((row) => {
          const cells = parseRow(row);
          tableHtml += '<tr class="border-b border-gray-100">';
          cells.forEach((c) => {
            tableHtml += `<td class="px-3 py-2 text-gray-600">${c}</td>`;
          });
          tableHtml += "</tr>";
        });
        tableHtml += "</tbody>";
      }

      tableHtml += "</table></div>";
      return tableHtml;
    },
  );

  // Horizontal rules (--- or ***)
  html = html.replace(/^[ \t]*[-*]{3,}[ \t]*$/gm, '<hr class="my-4 border-gray-200" />');

  // Headers (### → h3, ## → h2, # → h1)
  html = html.replace(/^#### (.+)$/gm, '<h4 class="text-sm font-bold text-gray-800 mt-4 mb-1">$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h3 class="text-base font-bold text-gray-900 mt-5 mb-2">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="text-lg font-bold text-gray-900 mt-5 mb-2">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold text-gray-900 mt-5 mb-2">$1</h1>');

  // Blockquotes (&gt; text — since we already escaped >)
  html = html.replace(
    /^&gt; (.+)$/gm,
    '<blockquote class="border-l-3 border-accent-400 bg-accent-50 pl-3 pr-2 py-2 my-2 text-sm italic text-gray-700 rounded-r">$1</blockquote>',
  );

  // Inline code
  html = html.replace(
    /`([^`]+)`/g,
    '<code class="bg-gray-100 rounded px-1 py-0.5 text-sm font-mono">$1</code>',
  );

  // Bold **text** or __text__
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__(.+?)__/g, "<strong>$1</strong>");

  // Italic *text* or _text_
  html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "<em>$1</em>");
  html = html.replace(/(?<!_)_([^_]+)_(?!_)/g, "<em>$1</em>");

  // Unordered list items (- or *)
  html = html.replace(
    /^[ \t]*[-*] (.+)$/gm,
    '<li class="ml-4 list-disc">$1</li>',
  );

  // Ordered list items
  html = html.replace(
    /^[ \t]*\d+\. (.+)$/gm,
    '<li class="ml-4 list-decimal">$1</li>',
  );

  // Wrap consecutive <li> runs
  html = html.replace(
    /(<li class="ml-4 list-disc">[^]*?<\/li>)(\n<li class="ml-4 list-disc">[^]*?<\/li>)*/g,
    (match) => `<ul class="my-2 space-y-1">${match}</ul>`,
  );
  html = html.replace(
    /(<li class="ml-4 list-decimal">[^]*?<\/li>)(\n<li class="ml-4 list-decimal">[^]*?<\/li>)*/g,
    (match) => `<ol class="my-2 space-y-1">${match}</ol>`,
  );

  // Line breaks — preserve newlines not already inside block elements
  html = html.replace(/\n/g, "<br />");

  // Clean up double <br /> after block elements
  html = html.replace(/(<\/h[1-4]>)<br \/>/g, "$1");
  html = html.replace(/(<hr[^>]*\/>)<br \/>/g, "$1");
  html = html.replace(/(<\/table><\/div>)<br \/>/g, "$1");
  html = html.replace(/(<\/blockquote>)<br \/>/g, "$1");
  html = html.replace(/(<\/pre>)<br \/>/g, "$1");
  html = html.replace(/(<\/ul>)<br \/>/g, "$1");
  html = html.replace(/(<\/ol>)<br \/>/g, "$1");

  return html;
}

// ─── Agent avatar ─────────────────────────────────────────────────────────────

function AgentAvatar({ agent }: { agent: AgentIdentity }) {
  return (
    <div
      className="flex items-center justify-center w-9 h-9 rounded-full flex-shrink-0 shadow-sm"
      style={{ background: agent.gradient }}
      aria-hidden="true"
    >
      <span className="text-base leading-none">{agent.icon}</span>
    </div>
  );
}

// ─── User avatar ──────────────────────────────────────────────────────────────

function UserAvatar() {
  return (
    <div
      className="flex items-center justify-center w-9 h-9 rounded-full flex-shrink-0 text-white text-xs font-bold shadow-sm"
      style={{ backgroundColor: "#3B82F6" }}
      aria-hidden="true"
    >
      JD
    </div>
  );
}

// ─── Streaming cursor ─────────────────────────────────────────────────────────

function StreamingCursor() {
  return (
    <span
      className="inline-block w-0.5 h-4 bg-gray-500 ml-0.5 align-middle animate-pulse"
      aria-hidden="true"
      style={{ animationDuration: "0.8s" }}
    />
  );
}

// ─── MessageBubble ────────────────────────────────────────────────────────────

export function MessageBubble({ message, agent = CENTRAL_INTELLIGENCE }: MessageBubbleProps) {
  const isAssistant = message.role === "assistant";

  if (isAssistant) {
    return (
      <div className="flex items-start gap-3 max-w-[80%]">
        <AgentAvatar agent={agent} />

        <div className="flex flex-col gap-1 min-w-0">
          {/* Sender label */}
          <span className="text-xs font-semibold text-gray-500 ml-1">
            {agent.name}
          </span>

          {/* Bubble */}
          <div
            className="relative bg-white border border-gray-200 rounded-2xl rounded-tl-[4px] px-4 py-3 shadow-sm text-sm text-gray-800 leading-relaxed"
            style={{ wordBreak: "break-word" }}
          >
            <div
              // eslint-disable-next-line react/no-danger
              dangerouslySetInnerHTML={{
                __html: renderMarkdown(message.content),
              }}
            />
            {message.isStreaming === true && <StreamingCursor />}
          </div>

          {/* Timestamp */}
          <span className="text-[10px] text-gray-400 ml-1">
            {formatTime(message.timestamp)}
          </span>
        </div>
      </div>
    );
  }

  // User message — right-aligned
  return (
    <div className="flex items-start gap-3 max-w-[80%] self-end flex-row-reverse">
      <UserAvatar />

      <div className="flex flex-col gap-1 items-end min-w-0">
        {/* Sender label */}
        <span className="text-xs font-semibold text-gray-500 mr-1">You</span>

        {/* Bubble */}
        <div
          className="bg-blue-500 rounded-2xl rounded-tr-[4px] px-4 py-3 shadow-sm text-sm text-white leading-relaxed"
          style={{ wordBreak: "break-word" }}
        >
          {/* User messages are plain text — just preserve whitespace */}
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Timestamp */}
        <span className="text-[10px] text-gray-400 mr-1">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  );
}
