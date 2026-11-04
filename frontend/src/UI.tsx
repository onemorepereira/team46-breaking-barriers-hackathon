import { useEffect, useState } from "react";
import { markdownLibs, renderMarkdown } from "./markdown";
export function Text({ value }: { value: unknown }) {
  const text = typeof value === "string" ? value : "";
  const [html, setHtml] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    markdownLibs()
      .then((libs) => live && setHtml(renderMarkdown(libs, text)))
      .catch(() => live && setHtml(null)); // plain text below if the renderer can't load
    return () => {
      live = false;
    };
  }, [text]);
  return html === null ? (
    <div className="markdown markdown-plain">{text}</div>
  ) : (
    <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />
  );
}
export function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
}) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {sub && <small>{sub}</small>}
    </div>
  );
}
