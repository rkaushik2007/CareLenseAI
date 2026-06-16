import type { CSSProperties } from "react";

const THEME_KEY = "mdp_theme";

export type Theme = "light" | "dark";

export function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "light";
  try {
    const t = localStorage.getItem(THEME_KEY);
    return t === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function setStoredTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* ignore */
  }
}

export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  if (theme === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

export function mapStrokeColors(theme: Theme): { stroke: string; focus: string } {
  return theme === "dark"
    ? { stroke: "#1d222e", focus: "#eef1f6" }
    : { stroke: "#ffffff", focus: "#1b1d26" };
}

export function segBtnStyle(active: boolean): CSSProperties {
  return {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: 32,
    height: 26,
    border: "none",
    borderRadius: 7,
    cursor: "pointer",
    background: active ? "var(--panel)" : "transparent",
    color: active ? "var(--accent)" : "var(--faint)",
    boxShadow: active ? "0 1px 2px rgba(0,0,0,.14)" : "none",
  };
}

export function grainBtnStyle(active: boolean): CSSProperties {
  return {
    flex: 1,
    padding: "7px 0",
    border: "none",
    borderRadius: 7,
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 12,
    fontWeight: 600,
    background: active ? "var(--panel)" : "transparent",
    color: active ? "var(--ink)" : "var(--faint)",
    boxShadow: active ? "0 1px 2px rgba(0,0,0,.08)" : "none",
  };
}

export function tabBtnStyle(active: boolean): CSSProperties {
  return {
    padding: "6px 16px",
    border: "none",
    borderRadius: 7,
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 12.5,
    fontWeight: 600,
    background: active ? "var(--solid)" : "transparent",
    color: active ? "var(--panel)" : "var(--muted)",
  };
}

export function sortBtnStyle(active: boolean): CSSProperties {
  return {
    padding: "5px 11px",
    borderRadius: 8,
    border: `1px solid ${active ? "var(--accent-border)" : "var(--border-3)"}`,
    background: active ? "var(--accent-soft)" : "var(--panel)",
    color: active ? "var(--accent)" : "var(--faint)",
    fontFamily: "inherit",
    fontSize: 11.5,
    fontWeight: 600,
    cursor: "pointer",
  };
}

export function capBtnStyle(active: boolean): CSSProperties {
  return {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    width: "100%",
    padding: "9px 11px",
    borderRadius: 9,
    cursor: "pointer",
    textAlign: "left",
    fontFamily: "inherit",
    border: `1px solid ${active ? "var(--accent-border)" : "transparent"}`,
    background: active ? "var(--accent-soft)" : "transparent",
    color: active ? "var(--accent-ink)" : "var(--ink-2)",
  };
}
