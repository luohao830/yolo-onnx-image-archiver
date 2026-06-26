export type JobMode = "person_filter" | "advanced";
export type JobStatus = "created" | "uploaded" | "running" | "completed" | "failed" | "canceled";

export interface JobEvent {
  id: number;
  event_type: string;
  message: string;
  payload_json: Record<string, unknown>;
}

/** 任务统计（后端 JobRecord.summary_json）。 */
export interface JobStats {
  total?: number;
  written?: number;
  by_label?: Record<string, number>;
  elapsed_sec?: number;
  inference_sec?: number;
  preprocess_sec?: number;
  postprocess_sec?: number;
  hardlink_sec?: number;
  draw_sec?: number;
  drawn?: number;
  txt_written?: number;
  hardlinked?: number;
  copied?: number;
  failed?: number;
  used_batch?: number;
  used_imgsz?: number[] | [number, number];
  cuda_enabled?: boolean;
  providers?: string[];
}

export interface JobDetection {
  filename: string;
  rel_path?: string;
  width: number;
  height: number;
  detections: Array<{
    label: string;
    confidence: number;
    bbox: [number, number, number, number];
    cls_id: number;
  }>;
  has_drawn: boolean;
  drawn_path?: string | null;
}

export interface JobDetectionsResponse {
  images: JobDetection[];
}
