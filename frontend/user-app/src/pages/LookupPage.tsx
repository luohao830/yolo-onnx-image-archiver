import { useState } from "react";

import { getJobStatus, type PublicJobStatus } from "../api/client";

export function LookupPage() {
  const [jobCode, setJobCode] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [result, setResult] = useState<PublicJobStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleLookup() {
    if (!jobCode.trim() || !accessToken.trim() || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setResult(null);

    try {
      const status = await getJobStatus(jobCode.trim(), accessToken.trim());
      setResult(status);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "查询任务失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main>
      <h1>任务凭证查询</h1>
      <p>输入任务编号和访问口令，查看当前任务状态。</p>
      <label htmlFor="lookup-job-code">任务编号</label>
      <input
        id="lookup-job-code"
        type="text"
        value={jobCode}
        onChange={(event) => setJobCode(event.target.value)}
      />
      <label htmlFor="lookup-access-token">访问口令</label>
      <input
        id="lookup-access-token"
        type="text"
        value={accessToken}
        onChange={(event) => setAccessToken(event.target.value)}
      />
      <button
        type="button"
        disabled={!jobCode.trim() || !accessToken.trim() || isSubmitting}
        onClick={handleLookup}
      >
        {isSubmitting ? "查询中..." : "查询任务"}
      </button>
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
      {result ? (
        <section aria-label="任务查询结果">
          <h2>任务状态</h2>
          <p>{result.status}</p>
          <h2>任务模式</h2>
          <p>{result.mode}</p>
          {result.error_message ? (
            <>
              <h2>错误信息</h2>
              <p>{result.error_message}</p>
            </>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
