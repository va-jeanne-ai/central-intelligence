"use client";

import { useState, useRef, useCallback, DragEvent, ChangeEvent } from "react";
import { apiClient } from "@/lib/api-client";
import type {
  TranscriptCallType,
  TranscriptFileType,
  TranscriptUploadRequest,
  TranscriptUploadResponse,
  TranscribeJobResponse,
} from "@/types";

// ─── Public interface ─────────────────────────────────────────────────────────

export interface TranscriptUploadResult {
  callId?: string;
  jobId?: string;
  status: "processing" | "queued" | "completed";
}

export interface TranscriptUploadWidgetProps {
  callType?: TranscriptCallType;
  leadId?: string;
  callOwner?: string;
  onSuccess?: (result: TranscriptUploadResult) => void;
  className?: string;
}

// ─── Internal types ───────────────────────────────────────────────────────────

type UploadStatus = "idle" | "uploading" | "processing" | "done" | "error";

interface DroppedFile {
  file: File;
  name: string;
  sizeLabel: string;
}

// ─── Accepted file types ──────────────────────────────────────────────────────

const AUDIO_VIDEO_TYPES = new Set([
  "video/mp4",
  "video/quicktime",
  "video/webm",
  "audio/mpeg",
  "audio/mp4",
  "audio/x-m4a",
  "audio/wav",
  "audio/x-wav",
  "audio/webm",
]);

const AUDIO_VIDEO_EXTENSIONS = new Set([
  "mp4", "mov", "mp3", "wav", "m4a", "webm",
]);

const TRANSCRIPT_TYPES = new Set([
  "text/plain",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);

const ACCEPTED_EXTENSIONS = ".mp4,.mov,.mp3,.wav,.m4a,.webm,.txt,.pdf,.docx";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getTranscriptFileType(file: File): TranscriptFileType | null {
  const ext = file.name.split(".").pop()?.toLowerCase();
  if (ext === "txt") return "txt";
  if (ext === "pdf") return "pdf";
  if (ext === "docx") return "docx";
  return null;
}

function isAudioVideo(file: File): boolean {
  if (AUDIO_VIDEO_TYPES.has(file.type)) return true;
  const ext = file.name.split(".").pop()?.toLowerCase();
  return ext !== undefined && AUDIO_VIDEO_EXTENSIONS.has(ext);
}

function isTranscriptFile(file: File): boolean {
  const ext = file.name.split(".").pop()?.toLowerCase();
  return (
    TRANSCRIPT_TYPES.has(file.type) ||
    ext === "txt" ||
    ext === "pdf" ||
    ext === "docx"
  );
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip the data URL prefix: "data:<mime>;base64,"
      const base64 = result.split(",")[1];
      if (base64 === undefined) {
        reject(new Error("Failed to read file as base64"));
        return;
      }
      resolve(base64);
    };
    reader.onerror = () => reject(new Error("FileReader error"));
    reader.readAsDataURL(file);
  });
}

// Simulate progress for non-XHR submits. Ticks every intervalMs up to maxPercent,
// then waits for the caller to call the returned `complete` function.
function simulateProgress(
  setProgress: (p: number) => void,
  estimatedMs = 8000,
): { complete: () => void } {
  const intervalMs = 200;
  const maxPercent = 90;
  const steps = estimatedMs / intervalMs;
  const increment = maxPercent / steps;
  let current = 0;

  const id = setInterval(() => {
    current = Math.min(current + increment, maxPercent);
    setProgress(Math.round(current));
  }, intervalMs);

  const complete = () => {
    clearInterval(id);
    setProgress(100);
  };

  return { complete };
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ProgressBar({ percent }: { percent: number }) {
  return (
    <div
      className="w-full bg-gray-200 rounded-full h-2 overflow-hidden"
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full bg-indigo-400 rounded-full transition-all duration-200"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

function Spinner() {
  return (
    <svg
      className="animate-spin w-5 h-5 text-indigo-500"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function TranscriptUploadWidget({
  callType,
  leadId,
  callOwner,
  onSuccess,
  className = "",
}: TranscriptUploadWidgetProps) {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [isDragOver, setIsDragOver] = useState(false);
  const [videoUrl, setVideoUrl] = useState("");
  const [droppedFile, setDroppedFile] = useState<DroppedFile | null>(null);
  const [progress, setProgress] = useState(0);
  const [processingPercent, setProcessingPercent] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [resultCallId, setResultCallId] = useState<string | undefined>();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ─── Reset to idle ──────────────────────────────────────────────────────────

  const reset = useCallback(() => {
    setStatus("idle");
    setProgress(0);
    setProcessingPercent(null);
    setErrorMessage("");
    setDroppedFile(null);
    setVideoUrl("");
    setResultCallId(undefined);
  }, []);

  // ─── Submit URL (Mode A) ────────────────────────────────────────────────────

  const handleUrlSubmit = useCallback(async () => {
    const trimmed = videoUrl.trim();
    if (!trimmed) return;

    setStatus("uploading");
    setProgress(0);

    const { complete } = simulateProgress(setProgress, 3000);

    try {
      const payload: { videoUrl: string; callType?: TranscriptCallType; leadId?: string } = {
        videoUrl: trimmed,
      };
      if (callType !== undefined) payload.callType = callType;
      if (leadId !== undefined) payload.leadId = leadId;

      const data = await apiClient.post<TranscribeJobResponse>(
        "/transcribe",
        payload,
        { silent: true },
      );

      complete();
      setStatus("processing");

      const result: TranscriptUploadResult = {
        jobId: data.jobId,
        status: data.status === "queued" ? "queued" : "processing",
      };

      onSuccess?.(result);

      // Move to done after a short delay so the user sees "processing"
      setTimeout(() => {
        setStatus("done");
      }, 1500);
    } catch (err) {
      complete();
      setStatus("error");
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to submit video URL. Please try again.",
      );
    }
  }, [videoUrl, callType, leadId, onSuccess]);

  // ─── Handle file drop / select ──────────────────────────────────────────────

  const processFile = useCallback(
    async (file: File) => {
      if (!isAudioVideo(file) && !isTranscriptFile(file)) {
        setStatus("error");
        setErrorMessage(
          "Unsupported file type. Please upload an mp4, mov, mp3, wav, m4a, webm, txt, pdf, or docx file.",
        );
        return;
      }

      setDroppedFile({
        file,
        name: file.name,
        sizeLabel: formatBytes(file.size),
      });

      setStatus("uploading");
      setProgress(0);

      if (isAudioVideo(file)) {
        // Multipart upload to /v1/transcribe/upload
        const { complete } = simulateProgress(setProgress, 10000);

        try {
          const formData = new FormData();
          formData.append("file", file);
          if (callType !== undefined) formData.append("callType", callType);
          if (leadId !== undefined) formData.append("leadId", leadId);

          const token = apiClient.getToken();
          const headers: HeadersInit = {};
          if (token !== null) {
            headers["Authorization"] = `Bearer ${token}`;
          }

          const apiBase =
            process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

          const response = await fetch(`${apiBase}/transcribe/upload`, {
            method: "POST",
            headers,
            body: formData,
          });

          if (!response.ok) {
            let msg = `Upload failed (${response.status})`;
            try {
              const body = (await response.json()) as { message?: string; detail?: string };
              msg = body.message ?? body.detail ?? msg;
            } catch {
              // Non-JSON body — use default message.
            }
            throw new Error(msg);
          }

          const data = (await response.json()) as TranscribeJobResponse;

          complete();
          setStatus("processing");

          const result: TranscriptUploadResult = {
            jobId: data.jobId,
            status: data.status === "queued" ? "queued" : "processing",
          };

          onSuccess?.(result);

          setTimeout(() => {
            setStatus("done");
          }, 1500);
        } catch (err) {
          setStatus("error");
          setErrorMessage(
            err instanceof Error ? err.message : "Upload failed. Please try again.",
          );
        }
      } else {
        // Transcript file — read as base64, then POST JSON
        const fileType = getTranscriptFileType(file);
        if (fileType === null) {
          setStatus("error");
          setErrorMessage("Unrecognized transcript file extension.");
          return;
        }

        const { complete } = simulateProgress(setProgress, 5000);

        try {
          const base64Content = await readFileAsBase64(file);

          const payload: TranscriptUploadRequest = {
            file_content: base64Content,
            file_name: file.name,
            file_type: fileType,
          };
          if (callOwner !== undefined) payload.call_owner = callOwner;
          if (callType !== undefined) payload.call_type = callType;

          const data = await apiClient.post<TranscriptUploadResponse>(
            "/ci/transcripts/upload",
            payload,
            { silent: true },
          );

          complete();
          setResultCallId(data.call_id);
          setStatus("processing");

          const result: TranscriptUploadResult = {
            callId: data.call_id,
            status: "processing",
          };

          onSuccess?.(result);

          setTimeout(() => {
            setStatus("done");
          }, 1500);
        } catch (err) {
          setStatus("error");
          setErrorMessage(
            err instanceof Error ? err.message : "Upload failed. Please try again.",
          );
        }
      }
    },
    [callType, leadId, callOwner, onSuccess],
  );

  // ─── Drag-and-drop events ───────────────────────────────────────────────────

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      const files = Array.from(e.dataTransfer.files);
      const first = files[0];
      if (first !== undefined) {
        void processFile(first);
      }
    },
    [processFile],
  );

  const handleFileInputChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file !== undefined) {
        void processFile(file);
      }
      // Reset so the same file can be re-selected after an error
      e.target.value = "";
    },
    [processFile],
  );

  // ─── Derived drop-zone classes ──────────────────────────────────────────────

  const dropZoneClasses = [
    "border-2 border-dashed rounded-xl p-6 text-center transition-all duration-150",
    isDragOver
      ? "border-indigo-400 bg-indigo-50"
      : "border-gray-300 bg-gray-50",
  ].join(" ");

  // ─── Render ─────────────────────────────────────────────────────────────────

  return (
    <div
      className={`bg-white rounded-xl border border-gray-200 p-5 shadow-sm ${className}`}
    >
      {/* ── Status: uploading ── */}
      {status === "uploading" && (
        <div className="flex flex-col items-center gap-4 py-4">
          <span className="text-2xl" aria-hidden="true">
            📹
          </span>
          <p className="text-sm font-medium text-gray-700">
            {droppedFile !== null
              ? `Uploading ${droppedFile.name}…`
              : "Submitting video URL…"}
          </p>
          <div className="w-full max-w-lg">
            <ProgressBar percent={progress} />
          </div>
          <p className="text-xs text-gray-400">{progress}% complete</p>
        </div>
      )}

      {/* ── Status: processing ── */}
      {status === "processing" && (
        <div className="flex flex-col items-center gap-3 py-4">
          <Spinner />
          <p className="text-sm font-medium text-gray-700">Transcribing…</p>
          {processingPercent !== null && (
            <p className="text-xs text-gray-400">{processingPercent}% complete</p>
          )}
        </div>
      )}

      {/* ── Status: done ── */}
      {status === "done" && (
        <div className="flex flex-col items-center gap-3 py-4">
          <span
            className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center text-green-600 text-xl"
            aria-hidden="true"
          >
            ✓
          </span>
          <p className="text-sm font-semibold text-gray-800">Transcript ready</p>
          {resultCallId !== undefined && (
            <p className="text-xs text-gray-400">Call ID: {resultCallId}</p>
          )}
          <button
            type="button"
            onClick={reset}
            className="mt-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
          >
            Submit another recording
          </button>
        </div>
      )}

      {/* ── Status: error ── */}
      {status === "error" && (
        <div className="flex flex-col items-center gap-3 py-4">
          <span
            className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-red-600 text-xl"
            aria-hidden="true"
          >
            !
          </span>
          <p className="text-sm font-semibold text-red-700">Upload failed</p>
          {errorMessage !== "" && (
            <p className="text-xs text-gray-500 text-center max-w-md">{errorMessage}</p>
          )}
          <button
            type="button"
            onClick={reset}
            className="mt-1 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            Try again
          </button>
        </div>
      )}

      {/* ── Status: idle ── */}
      {status === "idle" && (
        <div
          className={dropZoneClasses}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          role="region"
          aria-label="File upload drop zone"
        >
          {/* Icon */}
          <span className="text-3xl" aria-hidden="true">
            📹
          </span>

          {/* Title */}
          <p className="mt-2 font-bold text-gray-700">
            Submit Video for Transcription &amp; Analysis
          </p>

          {/* Subtitle */}
          <p className="mt-1 text-xs text-gray-400">
            Paste a URL, or drag &amp; drop a video / audio / transcript file
          </p>

          {/* URL input row */}
          <div className="mt-4 flex gap-2 max-w-lg mx-auto">
            <input
              type="url"
              placeholder="https://loom.com/share/... or Google Drive / direct URL"
              value={videoUrl}
              onChange={(e) => setVideoUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleUrlSubmit();
              }}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 focus:outline-none focus:ring-2 focus:ring-indigo-300/50 focus:border-indigo-400 transition-all"
              aria-label="Video URL"
            />
            <button
              type="button"
              onClick={() => void handleUrlSubmit()}
              disabled={videoUrl.trim() === ""}
              className="bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-200 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              Submit
            </button>
          </div>

          {/* Divider */}
          <div className="mt-4 flex items-center gap-3 max-w-lg mx-auto">
            <div className="flex-1 border-t border-gray-200" />
            <span className="text-xs text-gray-400 font-medium">or</span>
            <div className="flex-1 border-t border-gray-200" />
          </div>

          {/* File picker */}
          <div className="mt-3">
            {droppedFile !== null ? (
              <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg text-sm text-gray-700">
                <span aria-hidden="true">📄</span>
                <span className="font-medium">{droppedFile.name}</span>
                <span className="text-gray-400 text-xs">{droppedFile.sizeLabel}</span>
                <button
                  type="button"
                  onClick={() => setDroppedFile(null)}
                  className="ml-1 text-gray-400 hover:text-gray-600"
                  aria-label="Remove selected file"
                >
                  ×
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="text-sm text-indigo-600 hover:text-indigo-700 font-medium underline underline-offset-2"
              >
                Choose a file
              </button>
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_EXTENSIONS}
              className="sr-only"
              tabIndex={-1}
              aria-hidden="true"
              onChange={handleFileInputChange}
            />
          </div>

          {/* Accepted format hint */}
          <p className="mt-3 text-[11px] text-gray-300">
            mp4 · mov · mp3 · wav · m4a · webm · txt · pdf · docx
          </p>
        </div>
      )}

      {/* Hidden processing-percent setter — exposed via prop if parent needs it */}
      {/* (kept as internal state; consumer uses onSuccess callback) */}
    </div>
  );
}
