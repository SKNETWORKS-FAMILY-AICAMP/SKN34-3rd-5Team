"use client";

import { useEffect, useEffectEvent, useRef, useState } from "react";
import { loadCKEditor, type EditorInstance } from "@/lib/ckeditor";
import { plainTextToHtml, routeContentToText, type RouteContentFormat } from "@/lib/route-content";

type EditorProps = {
  id: string;
  value: string;
  format?: RouteContentFormat;
  disabled?: boolean;
  onChange: (value: string, format?: RouteContentFormat) => void;
};

// A license is a project decision. Do not silently opt this project into GPL.
const licenseKey = process.env.NEXT_PUBLIC_CKEDITOR_LICENSE_KEY?.trim();

export default function Editor({ id, value, format, disabled, onChange }: EditorProps) {
  const host = useRef<HTMLDivElement>(null);
  const editor = useRef<EditorInstance | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "fallback">(licenseKey ? "loading" : "fallback");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const emitChange = useEffectEvent((html: string) => onChange(html, "html"));
  const currentData = useEffectEvent(() => format === "html" ? value : plainTextToHtml(value));
  const text = routeContentToText(value, format);

  useEffect(() => {
    if (!licenseKey || !host.current) return;
    let canceled = false;
    let instance: EditorInstance | undefined;
    const container = document.createElement("div");
    host.current.appendChild(container);
    void loadCKEditor().then(async (bundle) => {
      if (canceled) return;
      const result = await bundle.ClassicEditor.create({
        attachTo: container, licenseKey, initialData: currentData(), language: "ko",
        plugins: ["Essentials", "Paragraph", "Heading", "Bold", "Italic", "Underline", "Link", "List", "BlockQuote", "Table", "TableToolbar"].map((plugin) => bundle[plugin]),
        toolbar: { items: ["undo", "redo", "|", "heading", "|", "bold", "italic", "underline", "|", "bulletedList", "numberedList", "|", "link", "blockQuote", "insertTable"], shouldNotGroupWhenFull: false },
        table: { contentToolbar: ["tableColumn", "tableRow", "mergeTableCells"] },
        link: { defaultProtocol: "https://", addTargetToExternalLinks: true },
        placeholder: "경기 전후의 계획, 준비물과 나만의 응원 팁을 자유롭게 적어보세요.",
      });
      if (canceled) { await result.destroy(); return; }
      instance = result;
      editor.current = result;
      const editable = result.ui.getEditableElement();
      if (editable) { editable.id = id; editable.setAttribute("aria-label", "루트 본문"); editable.setAttribute("aria-describedby", `${id}-count`); }
      result.model.document.on("change:data", () => emitChange(result.getData()));
      setError(""); setStatus("ready");
    }).catch(() => {
      if (!canceled) { setError("서식 에디터를 불러오지 못했어요. 기본 입력으로 계속 작성할 수 있어요."); setStatus("fallback"); }
    });
    return () => { canceled = true; editor.current = null; void instance?.destroy().catch(() => {}); container.remove(); };
  }, [id, attempt]);

  useEffect(() => {
    const instance = editor.current;
    if (!instance) return;
    const data = format === "html" ? value : plainTextToHtml(value);
    if (instance.getData() !== data) instance.setData(data);
  }, [value, format]);

  useEffect(() => {
    if (disabled) editor.current?.enableReadOnlyMode("saving");
    else editor.current?.disableReadOnlyMode("saving");
  }, [disabled, status]);

  return (
    <div className="writer-editor">
      <div className="writer-editor-heading"><span>나의 직관 이야기</span><span>{status === "ready" ? "글자 서식 · 목록 · 링크 · 표" : "자유롭게 작성해 주세요"}</span></div>
      {status === "loading" && <div className="writer-editor-loading" role="status"><span className="writer-spinner" aria-hidden="true" />서식 에디터를 준비하고 있어요.</div>}
      <div ref={host} hidden={status !== "ready"} />
      {status === "fallback" && <>
        {error && <div className="writer-editor-notice" role="status">{error}<button type="button" onClick={() => { setStatus("loading"); setAttempt((count) => count + 1); }}>에디터 다시 불러오기</button></div>}
        <textarea id={id} aria-label="루트 본문" value={text} onChange={(event) => onChange(event.target.value)} placeholder={"경기 전에는 어디에 들를까요?\n함께 가는 사람에게 알려주고 싶은 내용을 적어보세요.\n\n나만의 준비물, 맛집, 응원 팁도 좋아요."} rows={12} maxLength={12000} disabled={disabled} aria-describedby={`${id}-count`} />
      </>}
      <div id={`${id}-count`} className={`writer-editor-count${text.length > 12000 ? " is-over-limit" : ""}`}>{text.length.toLocaleString()} / 12,000자{status === "fallback" && !error && <span> · 기본 글쓰기</span>}</div>
    </div>
  );
}
