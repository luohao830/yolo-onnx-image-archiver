import { UploadCloud } from "lucide-react";
import { useCallback, useRef, useState, type DragEvent, type ReactNode } from "react";

import { cn } from "../../lib/utils";

interface DropzoneProps {
  onFiles: (files: File[]) => void;
  accept?: string;
  multiple?: boolean;
  disabled?: boolean;
  className?: string;
  /** 自定义提示文案 */
  hint?: ReactNode;
  children?: ReactNode;
}

/** 拖拽上传区：点击或拖入文件触发 onFiles。 */
export function Dropzone({
  onFiles,
  accept,
  multiple = false,
  disabled = false,
  className,
  hint = "拖拽文件到此处，或点击选择文件",
  children,
}: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(false);
      if (disabled) return;
      const files = Array.from(e.dataTransfer.files ?? []);
      if (files.length) onFiles(files);
    },
    [disabled, onFiles],
  );

  const handlePick = (files: FileList | null) => {
    if (!files) return;
    onFiles(Array.from(files));
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-disabled={disabled}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !disabled) {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragOver(true);
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        setDragOver(false);
      }}
      onDrop={handleDrop}
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed bg-page/60 px-6 py-10 text-center transition-colors",
        dragOver ? "border-brand bg-brand/5" : "border-line-strong",
        disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-brand/60",
        className,
      )}
    >
      <UploadCloud className="h-10 w-10 text-slate-400" aria-hidden />
      {children ?? <p className="text-sm leading-relaxed text-muted">{hint}</p>}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        className="hidden"
        onChange={(e) => {
          handlePick(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
