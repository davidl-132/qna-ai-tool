// Popup trả lời dùng chung cho content.js (trong trang web) và answer.html (cửa sổ dự phòng).
// createPanel(...) trả về { el, run, stop, destroy }.
const MODE_LABELS = { explain: "Giải thích", translate: "Dịch", summarize: "Tóm tắt", answer: "Trả lời" };

function createPanel({ text, context = "", pageTitle = "", mode = "explain", onClose }) {
  const el = document.createElement("div");
  el.className = "hl-panel";
  el.innerHTML = `
    <div class="hl-head">
      <div class="hl-modes">
        ${Object.entries(MODE_LABELS)
          .map(([k, v]) => `<button class="hl-mode" data-mode="${k}">${v}</button>`)
          .join("")}
      </div>
      <button class="hl-icon" data-act="close" title="Đóng (Esc)">✕</button>
    </div>
    <div class="hl-quote"></div>
    <div class="hl-body"></div>
    <form class="hl-ask" hidden>
      <input type="text" placeholder="Hỏi tiếp về đoạn này…" maxlength="2000">
      <button class="hl-small" type="submit">Gửi</button>
    </form>
    <div class="hl-foot">
      <button class="hl-small" data-act="stop">■ Dừng</button>
      <button class="hl-small" data-act="copy" hidden>Copy</button>
      <button class="hl-small" data-act="retry" hidden>Thử lại</button>
      <span class="hl-meta"></span>
    </div>`;

  const $ = (sel) => el.querySelector(sel);
  const body = $(".hl-body");
  const askForm = $(".hl-ask");
  const askInput = $(".hl-ask input");
  $(".hl-quote").textContent = text;

  let port = null;
  // Cuộc hội thoại: lượt đầu { q: null, a }, các lượt hỏi tiếp { q: "...", a }
  let turns = [];

  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Chỉ tự cuộn xuống khi người dùng đang ở gần cuối
  function render(streaming) {
    const nearBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 40;
    body.innerHTML = turns
      .map((t, i) => {
        const q = t.q ? `<div class="hl-turn-q">${esc(t.q)}</div>` : "";
        const last = i === turns.length - 1;
        const a = !t.a && last && streaming
          ? '<span class="hl-loading">Đang suy nghĩ</span>'
          : renderMarkdown(t.a) + (last && streaming ? '<span class="hl-loading"></span>' : "");
        return q + a;
      })
      .join("");
    if (nearBottom) body.scrollTop = body.scrollHeight;
  }

  function setStreaming(streaming) {
    const last = turns.at(-1);
    $('[data-act="stop"]').hidden = !streaming;
    $('[data-act="copy"]').hidden = streaming || !last?.a;
    $('[data-act="retry"]').hidden = streaming;
    askForm.hidden = streaming || !last?.a;
  }

  function showError(message) {
    const div = document.createElement("div");
    div.className = "hl-error";
    div.textContent = "⚠ " + message;
    body.appendChild(div);
  }

  function setMode(m) {
    mode = m;
    el.querySelectorAll(".hl-mode").forEach((b) => b.classList.toggle("active", b.dataset.mode === m));
  }

  // Lịch sử gửi lên server: [assistant: trả lời trước, user: câu hỏi tiếp, ...]
  function followupPayload() {
    const out = [];
    for (let i = 1; i < turns.length; i++) {
      out.push({ role: "assistant", content: turns[i - 1].a });
      out.push({ role: "user", content: turns[i].q });
    }
    return out;
  }

  function stop() {
    if (!port) return;
    port.disconnect(); // background sẽ huỷ request tới server
    port = null;
    render(false);
    setStreaming(false);
  }

  // Chạy (lại) lượt cuối cùng trong `turns`
  function stream() {
    stop();
    const turn = turns.at(-1);
    turn.a = "";
    $(".hl-meta").textContent = "";
    render(true);
    setStreaming(true);

    port = chrome.runtime.connect({ name: "ask" });
    port.onMessage.addListener((ev) => {
      if (ev.type === "chunk") {
        turn.a += ev.text;
        render(true);
      } else if (ev.type === "meta") {
        $(".hl-meta").textContent = ev.model || ev.provider || "";
        if (ev.truncated) $(".hl-meta").textContent += " · đã cắt bớt text";
      } else if (ev.type === "done" || ev.type === "error") {
        port?.disconnect();
        port = null;
        render(false);
        if (ev.type === "error") showError(ev.message);
        setStreaming(false);
        if (ev.type === "done") askInput.focus({ preventScroll: true });
      }
    });
    port.postMessage({
      type: "ask",
      payload: { selection: text, context, page_title: pageTitle, mode, followup: followupPayload() },
    });
  }

  // Bắt đầu mới với mode hiện tại
  function run(newMode = mode) {
    setMode(newMode);
    turns = [{ q: null, a: "" }];
    stream();
  }

  function askMore(q) {
    q = q.trim();
    if (!q || port) return;
    turns.push({ q, a: "" });
    askInput.value = "";
    body.scrollTop = body.scrollHeight;
    stream();
  }

  async function copy() {
    await navigator.clipboard.writeText(turns.at(-1)?.a || "").catch(() => {});
    const b = $('[data-act="copy"]');
    b.textContent = "Đã copy ✓";
    setTimeout(() => (b.textContent = "Copy"), 1200);
  }

  function destroy() {
    stop();
    el.remove();
  }

  $('[data-act="close"]').onclick = () => (onClose ? onClose() : destroy());
  $('[data-act="stop"]').onclick = stop;
  $('[data-act="copy"]').onclick = copy;
  $('[data-act="retry"]').onclick = stream;
  el.querySelectorAll(".hl-mode").forEach((b) => (b.onclick = () => run(b.dataset.mode)));
  askForm.addEventListener("submit", (e) => {
    e.preventDefault();
    askMore(askInput.value);
  });
  // Không để phím gõ trong ô hỏi tiếp lọt ra trang (nhiều trang có phím tắt riêng)
  askInput.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") e.stopPropagation();
  });
  setMode(mode);

  return { el, run, stop, destroy };
}
