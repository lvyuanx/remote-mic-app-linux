/** Linux WebKit IPC. The native host exposes only a fixed command dispatcher. */
declare global {
  interface Window {
    __SAYALL_LINUX__?: boolean;
    __linuxResolve: (id: number, value: unknown, error: string | null) => void;
    webkit?: { messageHandlers: { linux: { postMessage: (message: string) => void } } };
  }
}
let nextId = 0;
const pending = new Map<number, { resolve: (value: any) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> }>();
export function isLinuxRuntime(): boolean { return window.__SAYALL_LINUX__ === true; }
if (typeof window !== "undefined") window.__linuxResolve = (id, value, error) => {
  const request = pending.get(id);
  if (!request) return;
  clearTimeout(request.timer);
  pending.delete(id);
  if (error) {
    if (error.startsWith('Linux:')) window.dispatchEvent(new CustomEvent('sayall:linux-error', { detail: error }));
    request.reject(new Error(error));
  } else request.resolve(value);
};
export function linuxCall<T = any>(command: string, args: object = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('操作超时，请重试')); }, 30000);
    pending.set(id, { resolve, reject, timer });
    window.webkit!.messageHandlers.linux.postMessage(JSON.stringify({ id, command, args }));
  });
}

if (typeof document !== "undefined") document.addEventListener("mousedown", (event) => {
  if (isLinuxRuntime() && event.button === 0 && (event.target as HTMLElement).closest("[data-tauri-drag-region]")) void linuxCall("drag_window");
});

export function linuxSubscribe<T>(event: string, handler: (value:T) => void): () => void {
  const listener = (event:Event) => handler((event as CustomEvent<T>).detail);
  window.addEventListener('sayall:'+event,listener);
  return () => window.removeEventListener('sayall:'+event,listener);
}
