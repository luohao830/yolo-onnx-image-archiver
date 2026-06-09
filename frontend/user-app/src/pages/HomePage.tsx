import { ModeCard } from "../components/ModeCard";


export function HomePage() {
  return (
    <main>
      <h1>图片任务平台</h1>
      <p>选择合适的处理模式后提交任务，系统会返回任务编号和访问口令。</p>
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
    </main>
  );
}
