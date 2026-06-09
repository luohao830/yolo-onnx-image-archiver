import type { ChangeEvent } from "react";


interface UploadFieldProps {
  id: string;
  label: string;
  accept?: string;
  selectedFile: File | null;
  onFileChange: (file: File | null) => void;
}

export function UploadField({
  id,
  label,
  accept,
  selectedFile,
  onFileChange
}: UploadFieldProps) {
  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onFileChange(event.target.files?.[0] ?? null);
  }

  return (
    <div>
      <label htmlFor={id}>{label}</label>
      <input id={id} type="file" accept={accept} onChange={handleChange} />
      {selectedFile ? <p>已选择：{selectedFile.name}</p> : null}
    </div>
  );
}
