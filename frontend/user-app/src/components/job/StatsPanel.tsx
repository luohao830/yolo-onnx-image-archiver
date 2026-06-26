import { useMemo } from "react";

import type { JobDetection, JobStats } from "../../api/types";
import { formatSeconds } from "../../lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { KpiCard } from "./KpiCard";

interface StatsPanelProps {
  summary: JobStats | null;
  detections: JobDetection[];
}

const LABEL_COLORS = [
  "bg-brand",
  "bg-green-600",
  "bg-amber-600",
  "bg-red-600",
  "bg-purple-600",
  "bg-pink-600",
  "bg-cyan-600",
  "bg-slate-600",
];

/** 统计面板：总图数/检测图/无检测图、by_label 分布条、置信度分布、耗时概览。 */
export function StatsPanel({ summary, detections }: StatsPanelProps) {
  const detectedCount = useMemo(
    () => detections.filter((d) => d.detections.length > 0).length,
    [detections],
  );
  const emptyCount = detections.length - detectedCount;

  const byLabel = summary?.by_label ?? {};
  const labelEntries = useMemo(
    () => Object.entries(byLabel).sort((a, b) => b[1] - a[1]),
    [byLabel],
  );
  const labelTotal = labelEntries.reduce((sum, [, c]) => sum + c, 0) || 1;

  const confBuckets = useMemo(() => {
    const buckets = { high: 0, mid: 0, low: 0 };
    for (const img of detections) {
      for (const det of img.detections) {
        if (det.confidence >= 0.9) buckets.high += 1;
        else if (det.confidence >= 0.7) buckets.mid += 1;
        else buckets.low += 1;
      }
    }
    return buckets;
  }, [detections]);
  const confTotal = confBuckets.high + confBuckets.mid + confBuckets.low;

  return (
    <Card>
      <CardHeader>
        <CardTitle>检测统计</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <div className="grid grid-cols-3 gap-2">
          <KpiCard title="总图数" value={summary?.total ?? detections.length} />
          <KpiCard title="检测图" value={detectedCount} />
          <KpiCard title="无检测" value={emptyCount} />
        </div>

        {labelEntries.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wide text-subtle">类别分布</p>
            <div className="flex flex-col gap-1.5">
              {labelEntries.map(([label, count], idx) => (
                <div key={label} className="flex items-center gap-2">
                  <span className="w-24 truncate text-xs text-muted">{label}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className={`h-full rounded-full ${LABEL_COLORS[idx % LABEL_COLORS.length]}`}
                      style={{ width: `${(count / labelTotal) * 100}%` }}
                    />
                  </div>
                  <span className="w-10 text-right text-xs font-bold text-ink">{count}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {confTotal > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wide text-subtle">置信度分布</p>
            <div className="flex h-3 w-full overflow-hidden rounded-full">
              <div className="bg-green-600" style={{ width: `${(confBuckets.high / confTotal) * 100}%` }} />
              <div className="bg-amber-600" style={{ width: `${(confBuckets.mid / confTotal) * 100}%` }} />
              <div className="bg-red-600" style={{ width: `${(confBuckets.low / confTotal) * 100}%` }} />
            </div>
            <div className="flex justify-between text-[10px] text-muted">
              <span>≥0.9: {confBuckets.high}</span>
              <span>≥0.7: {confBuckets.mid}</span>
              <span>{"<"}0.7: {confBuckets.low}</span>
            </div>
          </div>
        ) : null}

        <div className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-wide text-subtle">耗时概览</p>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-subtle">总耗时</dt>
            <dd className="text-ink">{formatSeconds(summary?.elapsed_sec)}</dd>
            <dt className="text-subtle">推理</dt>
            <dd className="text-ink">{formatSeconds(summary?.inference_sec)}</dd>
            <dt className="text-subtle">预处理</dt>
            <dd className="text-ink">{formatSeconds(summary?.preprocess_sec)}</dd>
            <dt className="text-subtle">后处理</dt>
            <dd className="text-ink">{formatSeconds(summary?.postprocess_sec)}</dd>
          </dl>
        </div>
      </CardContent>
    </Card>
  );
}
