---
name: YOLO 多用户推理平台
description: 用户提交图片/压缩包任务，查看进度、日志并下载结果的冷静工程化界面。
colors:
  primary: "#2563eb"
  primary-deep: "#1d4ed8"
  primary-soft: "#dbeafe"
  success: "#16a34a"
  success-deep: "#15803d"
  danger: "#991b1b"
  danger-soft: "#fee2e2"
  warning: "#0369a1"
  warning-soft: "#e0f2fe"
  ink: "#0f172a"
  body: "#475569"
  muted: "#64748b"
  surface: "#ffffff"
  background: "#f8fafc"
  border: "#e2e8f0"
  border-strong: "#cbd5e1"
  log-bg: "#020617"
  log-text: "#e2e8f0"
  log-accent: "#38bdf8"
typography:
  display:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "clamp(28px, 5vw, 36px)"
    fontWeight: 700
    lineHeight: 1.12
    letterSpacing: "normal"
  headline:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "normal"
  title:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "normal"
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "normal"
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  sm: "7px"
  md: "8px"
  lg: "10px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "18px"
  2xl: "20px"
  3xl: "24px"
  4xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "0 14px"
    size: "min-height 40px"
  button-primary-hover:
    backgroundColor: "{colors.primary-deep}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "0 14px"
    size: "min-height 40px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0 14px"
    size: "min-height 40px"
  button-secondary-hover:
    backgroundColor: "{colors.background}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0 14px"
    size: "min-height 40px"
  button-success:
    backgroundColor: "{colors.success}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "0 14px"
    size: "min-height 40px"
  button-success-hover:
    backgroundColor: "{colors.success-deep}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "0 14px"
    size: "min-height 40px"
  status-badge-running:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary-deep}"
    rounded: "{rounded.pill}"
    padding: "5px 9px"
  status-badge-completed:
    backgroundColor: "#dcfce7"
    textColor: "#166534"
    rounded: "{rounded.pill}"
    padding: "5px 9px"
  status-badge-failed:
    backgroundColor: "{colors.danger-soft}"
    textColor: "{colors.danger}"
    rounded: "{rounded.pill}"
    padding: "5px 9px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "20px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
  log-panel:
    backgroundColor: "{colors.log-bg}"
    textColor: "{colors.log-text}"
    rounded: "{rounded.lg}"
    padding: "14px"
---

# Design System: YOLO 多用户推理平台

## 1. Overview

**Creative North Star: "The Reliable Bench"**

这个界面是一架状态良好的实验台：上传、处理、日志、下载各就各位。没有噪音，每个按钮和进度条都在告诉你系统正在可靠运转。设计的核心不是说服用户"这个产品很棒"，而是让用户在把图片交给它处理的那几秒钟内，感到事情已经安排妥当。

界面的气质从 PRODUCT.md 的"冷静、工程化、可信"延伸而来。中性浅色工作区承载主要任务，深色只出现在日志面板这种需要高密度信息的地方——日志本身成为"后台正在认真工作"的可信信号。装饰被压到最低，状态反馈被提到最高。

**Key Characteristics:**

- **任务路径优先**：每个页面只回答"现在该做什么"和"任务进行到哪了"。
- **状态即反馈**：进度、日志、错误、成功都必须可见、可理解。
- **无账户≠低信任**：无需登录的体验更要在文案、错误处理和视觉稳定感上建立信任。
- **深色是工具**：深色面板仅用于日志/终端感内容，浅色工作区保持开放高效。
- **克制胜于丰富**：少一个装饰元素，多一份可信度。

## 2. Colors

调色板以中性冷灰工作区为底，科技蓝为主功能色，深色面板只用于日志。状态色清晰但不过亮，避免传统运维后台那种大红大绿的刺眼感。

### Primary

- **Signal Blue** (`#2563eb` / oklch(55% 0.22 255)): 主按钮、进度条、当前步骤指示、焦点环。用于引导用户完成核心动作，但绝不滥用。
- **Deep Signal** (`#1d4ed8` / oklch(49% 0.21 255)): Primary 按钮悬停状态，强调按下后的"系统已响应"。
- **Soft Signal** (`#dbeafe` / oklch(93% 0.03 255)): 运行中状态徽章背景、悬停背景 tint。让状态信息柔和地突出。

### Neutral

- **Ink** (`#0f172a` / oklch(21% 0.03 250)): 主标题、关键文字、管理员导航背景。界面最重的颜色。
- **Body** (`#475569` / oklch(46% 0.04 245)): 正文、描述、辅助说明。对比度足够，但比 Ink 轻一级。
- **Muted** (`#64748b` / oklch(56% 0.04 245)): 表头、次要元数据、空状态提示。
- **Surface** (`#ffffff`): 卡片、面板、输入框背景。与 Background 形成清晰分层。
- **Background** (`#f8fafc` / oklch(97% 0.01 240)): 页面底色。冷灰，不偏暖，避免 AI 默认暖米色。
- **Border** (`#e2e8f0`): 卡片、面板、列表分隔线。低对比度边界，保持整洁。
- **Border Strong** (`#cbd5e1`): 输入框边框、次要按钮边框。悬停时过渡到更深的 `#94a3b8`。

### Functional

- **Success** (`#16a34a` / oklch(58% 0.21 145)): 完成状态、下载结果按钮。只在终点出现。
- **Success Deep** (`#15803d`): Success 按钮悬停。
- **Danger** (`#991b1b` / oklch(43% 0.18 25)): 失败状态、错误提示文字。
- **Danger Soft** (`#fee2e2` / oklch(95% 0.05 25)): 错误提示背景、失败状态徽章背景。
- **Warning** (`#0369a1` / oklch(50% 0.14 235)): 已创建/已上传等中间状态。
- **Warning Soft** (`#e0f2fe` / oklch(95% 0.03 235)): 中间状态徽章背景。

### Terminal / Log

- **Log Background** (`#020617`): 日志面板唯一背景。深色让时间戳和事件类型形成终端般的可读层次。
- **Log Text** (`#e2e8f0`): 日志正文，浅灰保证长时间阅读不累。
- **Log Accent** (`#38bdf8`): 事件类型标签、关键字段。冷青色在深色上清晰但不跳动。

### Named Rules

**The One Accent Rule.** 主色 `#2563eb` 只出现在主按钮、当前进度、运行状态和焦点环上。任何一页上，Signal Blue 的占比不应超过 10%。它的稀有性就是它的强调力。

**The Dark-Is-For-Logs Rule.** 深色背景只用于日志面板。不要为了让界面"看起来更专业"而任意使用深色卡片或侧边栏。

## 3. Typography

**Display / Body Font:** Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif  
**Label / Mono Font:** ui-monospace, SFMono-Regular, Menlo, Consolas, monospace（仅用于日志时间戳/事件类型）

**Character:** 单一无衬线家族，全界面统一。Inter 的中性、高可读性和工程感与"冷静、可信"的定位一致。没有装饰性字体，没有对比强烈的字体配对，避免任何"设计感"压倒任务感。

### Hierarchy

- **Display** (700, `clamp(28px, 5vw, 36px)`, line-height 1.12): 页面主标题，出现在 `page-hero`。最多两行，配合 eyebrow 使用。
- **Headline** (700, `30px`, line-height 1.15): 管理员页面标题 (`page-heading h1`)，比 Display 更收敛。
- **Title** (700, `20px`, line-height 1.2): 卡片标题 (`mode-card h2`, `panel-heading h2`, `status-panel h2`)。
- **Body** (400, `16px`, line-height 1.6): 页面描述、卡片说明、一般正文。行宽控制在 65–75ch。
- **Label** (800, `12px`, line-height 1.2, uppercase): eyebrow、状态徽章、表头。全大写，字重 800，小字号。
- **Mono** (400, `12px`, line-height 1.5): 仅用于日志中的事件类型和时间戳。

### Named Rules

**The No Shouting Rule.** 字号上限为 36px (Display) 和 30px (Headline)。再大的标题会制造营销感，而不是工具感。

**The One Family Rule.** 全界面只使用 Inter 及其系统回退。不要为了"层次"引入第二套无衬线或装饰字体。

## 4. Elevation

系统使用柔和的阴影来区分卡片/面板与背景，但阴影始终保持低调，不制造浮层感或材质感。深度主要通过白色表面叠在冷灰背景上来表达，而不是强烈的阴影。

### Shadow Vocabulary

- **Card Shadow** (`0 14px 34px rgba(15, 23, 42, 0.06)`): 卡片、面板、状态区域的标准阴影。足够让表面从背景中升起，但绝不厚重。
- **Focus Ring** (`outline: 3px solid rgba(37, 99, 235, 0.28); outline-offset: 2px`): 所有可聚焦元素的键盘焦点环。半透明蓝色，不替代边框。
- **Current Step Glow** (`box-shadow: 0 0 0 5px rgba(37, 99, 235, 0.16)`): 步骤列表中当前步骤指示点的外发光。仅用于状态理解。

### Named Rules

**The Flat-By-Default Rule.** 表面在静止时是平的。阴影只出现在需要与背景分层的卡片/面板上。不要使用悬停时大幅抬升的阴影来制造"可点击"的暗示；可点击性由颜色、形状和光标承担。

## 5. Components

组件系统的整体感觉是"克制、明确、有响应"。按钮、卡片、输入框都使用相同的圆角语言（7px 小圆角、10px 卡片圆角），过渡时间为 180ms，easing 使用 ease。

### Buttons

- **Shape:** 小圆角 (`7px`)，min-height 40px（管理员按钮 34px，次要入口），内边距 `0 14px`，字重 800。
- **Primary:** 背景 `#2563eb`，文字白色。悬停 `#1d4ed8`。用于"开始处理"、"提交"等主行动作。
- **Secondary:** 白色背景，边框 `1px solid #cbd5e1`，文字 `#0f172a`。悬停背景 `#f8fafc`，边框 `#94a3b8`。用于"进入"、返回、非主要操作。
- **Success:** 背景 `#16a34a`，文字白色。悬停 `#15803d`。只在结果可下载时出现，作为结果下载按钮。
- **Focus / Disabled:** 焦点环 3px 半透明蓝；disabled 透明度 0.55，光标 not-allowed。
- **Transition:** `background-color 180ms ease, border-color 180ms ease, color 180ms ease, opacity 180ms ease`。

### Cards / Containers

- **Corner Style:** 10px 圆角 (`rounded-lg`)。
- **Background:** 白色 (`#ffffff`)。
- **Shadow:** `0 14px 34px rgba(15, 23, 42, 0.06)`。
- **Border:** 1px solid `#e2e8f0`。
- **Internal Padding:** 20px（`mode-card`, `work-card`, `status-panel`, `log-panel`, `table-card`）。
- **Usage:** 模式入口卡片、任务工作区、状态面板、管理员表格容器。

### Inputs / Fields

- **Style:** 白色背景，1px solid `#cbd5e1` 边框，7px 圆角，内边距 `10px 12px`。宽度 100%。
- **Focus:** 3px 半透明蓝色焦点环 (`outline: 3px solid rgba(37, 99, 235, 0.28)`)。
- **File Upload:** 虚线边框 (`1px dashed #94a3b8`)，背景 `#f8fafc`，10px 圆角。与一般输入框区分，暗示"拖放/选择文件"。
- **Labels:** 字重 800，`#0f172a`。

### Status Badges

- **Shape:** 药丸形 (`999px`)，内边距 `5px 9px`，字号 12px，字重 800。
- **Running:** 背景 `#dbeafe`，文字 `#1d4ed8`。
- **Completed:** 背景 `#dcfce7`，文字 `#166534`。
- **Failed:** 背景 `#fee2e2`，文字 `#991b1b`。
- **Created / Uploaded:** 背景 `#e0f2fe`，文字 `#0369a1`。
- **Canceled:** 背景 `#f1f5f9`，文字 `#475569`。

### Progress Indicators

- **Progress Track:** 高度 12px，药丸形，背景 `#e2e8f0`。
- **Progress Fill:** 背景 `#2563eb`，宽度动画 220ms ease。
- **Progress Summary:** 大号百分比 (`42px`, `#0f172a`) + 说明文字 (`14px`, `#64748b`)。
- **Stage List:** 圆点 + 文字，当前步骤圆点 `#2563eb` 带柔和外发光，文字加粗。

### Navigation

- **Admin Nav:** 深色背景 (`#0f172a`)，链接文字 `#cbd5e1`，字重 800。悬停背景 `rgba(59, 130, 246, 0.22)`，文字变白。移动端水平滚动，padding 12px。
- **User Nav:** 当前为无顶部导航的页面流，依赖卡片和按钮引导。

### Log Panel

- **Background:** `#020617`，14px 圆角，14px 内边距。
- **List:** 最大高度 260px，可滚动。条目下边框 `1px solid rgba(148, 163, 184, 0.18)`。
- **Timestamp / Event Type:** `#38bdf8`，等宽字体，12px。
- **Message:** `#e2e8f0`，无衬线，1.5 行高。

## 6. Do's and Don'ts

### Do:

- **Do** 使用 `#f8fafc` 作为页面背景，`#ffffff` 作为卡片/面板背景，保持冷灰工作区。
- **Do** 把 `#2563eb` 留给主按钮、运行状态、当前进度和焦点环，让主色保持稀缺。
- **Do** 在日志面板使用 `#020617` 深色背景 + `#e2e8f0` 浅色文字 + `#38bdf8` 事件类型。
- **Do** 给所有交互元素提供清晰的焦点环（`outline: 3px solid rgba(37, 99, 235, 0.28)`）。
- **Do** 在状态指示中同时使用颜色 + 文字/百分比，不单独依赖颜色。
- **Do** 使用 Inter 单一家族，避免引入第二套无衬线或装饰字体。
- **Do** 保持卡片阴影低调：`0 14px 34px rgba(15, 23, 42, 0.06)`。
- **Do** 在 `prefers-reduced-motion: reduce` 下把过渡降到 0.01ms，支持即时状态变化。
- **Do** 保证正文 `#475569` 在 `#f8fafc` 上对比度 ≥4.5:1，大号文字/按钮 ≥3:1。

### Don't:

- **Don't** 使用暖米色/奶油色/沙色作为页面背景。"可信"不等于"暖"。
- **Don't** 把深色背景用作装饰卡片、侧边栏或大面积氛围，深色只给日志面板。
- **Don't** 使用渐变文字、大数字指标、营销话术或抽象插图——这是 SaaS 营销落地页的 cliché，会拖慢用户的任务路径。
- **Don't** 使用大红大绿的状态色块和密集表格——这是传统运维后台的外观，只有内行才能看懂。
- **Don't** 让界面冷淡到没有反馈、错误不解释。用户需要每一步都被确认。
- **Don't** 使用 999 / 9999 等任意 z-index。建立语义化层级（dropdown → sticky → modal-backdrop → modal → toast → tooltip）。
- **Don't** 在卡片上堆砌卡片。嵌套卡片是错误的信息架构。
- **Don't** 在虚线边框上传区域里使用奶油色背景暗示"拖放区"。上传区使用 `#f8fafc`。
- **Don't** 在首页和任务页之间加入营销式 eyebrow 小字（"FEATURES"、"HOW IT WORKS"）。 eyebrow 只用于当前上下文标签（如"人员筛选模式"、"处理状态"）。
- **Don't** 为每个 section 添加 `01 / 02 / 03` 编号标记。编号只用于真正的序列（如处理阶段）。
