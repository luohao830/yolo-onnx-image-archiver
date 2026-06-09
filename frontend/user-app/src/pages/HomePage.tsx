import { ModeCard } from "../components/ModeCard";


export function HomePage() {
  return (
    <main className="app-main">
      <section className="page-hero">
        <p className="eyebrow">图片任务平台</p>
        <h1>提交任务后直接查看进度与日志</h1>
        <p>选择处理模式，提交文件后查看关键日志和进度。任务完成后下载结果压缩包。</p>
      </section>
      <section className="mode-grid" aria-label="任务模式">
        <ModeCard
          title="人员筛选模式"
          description="上传图片或压缩包，快速筛出检测到人的结果。"
          to="/person-filter"
        />
        <ModeCard
          title="高级模式"
          description="使用管理员发布的模型和高级参数进行批量处理。"
          to="/advanced"
        />
      </section>
    </main>
  );
}
