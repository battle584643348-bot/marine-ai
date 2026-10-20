/* 设置面板：配置读取/保存/健康检查 */
window.Settings = (function () {
  async function load() {
    const cfg = await API.get("/api/config");
    const llm = cfg.llm || {};
    $("#sProvider").value = llm.provider || "auto";
    const oll = llm.ollama || {};
    $("#sOllamaUrl").value = oll.base_url || "";
    $("#sOllamaModel").value = oll.model || "";
    $("#sOllamaEmbed").value = oll.embedding_model || "";
    $("#sEmbedEnabled").checked = !!oll.embedding_enabled;
    const oa = llm.openai_compatible || {};
    $("#sOpenaiUrl").value = oa.base_url || "";
    $("#sOpenaiKey").value = oa.api_key || "";
    $("#sOpenaiModel").value = oa.model || "";
    showHealth();
  }
  function collect() {
    return {
      llm: {
        provider: $("#sProvider").value,
        ollama: {
          base_url: $("#sOllamaUrl").value.trim(),
          model: $("#sOllamaModel").value.trim(),
          embedding_model: $("#sOllamaEmbed").value.trim(),
          embedding_enabled: $("#sEmbedEnabled").checked,
        },
        openai_compatible: {
          base_url: $("#sOpenaiUrl").value.trim(),
          api_key: $("#sOpenaiKey").value.trim(),
          model: $("#sOpenaiModel").value.trim(),
        },
      },
    };
  }
  function renderHealth(h) {
    const box = $("#healthBox");
    const lines = [];
    lines.push('<span class="' + (h.llm.ok ? "ok" : "err") + '">模型：' + escapeHtml(h.llm.detail || "") + "</span>");
    lines.push("<span>知识库：" + h.rag.documents + " 份文档 / " + h.rag.chunks + " 个片段" +
      (h.rag.embedding ? "（语义检索已启用）" : "（关键词检索）") + "</span>");
    lines.push("<span>技能：" + h.skills.count + " 个，已启用 " + h.skills.enabled.length + " 个：" + escapeHtml(h.skills.enabled.join("、")) + "</span>");
    box.innerHTML = lines.map((l) => "<div>" + l + "</div>").join("");
  }
  async function showHealth() {
    try {
      renderHealth(await API.get("/api/health"));
    } catch (e) {
      $("#healthBox").innerHTML = '<span class="err">无法连接后端</span>';
    }
  }
  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function bind() {
    $("#btnSaveCfg").addEventListener("click", async () => {
      const btn = $("#btnSaveCfg");
      btn.disabled = true; btn.textContent = "应用中…";
      try {
        await API.post("/api/config", { patch: collect() });
        await showHealth();
        window.App.refreshStatus();
        alert("配置已保存并生效。");
      } catch (e) {
        alert("保存失败：" + e.message);
      }
      btn.disabled = false; btn.textContent = "保存并应用";
    });
    $("#btnTestCfg").addEventListener("click", async () => {
      $("#healthBox").innerHTML = "测试中…";
      try {
        await API.post("/api/config", { patch: collect() });
        await showHealth();
      } catch (e) {
        $("#healthBox").innerHTML = '<span class="err">测试失败：' + escapeHtml(e.message) + "</span>";
      }
    });
  }
  return { load: load, bind: bind };
})();
