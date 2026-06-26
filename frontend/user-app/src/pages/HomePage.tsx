import { Link } from "react-router-dom";

import { FadeIn } from "../components/ui/fade-in";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { PersonFilterPage } from "./PersonFilterPage";

/**
 * 首页：同时承担人员筛选上传工作台（保持与现有测试契约一致），
 * 并提供模式切换入口与高级模式/管理员入口。
 */
export function HomePage() {
  return (
    <div className="min-h-screen bg-page">
      <main className="mx-auto grid w-[min(1120px,calc(100%-32px))] gap-6 py-8">
        <FadeIn>
          <section className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <p className="text-xs font-bold uppercase tracking-wide text-brand">内网图片处理工作台</p>
              <h1 className="max-w-2xl text-4xl font-bold leading-tight text-ink">
                上传图片后直接查看处理进度
              </h1>
              <p className="max-w-2xl text-sm leading-relaxed text-muted">
                选择图片或压缩包，提交后系统会按 batch 推理并实时反馈进度、关键日志和结果下载入口。
              </p>
            </div>
            <Link
              to="/admin/configs"
              className="inline-flex min-h-10 self-start items-center justify-center rounded-md border border-line-strong bg-card px-3.5 font-bold text-ink transition-colors hover:border-slate-400 hover:bg-page"
            >
              管理员配置
            </Link>
          </section>
        </FadeIn>

        <FadeIn delay={0.05}>
          <Card>
            <CardHeader>
              <CardTitle>模式选择</CardTitle>
              <CardDescription>选择适合的推理模式，或直接在下方提交人员筛选任务。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <Link
                to="/person-filter"
                className="group flex flex-col gap-2 rounded-lg border border-line bg-card p-4 transition-colors hover:border-brand"
              >
                <span className="text-sm font-bold text-ink group-hover:text-brand">人员筛选模式</span>
                <span className="text-xs leading-relaxed text-muted">上传图片或 zip，使用默认人员检测模型筛选含人图片。</span>
              </Link>
              <Link
                to="/advanced"
                className="group flex flex-col gap-2 rounded-lg border border-line bg-card p-4 transition-colors hover:border-brand"
              >
                <span className="text-sm font-bold text-ink group-hover:text-brand">高级模式</span>
                <span className="text-xs leading-relaxed text-muted">自定义模型与 conf/iou/batch 等参数，支持画框与标签输出。</span>
              </Link>
            </CardContent>
          </Card>
        </FadeIn>

        <FadeIn delay={0.1}>
          <PersonFilterPage embedded />
        </FadeIn>
      </main>
    </div>
  );
}
