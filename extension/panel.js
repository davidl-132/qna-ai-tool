// Popup trả lời dùng chung cho content.js (trong trang web) và answer.html (cửa sổ dự phòng).
// createPanel(...) trả về { el, run, stop, destroy }.
function createPanel({ text, context = "", pageTitle = "", onClose }) {
  const el = document.createElement("div");
  el.className = "hl-panel";
  el.innerHTML = `
    <div class="hl-head">
      <span class="hl-title">✦ Highlight AI</span>
      <button class="hl-icon" data-act="close" title="Đóng (Esc)">✕</button>
    </div>
    <div class="hl-quote"></div>
    <div class="hl-body"></div>
    <div class="hl-foot">
      <button class="hl-small" data-act="stop">■ Dừng</button>
      <button class="hl-small" data-act="copy" hidden>Copy</button>
      <button class="hl-small" data-act="retry" hidden>Thử lại</button>
      <span class="hl-meta"></span>
    </div>`;

  const $ = (sel) => el.querySelector(sel);
  const body = $(".hl-body");
  $(".hl-quote").textContent = text;

  let port = null;
  let answer = "";

  // Chỉ tự cuộn xuống khi người dùng đang ở gần cuối
  function render(streaming) {
    const nearBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 40;
    body.innerHTML = renderMarkdown(answer) + (streaming ? '<span class="hl-loading"></span>' : "");
    if (nearBottom) body.scrollTop = body.scrollHeight;
  }

  function setButtons(streaming) {
    $('[data-act="stop"]').hidden = !streaming;
    $('[data-act="copy"]').hidden = streaming || !answer;
    $('[data-act="retry"]').hidden = streaming;
  }

  function showError(message) {
    const div = document.createElement("div");
    div.className = "hl-error";
    div.textContent = "⚠ " + message;
    body.appendChild(div);
  }

  function stop() {
    if (!port) return;
    port.disconnect(); // background sẽ huỷ request tới server
    port = null;
    render(false);
    setButtons(false);
  }

  function run() {
    stop();
    answer = "";
    body.innerHTML = '<span class="hl-loading">Đang suy nghĩ</span>';
    $(".hl-meta").textContent = "";
    setButtons(true);

    port = chrome.runtime.connect({ name: "ask" });
    port.onMessage.addListener((ev) => {
      if (ev.type === "chunk") {
        answer += ev.text;
        render(true);
      } else if (ev.type === "meta") {
        $(".hl-meta").textContent = ev.model || ev.provider || "";
        if (ev.truncated) $(".hl-meta").textContent += " · đã cắt bớt text";
      } else if (ev.type === "done" || ev.type === "error") {
        port?.disconnect();
        port = null;
        render(false);
        if (ev.type === "error") showError(ev.message);
        setButtons(false);
      }
    });
    port.postMessage({ type: "ask", payload: { selection: text, context, page_title: pageTitle } });
  }

  async function copy() {
    await navigator.clipboard.writeText(answer).catch(() => {});
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
  $('[data-act="retry"]').onclick = run;

  return { el, run, stop, destroy };
}
