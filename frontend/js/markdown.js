/* 轻量 Markdown 渲染（先转义 HTML 再结构化） */
window.MD = (function () {
  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function inline(s) {
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    s = s.replace(/\*([^*]+)\*/g, "<i>$1</i>");
    s = s.replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    return s;
  }
  function render(src) {
    if (!src) return "";
    const codeBlocks = [];
    let text = src.replace(/```(\w*)\n([\s\S]*?)```/g, function (_, lang, code) {
      codeBlocks.push(code.replace(/\n$/, ""));
      return "\x00CODE" + (codeBlocks.length - 1) + "\x00";
    });
    const lines = text.split("\n");
    let html = "";
    let listType = null;
    let table = null;

    function flushTable() {
      if (!table) return;
      let h = "<table>";
      table.forEach((row, i) => {
        h += "<tr>";
        row.forEach((cell) => {
          h += (i === 0 ? "<th>" : "<td>") + inline(cell.trim()) + (i === 0 ? "</th>" : "</td>");
        });
        h += "</tr>";
      });
      html += h + "</table>";
      table = null;
    }
    function flushList() {
      if (listType) { html += "</" + listType + ">"; listType = null; }
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.startsWith("|")) {
        if (!table) { flushList(); table = []; }
        const cells = line.replace(/^\||\|$/g, "").split("|");
        if (cells.every((c) => /^:?-{2,}:?$/.test(c.trim()))) continue; // 分隔行
        table.push(cells);
        continue;
      } else {
        flushTable();
      }
      const t = line.trim();
      if (!t) { flushList(); html += "\n"; continue; }

      const codeMatch = /^\x00CODE(\d+)\x00$/.exec(t);
      if (codeMatch) {
        flushList();
        html += "<pre><code>" + esc(codeBlocks[+codeMatch[1]]) + "</code></pre>";
        continue;
      }
      const head = /^(#{1,4})\s+(.*)$/.exec(t);
      if (head) {
        flushList();
        const lv = head[1].length;
        html += "<h" + lv + ">" + inline(head[2]) + "</h" + lv + ">";
        continue;
      }
      if (/^-{3,}$/.test(t)) { flushList(); html += "<hr>"; continue; }
      if (/^&gt;\s?/.test(t) || /^>\s?/.test(t)) {
        flushList();
        html += "<blockquote>" + inline(t.replace(/^>\s?/, "")) + "</blockquote>";
        continue;
      }
      const ul = /^[-*]\s+(.*)$/.exec(t);
      if (ul) {
        if (listType !== "ul") { flushList(); html += "<ul>"; listType = "ul"; }
        html += "<li>" + inline(ul[1]) + "</li>";
        continue;
      }
      const ol = /^\d+\.\s+(.*)$/.exec(t);
      if (ol) {
        if (listType !== "ol") { flushList(); html += "<ol>"; listType = "ol"; }
        html += "<li>" + inline(ol[1]) + "</li>";
        continue;
      }
      flushList();
      html += "<p>" + inline(t) + "</p>";
    }
    flushTable();
    flushList();
    return html;
  }
  return { render: render };
})();
