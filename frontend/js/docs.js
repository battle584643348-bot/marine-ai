/* 知识库面板：上传 / 列表 / 删除 / 重建 */
window.Docs = (function () {
  function fmtSize(n) {
    if (n >= 1048576) return (n / 1048576).toFixed(1) + " MB";
    if (n >= 1024) return (n / 1024).toFixed(1) + " KB";
    return n + " B";
  }
  async function load() {
    const data = await API.get("/api/documents");
    $("#docsStat").textContent = "(" + data.documents.length + " 份文档 · " + data.total_chunks + " 个片段)";
    const list = $("#docList");
    list.innerHTML = "";
    if (!data.documents.length) {
      list.innerHTML = '<div class="doc-item"><span class="sub">知识库为空。上传 PDF/DOCX/XLSX/TXT/MD 文档后，即可在对话中检索问答。</span></div>';
      return;
    }
    data.documents.forEach((d) => {
      const item = document.createElement("div");
      item.className = "doc-item";
      item.innerHTML =
        '<span class="name">' + escapeHtml(d.name) + "</span>" +
        '<span class="sub">' + d.num_chunks + " 片段 · " + fmtSize(d.size) +
        ' · ' + new Date(d.added_at * 1000).toLocaleString() + "</span>" +
        '<button class="del" title="删除并从索引移除">✕</button>';
      item.querySelector(".del").addEventListener("click", async () => {
        if (!confirm("删除文档 " + d.name + "？")) return;
        await API.del("/api/documents/" + d.doc_id);
        load();
      });
      list.appendChild(item);
    });
  }
  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  async function uploadFiles(files) {
    if (!files.length) return;
    const res = await API.upload("/api/documents/upload", files);
    let msg = "已入库 " + res.added.length + " 份";
    if (res.errors.length) msg += "；失败 " + res.errors.length + " 份（" + res.errors.map((e) => e.name + ": " + e.error).join("；") + "）";
    alert(msg);
    load();
  }
  function bind() {
    const dz = $("#dropzone");
    const input = $("#fileInput");
    dz.addEventListener("click", () => input.click());
    input.addEventListener("change", () => { uploadFiles([...input.files]); input.value = ""; });
    dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
    dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
    dz.addEventListener("drop", (e) => {
      e.preventDefault();
      dz.classList.remove("drag");
      uploadFiles([...e.dataTransfer.files]);
    });
  }
  return { load: load, bind: bind };
})();
