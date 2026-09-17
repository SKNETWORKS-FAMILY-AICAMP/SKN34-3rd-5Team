export type EditorInstance = {
  getData: () => string;
  setData: (value: string) => void;
  destroy: () => Promise<void>;
  model: { document: { on: (event: string, callback: () => void) => void } };
  ui: { getEditableElement: () => HTMLElement | undefined };
  enableReadOnlyMode: (id: string) => void;
  disableReadOnlyMode: (id: string) => void;
};
type CKEditorBundle = Record<string, unknown> & { ClassicEditor: { create: (options: Record<string, unknown>) => Promise<EditorInstance> } };
declare global { interface Window { CKEDITOR?: CKEditorBundle } }

const VENDOR = "/vendor/ckeditor5-48.5.0";
let bundlePromise: Promise<CKEditorBundle> | undefined;

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    const timer = setTimeout(() => { script.remove(); reject(new Error("에디터를 불러오는 데 시간이 걸리고 있어요.")); }, 15000);
    script.src = src;
    script.async = true;
    script.onload = () => { clearTimeout(timer); resolve(); };
    script.onerror = () => { clearTimeout(timer); script.remove(); reject(new Error("에디터 파일을 불러오지 못했어요.")); };
    document.head.appendChild(script);
  });
}

export function loadCKEditor(): Promise<CKEditorBundle> {
  if (!bundlePromise) {
    bundlePromise = (async () => {
      if (!document.querySelector("link[data-kbo-editor]")) {
        const stylesheet = document.createElement("link");
        stylesheet.rel = "stylesheet";
        stylesheet.href = `${VENDOR}/ckeditor5.css`;
        stylesheet.dataset.kboEditor = "true";
        document.head.appendChild(stylesheet);
      }
      if (!window.CKEDITOR) await loadScript(`${VENDOR}/ckeditor5.umd.js`);
      await loadScript(`${VENDOR}/ko.umd.js`);
      if (!window.CKEDITOR?.ClassicEditor) throw new Error("에디터를 초기화하지 못했어요.");
      return window.CKEDITOR;
    })().catch((error) => { bundlePromise = undefined; throw error; });
  }
  return bundlePromise;
}
