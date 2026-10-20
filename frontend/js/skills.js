/* 技能面板 */
window.Skills = (function () {
  async function load() {
    const data = await API.get("/api/skills");
    const list = $("#skillList");
    list.innerHTML = "";
    data.skills.forEach((s) => {
      const card = document.createElement("div");
      card.className = "skill-card";
      const params = (s.parameters || []).map((p) => p.name + "(" + p.type + ")").join("、") || "无参数";
      card.innerHTML =
        '<div class="top"><h3>' + escapeHtml(s.title) + ' <span class="tag">' + escapeHtml(s.name) + "</span></h3>" +
        '<label class="switch"><input type="checkbox" ' + (s.enabled ? "checked" : "") + ">" +
        '<span class="slider"></span></label></div>' +
        '<div class="desc">' + escapeHtml(s.description) + "</div>" +
        '<div class="params">参数：' + escapeHtml(params) + "</div>";
      card.querySelector("input").addEventListener("change", async (e) => {
        await API.post("/api/skills/" + s.name + "/toggle");
        load();
      });
      list.appendChild(card);
    });
  }
  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  return { load: load };
})();
