import { AlertTriangle, RefreshCw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "./button";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}
interface State {
  hasError: boolean;
  message?: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // 优先日志而非 print；这里输出到 console 便于前端排查。
    console.error("[ErrorBoundary] 渲染异常:", error, info);
  }

  private handleReset = () => {
    this.setState({ hasError: false, message: undefined });
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
          {this.state.message ? (
            <p className="text-sm leading-relaxed text-red-700">{this.state.message}</p>
          ) : null}
          <Button variant="secondary" size="sm" onClick={this.handleReset}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            重试
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
