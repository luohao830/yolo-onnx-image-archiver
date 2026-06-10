import { useEffect, useState } from "react";

import {
  deleteUploadedArchives,
  listUploadedArchives,
  type UploadedArchive
} from "../api/client";

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value || "未知";
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function UploadedArchivesPage() {
  const [archives, setArchives] = useState<UploadedArchive[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);

  async function loadArchives() {
    setIsLoading(true);
    try {
      const loaded = await listUploadedArchives();
      setArchives(loaded);
      setSelectedIds((current) => current.filter((id) => loaded.some((archive) => archive.id === id)));
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "加载压缩包列表失败");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadArchives();
  }, []);

  function toggleArchive(archiveId: number) {
    setSelectedIds((current) =>
      current.includes(archiveId)
        ? current.filter((id) => id !== archiveId)
        : [...current, archiveId]
    );
  }

  async function handleDeleteSelected() {
    if (selectedIds.length === 0 || isDeleting) {
      return;
    }

    setIsDeleting(true);
    try {
      await deleteUploadedArchives(selectedIds);
      await loadArchives();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "删除压缩包失败");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <section className="admin-page">
      <div className="page-heading">
        <p className="eyebrow">压缩包管理</p>
        <h1>已上传压缩包</h1>
        <p>查看按 SHA-256 去重保存的压缩包，并删除不再需要的缓存文件。</p>
      </div>

      {errorMessage ? <p className="alert" role="alert">{errorMessage}</p> : null}

      <div className="toolbar">
        <button
          className="button button--danger"
          type="button"
          disabled={selectedIds.length === 0 || isDeleting}
          onClick={() => void handleDeleteSelected()}
        >
          删除选中压缩包
        </button>
      </div>

      <div className="table-card" role="table" aria-label="已上传压缩包">
        <div className="archive-row archive-row--head" role="row">
          <span>选择</span>
          <span>文件名</span>
          <span>SHA-256</span>
          <span>图片数</span>
          <span>大小</span>
          <span>上传时间</span>
        </div>
        {archives.map((archive) => (
          <div className="archive-row" role="row" key={archive.id}>
            <input
              aria-label={`选择 ${archive.original_filename}`}
              type="checkbox"
              checked={selectedIds.includes(archive.id)}
              onChange={() => toggleArchive(archive.id)}
            />
            <strong>{archive.original_filename}</strong>
            <span className="mono-text">{archive.content_sha256}</span>
            <span>{archive.image_count}</span>
            <span>{formatBytes(archive.size_bytes)}</span>
            <span>{formatDate(archive.created_at)}</span>
          </div>
        ))}
      </div>

      {!isLoading && archives.length === 0 ? <p className="muted">暂无已上传压缩包。</p> : null}
      {isLoading ? <p className="muted">正在加载压缩包列表。</p> : null}
    </section>
  );
}
