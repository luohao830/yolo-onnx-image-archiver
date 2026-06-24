import { createContext, useContext, useId, useState, type ReactNode } from "react";

import { cn } from "../../lib/utils";

interface TabsContextValue {
  value: string;
  setValue: (v: string) => void;
  baseId: string;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext(component: string): TabsContextValue {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error(`${component} 必须在 <Tabs> 内使用`);
  return ctx;
}

interface TabsProps {
  value?: string;
  defaultValue: string;
  onValueChange?: (v: string) => void;
  children: ReactNode;
  className?: string;
}

export function Tabs({ value, defaultValue, onValueChange, children, className }: TabsProps) {
  const isControlled = value !== undefined;
  const [internal, setInternal] = useState(defaultValue);
  const baseId = useId();
  const current = isControlled ? (value as string) : internal;

  const setValue = (v: string) => {
    if (!isControlled) setInternal(v);
    onValueChange?.(v);
  };

  return (
    <TabsContext.Provider value={{ value: current, setValue, baseId }}>
      <div className={cn("flex flex-col gap-4", className)}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabsList({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      role="tablist"
      className={cn(
        "inline-flex items-center gap-1 rounded-lg border border-line bg-card p-1",
        className,
      )}
    >
      {children}
    </div>
  );
}

interface TabsTriggerProps {
  value: string;
  children: ReactNode;
  className?: string;
}

export function TabsTrigger({ value, children, className }: TabsTriggerProps) {
  const ctx = useTabsContext("TabsTrigger");
  const active = ctx.value === value;
  return (
    <button
      type="button"
      role="tab"
      id={`${ctx.baseId}-tab-${value}`}
      aria-selected={active}
      aria-controls={`${ctx.baseId}-panel-${value}`}
      data-state={active ? "active" : "inactive"}
      onClick={() => ctx.setValue(value)}
      className={cn(
        "inline-flex min-h-9 items-center rounded-md px-3 text-sm font-bold transition-colors",
        active ? "bg-brand text-white" : "text-muted hover:bg-slate-100 hover:text-ink",
        className,
      )}
    >
      {children}
    </button>
  );
}

interface TabsContentProps {
  value: string;
  children: ReactNode;
  className?: string;
}

export function TabsContent({ value, children, className }: TabsContentProps) {
  const ctx = useTabsContext("TabsContent");
  if (ctx.value !== value) return null;
  return (
    <div
      role="tabpanel"
      id={`${ctx.baseId}-panel-${value}`}
      aria-labelledby={`${ctx.baseId}-tab-${value}`}
      className={cn("focus-visible:outline-none", className)}
    >
      {children}
    </div>
  );
}
