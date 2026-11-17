// Chuyển Markdown đơn giản → HTML an toàn.
// Escape toàn bộ HTML TRƯỚC, sau đó mới thêm thẻ của mình,
// nên câu trả lời của AI không thể chèn script vào trang.
function renderMarkdown(src) {
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inline = (s) =>
    esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\w)/g, "$1<em>$2</em>");

  const lines = (src || "").replace(/\r/g, "").split("\n");
  const out = [];
  let list = null; // "ul" | "ol" | null
  let para = [];
  let code = null; // mảng dòng khi đang ở trong ```

  const flushPara = () => {
    if (para.length) out.push(`<p>${para.map(inline).join("<br>")}</p>`);
    para = [];
  };
  const closeList = () => {
    if (list) out.push(`</${list}>`);
    list = null;
  };

  for (const line of lines) {
    if (code !== null) {
      if (/^\s*```/.test(line)) {
        out.push(`<pre><code>${esc(code.join("\n"))}</code></pre>`);
        code = null;
      } else code.push(line);
      continue;
    }
    if (/^\s*```/.test(line)) {
      flushPara(); closeList(); code = [];
      continue;
    }
    const h = line.match(/^\s*#{1,6}\s+(.*)$/);
    const ul = line.match(/^\s*[-*•]\s+(.*)$/);
    const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (h) {
      flushPara(); closeList();
      out.push(`<h4>${inline(h[1])}</h4>`);
    } else if (ul || ol) {
      flushPara();
      const kind = ul ? "ul" : "ol";
      if (list !== kind) { closeList(); out.push(`<${kind}>`); list = kind; }
      out.push(`<li>${inline((ul || ol)[1])}</li>`);
    } else if (!line.trim()) {
      flushPara(); closeList();
    } else {
      closeList();
      para.push(line);
    }
  }
  if (code !== null) out.push(`<pre><code>${esc(code.join("\n"))}</code></pre>`); // ``` chưa đóng (đang stream)
  flushPara(); closeList();
  return out.join("");
}
