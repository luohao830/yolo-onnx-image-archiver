import { useEffect, useState } from "react";

import { adminLogin } from "../../admin-api/client";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { FadeIn } from "../../components/ui/fade-in";

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
    if (localStorage.getItem(ADMIN_AUTO_LOGIN_DISABLED_KEY) === "1") return;
    let cancelled = false;
    async function tryWhitelistLogin() {
      try {
        const result = await adminLogin("");
        if (cancelled) return;
        localStorage.setItem(ADMIN_TOKEN_KEY, result.token);
        localStorage.removeItem(ADMIN_AUTO_LOGIN_DISABLED_KEY);
        onLogin(result.token);
      } catch {
        // 非白名单 IP 正常失败，保留手动登录入口。
      }
    }
    void tryWhitelistLogin();
    return () => {
      cancelled = true;
    };
  }, [onLogin]);

  async function handleSubmit() {
    if (!secret.trim() || isSubmitting) return;
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
    <main className="grid min-h-screen place-items-center bg-page p-6">
      <FadeIn y={12}>
        <Card className="w-[min(480px,100%)]">
          <CardHeader>
            <p className="text-xs font-bold uppercase tracking-wide text-brand">管理员后台</p>
            <CardTitle>进入管理后台</CardTitle>
            <CardDescription>
              输入管理员密钥，或使用已配置的内网白名单免密进入模型、配置和任务后台。
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <label htmlFor="admin-secret" className="text-sm font-bold text-ink">管理员密钥</label>
            <input
              id="admin-secret"
              type="password"
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
              className="w-full rounded-md border border-line-strong bg-card px-3 py-2.5 text-ink"
            />
            <Button variant="primary" size="lg" disabled={!secret.trim() || isSubmitting} onClick={handleSubmit}>
              {isSubmitting ? "登录中..." : "进入后台"}
            </Button>
            {errorMessage ? (
              <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
                {errorMessage}
              </p>
            ) : null}
          </CardContent>
        </Card>
      </FadeIn>
    </main>
  );
}
