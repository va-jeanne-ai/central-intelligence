"use client";

import {
  useState,
  useRef,
  useCallback,
  type KeyboardEvent,
  type ChangeEvent,
  type FormEvent,
} from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ChatInputProps {
  onSend: (message: string) => void;
  isDisabled?: boolean;
}

// ─── Send icon ────────────────────────────────────────────────────────────────

function SendIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      className="w-4 h-4"
      aria-hidden="true"
    >
      <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
    </svg>
  );
}

// ─── ChatInput ────────────────────────────────────────────────────────────────

export function ChatInput({ onSend, isDisabled = false }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-grow the textarea up to a maximum height.
  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (el === null) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, []);

  const handleChange = useCallback(
    (e: ChangeEvent<HTMLTextAreaElement>) => {
      setValue(e.target.value);
      resizeTextarea();
    },
    [resizeTextarea],
  );

  const submit = useCallback(() => {
    const trimmed = value.trim();
    if (trimmed === "" || isDisabled) return;
    onSend(trimmed);
    setValue("");
    // Reset height after clearing.
    if (textareaRef.current !== null) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, isDisabled, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submit();
      }
    },
    [submit],
  );

  const handleSubmit = useCallback(
    (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      submit();
    },
    [submit],
  );

  const canSend = value.trim() !== "" && !isDisabled;

  return (
    <div className="bg-white border-t border-gray-200 px-5 py-3.5 flex-shrink-0">
      <form onSubmit={handleSubmit} className="flex items-end gap-3">
        {/* Text input */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
          rows={1}
          placeholder="Ask Central Intelligence anything — leads, members, content ideas, optimization..."
          aria-label="Chat message input"
          className={[
            "flex-1 resize-none rounded-3xl bg-gray-50 border border-gray-200 px-4 py-2.5",
            "text-sm text-gray-800 placeholder-gray-400 leading-relaxed outline-none",
            "transition-colors duration-150 overflow-y-hidden",
            "focus:border-indigo-400 focus:bg-white focus:ring-2 focus:ring-indigo-100",
            isDisabled ? "opacity-50 cursor-not-allowed" : "",
          ]
            .filter(Boolean)
            .join(" ")}
          style={{ minHeight: "42px", maxHeight: "160px" }}
        />

        {/* Send button */}
        <button
          type="submit"
          disabled={!canSend}
          aria-label="Send message"
          className={[
            "flex items-center justify-center w-[38px] h-[38px] rounded-full flex-shrink-0",
            "text-white transition-all duration-150",
            canSend
              ? "hover:opacity-90 active:scale-95 shadow-sm"
              : "opacity-40 cursor-not-allowed",
          ]
            .filter(Boolean)
            .join(" ")}
          style={{
            backgroundColor: canSend ? "#6366F1" : "#D1D5DB",
          }}
        >
          <SendIcon />
        </button>
      </form>

      {/* Hint text */}
      <p className="mt-1.5 text-[11px] text-gray-400 text-center select-none">
        Press{" "}
        <kbd className="font-medium text-gray-500">Enter</kbd> to send
        {" · "}
        <kbd className="font-medium text-gray-500">Shift + Enter</kbd> for new line
      </p>
    </div>
  );
}
