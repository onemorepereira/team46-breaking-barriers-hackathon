// The agent's answer is Markdown. Render it the same way the classic console does: the vendored marked
// + DOMPurify (harness/web/static/vendor), so both UIs show the same answer and one renderer is patched.
import { endpoint } from "./api";

type Libs = {
  marked: { parse: (s: string, o?: object) => string };
  DOMPurify: { sanitize: (s: string) => string };
};
let loading: Promise<Libs> | null = null;

function script(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = endpoint(src);
    el.onload = () => resolve();
    el.onerror = () => reject(new Error(`${src} could not load`));
    document.head.append(el);
  });
}

export function markdownLibs(): Promise<Libs> {
  const w = window as any;
  if (w.marked && w.DOMPurify)
    return Promise.resolve({ marked: w.marked, DOMPurify: w.DOMPurify });
  if (!loading)
    loading = Promise.all([
      script("/static/vendor/marked/marked.umd.js"),
      script("/static/vendor/dompurify/purify.min.js"),
    ])
      .then(() => ({ marked: w.marked, DOMPurify: w.DOMPurify }))
      .catch((e) => {
        loading = null;
        throw e;
      });
  return loading;
}

export function renderMarkdown(libs: Libs, text: string): string {
  return libs.DOMPurify.sanitize(
    libs.marked.parse(text, { gfm: true, breaks: false }),
  );
}
