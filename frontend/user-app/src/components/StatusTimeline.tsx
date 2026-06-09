import type { JobStatus } from "../api/client";

const STATUS_STEPS: Array<{ status: JobStatus; label: string }> = [
  { status: "created", label: "任务已创建" },
  { status: "uploaded", label: "文件已接收" },
  { status: "running", label: "正在处理" },
  { status: "completed", label: "处理完成" },
  { status: "failed", label: "处理失败" },
  { status: "canceled", label: "任务已取消" }
];

function getStepState(currentStatus: JobStatus, stepStatus: JobStatus): string {
  if (currentStatus === "failed" || currentStatus === "canceled") {
    if (stepStatus === currentStatus) {
      return "current";
    }

    return STATUS_STEPS.findIndex((step) => step.status === stepStatus) < 3 ? "done" : "pending";
  }

  const currentIndex = STATUS_STEPS.findIndex((step) => step.status === currentStatus);
  const stepIndex = STATUS_STEPS.findIndex((step) => step.status === stepStatus);

  if (stepIndex < currentIndex) {
    return "done";
  }

  if (stepIndex === currentIndex) {
    return "current";
  }

  return "pending";
}

export interface StatusTimelineProps {
  status: JobStatus;
}

export function StatusTimeline({ status }: StatusTimelineProps) {
  return (
    <section aria-label="任务状态时间线">
      <h2>处理进度</h2>
      <ol>
        {STATUS_STEPS.map((step) => {
          const stepState = getStepState(status, step.status);

          return (
            <li key={step.status}>
              <strong>{step.label}</strong>
              <span>{stepState === "current" ? "（当前）" : stepState === "done" ? "（已完成）" : "（待处理）"}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
