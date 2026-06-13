import { useEffect, useState } from "react";

import { adminLogin } from "../../admin-api/client";

const ADMIN_TOKEN_KEY = "admin-token";
const ADMIN_AUTO_LOGIN_DISABLED_KEY = "admin-auto-login-disabled";

interface LoginPageProps {
  onLogin: (token: string) => void;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [secret, setSecret] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function tryWhitelistLogin() {
      try {
        const result = await adminLogin("");
        if (cancelled) {
          return;
        }
        localStorage.setItem(ADMIN_TOKEN_KEY, result.token);
        localStorage.removeItem(ADMIN_AUTO_LOGIN_DISABLED_KEY);
        onLogin(result.token);
      } catch {
        // 非白名单 IP 会正常失败，保留手动登录入口。
      }
    }

    void tryWhitelistLogin();

    return () => {
      cancelled = true;
    };
  }, [onLogin]);

  async function handleSubmit() {
    if (!secret.trim() || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const result = await adminLogin(secret.trim());
      localStorage.setItem(ADMIN_TOKEN_KEY, result.token);
      localStorage.removeItem(ADMIN_AUTO_LOGIN_DISABLED_KEY);
      onLogin(result.token);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "管理员登录失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="admin-login-shell">
      <section className="work-card admin-login-card" aria-label="管理员登录">
        <div className="panel-heading">
          <p className="eyebrow">管理员后台</p>
          <h1>进入管理后台</h1>
          <p>输入管理员密钥，或使用已配置的内网白名单免密进入模型、配置和任务后台。</p>
        </div>
        <label htmlFor="admin-secret">管理员密钥</label>
        <input
          id="admin-secret"
          type="password"
          value={secret}
          onChange={(event) => setSecret(event.target.value)}
        />
        <button className="button button--primary" type="button" disabled={!secret.trim() || isSubmitting} onClick={handleSubmit}>
          {isSubmitting ? "登录中..." : "进入后台"}
        </button>
        {errorMessage ? <p className="alert" role="alert">{errorMessage}</p> : null}
      </section>
    </main>
  );
}
