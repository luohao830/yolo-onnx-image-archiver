import { useMemo, useState } from "react";

import { buildJobImageUrl, type JobDetection } from "../../api/client";
import { cn } from "../../lib/utils";
import { Button } from "../ui/button";

interface DetectionImageViewerProps {
  jobCode: string;
  accessToken: string;
  detections: JobDetection[];
  /** 仅展示含画框图的图片（has_drawn）；否则展示全部。 */
  onlyDrawn?: boolean;
}

/** 置信度颜色编码：≥0.9 绿 / ≥0.7 黄 / <0.7 红，颜色 + 线型双重编码。 */
function confidenceStyle(conf: number): { stroke: string; dash: string } {
  if (conf >= 0.9) return { stroke: "#16a34a", dash: "" };
  if (conf >= 0.7) return { stroke: "#d97706", dash: "6 4" };
  return { stroke: "#dc2626", dash: "2 4" };
}

export function DetectionImageViewer({
  jobCode,
  accessToken,
  detections,
  onlyDrawn = false,
}: DetectionImageViewerProps) {
  const images = useMemo(
    () => (onlyDrawn ? detections.filter((d) => d.has_drawn) : detections),
    [detections, onlyDrawn],
  );
  const [activeIdx, setActiveIdx] = useState(0);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  if (images.length === 0) {
    return (
      <p className="text-sm text-muted">暂无可视化检测结果。开启「绘制检测框」后可在此查看画框图。</p>
    );
  }

  const active = images[Math.min(activeIdx, images.length - 1)];
  const activeSrc = active.drawn_path
    ? buildJobImageUrl(jobCode, accessToken, active.drawn_path)
    : buildJobImageUrl(jobCode, accessToken, active.rel_path ?? active.filename);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_180px]">
      <div className="relative overflow-hidden rounded-lg border border-line bg-card">
        <img
          src={activeSrc}
          alt={active.filename}
          className="block max-h-[520px] w-full object-contain"
        />
        <svg
          viewBox={`0 0 ${active.width || 1} ${active.height || 1}`}
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 h-full w-full"
          aria-label="检测框叠层"
        >
          {active.detections.map((det, i) => {
            const style = confidenceStyle(det.confidence);
            const isHover = hoverIdx === i;
            return (
              <g key={i}>
                <rect
                  x={det.bbox[0]}
                  y={det.bbox[1]}
                  width={Math.max(0, det.bbox[2] - det.bbox[0])}
                  height={Math.max(0, det.bbox[3] - det.bbox[1])}
                  fill="none"
                  stroke={style.stroke}
                  strokeWidth={isHover ? 4 : 2}
                  strokeDasharray={style.dash}
                  opacity={isHover ? 1 : 0.85}
                />
                {isHover ? (
                  <text
                    x={det.bbox[0]}
                    y={Math.max(12, det.bbox[1] - 4)}
                    fill={style.stroke}
                    fontSize={Math.max(12, (active.width || 1) * 0.02)}
                    fontWeight="bold"
                  >
                    {det.label} {(det.confidence * 100).toFixed(0)}%
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-xs text-subtle">
            {activeIdx + 1} / {images.length}
          </span>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="sm"
              disabled={activeIdx === 0}
              onClick={() => setActiveIdx((i) => Math.max(0, i - 1))}
            >
              上一张
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={activeIdx >= images.length - 1}
              onClick={() => setActiveIdx((i) => Math.min(images.length - 1, i + 1))}
            >
              下一张
            </Button>
          </div>
        </div>

        <ul
          className="grid max-h-[480px] grid-cols-3 gap-2 overflow-auto lg:grid-cols-2"
          aria-label="图片缩略图导航"
        >
          {images.map((img, idx) => (
            <li key={`${img.filename}-${idx}`}>
              <button
                type="button"
                onMouseEnter={() => setHoverIdx(null)}
                onClick={() => setActiveIdx(idx)}
                className={cn(
                  "flex flex-col gap-1 rounded-md border p-1 text-left transition-colors",
                  idx === activeIdx ? "border-brand bg-brand/5" : "border-line hover:border-slate-400",
                )}
              >
                <span className="truncate text-[10px] text-muted">{img.filename}</span>
                <span className="text-[10px] font-bold text-ink">
                  {img.detections.length} 框
                </span>
              </button>
            </li>
          ))}
        </ul>

        <div className="flex flex-wrap gap-2 text-[10px] text-muted">
          <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-4 bg-green-600" />≥0.9</span>
          <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-4 bg-amber-600" />≥0.7</span>
          <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-4 bg-red-600" />{"<"}0.7</span>
        </div>
      </div>
    </div>
  );
}
