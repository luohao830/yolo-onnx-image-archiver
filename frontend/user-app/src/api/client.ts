export type JobMode = "person_filter" | "advanced";

export async function createJob(mode: JobMode) {
  const response = await fetch("/api/jobs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ mode })
  });

  return response.json();
}
