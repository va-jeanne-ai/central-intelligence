"use client";

/**
 * TipTap-based rich-text editor for email composition.
 *
 * Loaded via `next/dynamic` with `ssr: false` from the compose page —
 * TipTap depends on browser-only APIs (window, document). Even with
 * `immediatelyRender: false`, dynamic-import keeps the SSR pass clean.
 *
 * Public API (via ref):
 *   - setContent(html: string): replace the editor body. Used by the
 *     compose page to load a template, dump in AI-generated HTML, or
 *     reset between Save Drafts.
 *
 * The toolbar exposes a Mailchimp-style set of formatting controls plus
 * a "Fill with AI" hook the parent wires to the existing /email/draft
 * endpoint.
 */

import {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useState,
} from "react";
import { useEditor, EditorContent, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
// TipTap v3 consolidated TextStyle + Color into @tiptap/extension-text-style.
// @tiptap/extension-color is a thin re-export of Color from the same package
// for back-compat. Importing both from extension-text-style is the canonical
// v3 path.
import { TextStyle, Color } from "@tiptap/extension-text-style";
import Link from "@tiptap/extension-link";
import Image from "@tiptap/extension-image";

// ─── Public ref API ───────────────────────────────────────────────────────────

export interface EmailEditorHandle {
  setContent: (html: string) => void;
  getHTML: () => string;
}

export interface EmailEditorProps {
  initialHtml?: string;
  onChange?: (html: string) => void;
  onAiAssistClick?: () => void;
  aiBusy?: boolean;
}

// ─── Toolbar primitives ───────────────────────────────────────────────────────

function ToolbarButton({
  onClick,
  active,
  disabled,
  title,
  children,
}: {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
      className={`px-2 py-1 rounded text-sm font-medium border transition-colors ${
        active
          ? "bg-indigo-50 border-indigo-200 text-indigo-700"
          : "bg-white border-transparent text-gray-700 hover:bg-gray-100"
      } disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      {children}
    </button>
  );
}

function ToolbarDivider() {
  return <span aria-hidden className="w-px h-5 bg-gray-200 mx-1" />;
}

// ─── Toolbar ──────────────────────────────────────────────────────────────────

function EditorToolbar({
  editor,
  onAiAssistClick,
  aiBusy,
}: {
  editor: Editor;
  onAiAssistClick?: () => void;
  aiBusy?: boolean;
}) {
  // Inline color state — TipTap's TextStyle/Color extensions expect a string.
  const currentColor =
    (editor.getAttributes("textStyle").color as string | undefined) || "#111827";

  const setLink = useCallback(() => {
    const prev = editor.getAttributes("link").href as string | undefined;
    const url = window.prompt("Link URL", prev ?? "https://");
    if (url === null) return;
    if (url === "") {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
  }, [editor]);

  const insertImage = useCallback(() => {
    const url = window.prompt("Image URL", "https://");
    if (!url) return;
    editor.chain().focus().setImage({ src: url }).run();
  }, [editor]);

  return (
    <div className="flex items-center gap-1 flex-wrap border-b border-gray-200 px-3 py-2 bg-gray-50 rounded-t-lg">
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleBold().run()}
        active={editor.isActive("bold")}
        title="Bold (⌘B)"
      >
        <strong>B</strong>
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleItalic().run()}
        active={editor.isActive("italic")}
        title="Italic (⌘I)"
      >
        <em>I</em>
      </ToolbarButton>

      <ToolbarDivider />

      <ToolbarButton
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        active={editor.isActive("heading", { level: 1 })}
        title="Heading 1"
      >
        H1
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        active={editor.isActive("heading", { level: 2 })}
        title="Heading 2"
      >
        H2
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        active={editor.isActive("heading", { level: 3 })}
        title="Heading 3"
      >
        H3
      </ToolbarButton>

      <ToolbarDivider />

      <ToolbarButton
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        active={editor.isActive("bulletList")}
        title="Bulleted list"
      >
        • List
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        active={editor.isActive("orderedList")}
        title="Numbered list"
      >
        1. List
      </ToolbarButton>

      <ToolbarDivider />

      <ToolbarButton onClick={setLink} active={editor.isActive("link")} title="Link">
        🔗
      </ToolbarButton>
      <ToolbarButton onClick={insertImage} title="Insert image by URL">
        🖼️
      </ToolbarButton>

      <label className="ml-1 inline-flex items-center gap-1 px-2 py-1 rounded border border-transparent hover:bg-gray-100 cursor-pointer" title="Text color">
        <span className="text-sm text-gray-700">A</span>
        <input
          type="color"
          aria-label="Text color"
          value={currentColor}
          onChange={(e) => editor.chain().focus().setColor(e.target.value).run()}
          className="w-5 h-5 border-0 p-0 cursor-pointer bg-transparent"
        />
      </label>

      <ToolbarDivider />

      <ToolbarButton
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!editor.can().undo()}
        title="Undo (⌘Z)"
      >
        ↶
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!editor.can().redo()}
        title="Redo (⌘⇧Z)"
      >
        ↷
      </ToolbarButton>

      {onAiAssistClick && (
        <button
          type="button"
          onClick={onAiAssistClick}
          disabled={aiBusy}
          className="ml-auto inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold hover:bg-amber-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {aiBusy ? "Generating…" : "✨ Fill with AI"}
        </button>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

const EmailEditor = forwardRef<EmailEditorHandle, EmailEditorProps>(function EmailEditor(
  { initialHtml = "", onChange, onAiAssistClick, aiBusy },
  ref,
) {
  // We track a small render counter to force the toolbar to re-evaluate
  // `editor.isActive(...)` after every transaction. TipTap v3 deprecated
  // automatic re-renders on every transaction (perf win); for a Word-like
  // editor we want the toolbar to stay accurate, so we bump a counter on
  // each onUpdate / onSelectionUpdate.
  const [, setTick] = useState(0);

  const editor = useEditor({
    extensions: [
      StarterKit,
      TextStyle,
      Color,
      Link.configure({ openOnClick: false, autolink: true }),
      Image,
    ],
    content: initialHtml,
    immediatelyRender: false,
    onUpdate: ({ editor }) => {
      onChange?.(editor.getHTML());
      setTick((t) => t + 1);
    },
    onSelectionUpdate: () => {
      setTick((t) => t + 1);
    },
    editorProps: {
      attributes: {
        class:
          "prose prose-sm max-w-none min-h-[400px] px-4 py-3 focus:outline-none",
      },
    },
  });

  useImperativeHandle(
    ref,
    () => ({
      setContent: (html: string) => {
        editor?.commands.setContent(html, { emitUpdate: true });
      },
      getHTML: () => editor?.getHTML() ?? "",
    }),
    [editor],
  );

  if (!editor) {
    return (
      <div className="border border-gray-200 rounded-lg min-h-[400px] flex items-center justify-center text-sm text-gray-400">
        Loading editor…
      </div>
    );
  }

  return (
    <div className="border border-gray-200 rounded-lg bg-white">
      <EditorToolbar editor={editor} onAiAssistClick={onAiAssistClick} aiBusy={aiBusy} />
      <EditorContent editor={editor} />
    </div>
  );
});

export default EmailEditor;
