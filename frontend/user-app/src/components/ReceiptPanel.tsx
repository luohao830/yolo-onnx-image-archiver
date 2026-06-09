import type { CreateJobResponse } from "../api/client";


interface ReceiptPanelProps {
  receipt: Pick<CreateJobResponse, "job_code" | "access_token" | "status">;
}

export function ReceiptPanel({ receipt }: ReceiptPanelProps) {
  return (
    <section aria-label="任务回执">
      <h3>任务回执</h3>
      <p>任务编号</p>
      <p>{receipt.job_code}</p>
      <p>访问口令</p>
      <p>{receipt.access_token}</p>
      <p>当前状态</p>
      <p>{receipt.status}</p>
    </section>
  );
}
