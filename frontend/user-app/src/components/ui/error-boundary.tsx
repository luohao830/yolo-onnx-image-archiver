import { AlertTriangle, RefreshCw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "./button";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}
interface State {
  hasError: boolean;
  retryKey: number;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, retryKey: 0 };

  static getDerivedStateFromError(_error: Error): Partial<State> {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("[ErrorBoundary] 渲染异常:", error, info);
  }

  private handleReset = () => {
    this.setState((prev) => ({ hasError: false, retryKey: prev.retryKey + 1 }));
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div
          role="alert"
          className="flex flex-col items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-5 text-red-800"
        >
          <div className="flex items-center gap-2 font-bold">
            <AlertTriangle className="h-5 w-5" aria-hidden />
            <span>页面渲染出现问题</span>
          </div>
          <p className="text-sm leading-relaxed text-red-700">
            页面加载过程中发生了意外错误，请重试。如问题持续出现，请联系管理员。
          </p>
          <Button variant="secondary" size="sm" onClick={this.handleReset}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            重试
          </Button>
        </div>
      );
    }
    return <ErrorBoundaryRetryRoot key={this.state.retryKey}>{this.props.children}</ErrorBoundaryRetryRoot>;
  }
}

/** 辅助组件：在 key 变化时强制重新挂载 children（重置 React 内部状态）。 */
function ErrorBoundaryRetryRoot({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
