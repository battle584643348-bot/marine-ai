/* API 封装 */
window.$ = function (sel) { return document.querySelector(sel); };

window.API = (function () {
  async function get(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function post(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function del(url) {
    const r = await fetch(url, { method: "DELETE" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function upload(url, files) {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    const r = await fetch(url, { method: "POST", body: fd });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  /* SSE 对话流：onEvent(ev)，返回最终事件 */
  async function sseChat(message, sessionId, branch, onEvent) {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message, session_id: sessionId, branch: branch || "overall" }),
    });
    if (!resp.ok || !resp.body) throw new Error("HTTP " + resp.status);
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let last = null;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const line = chunk.trim();
        if (!line.startsWith("data:")) continue;
        let ev;
        try { ev = JSON.parse(line.slice(5).trim()); } catch (e) { continue; }
        last = ev;
        onEvent(ev);
        if (ev.type === "done" || ev.type === "error") return ev;
      }
    }
    return last;
  }
  return { get, post, del, upload, sseChat };
})();
