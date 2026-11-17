// Chạy trong mọi trang web: bắt vùng bôi đen, hiện nút nổi và popup trả lời.
(() => {
  if (window.__highlightAI) return; // tránh chạy 2 lần trong cùng 1 frame
  window.__highlightAI = true;

  let host = null;   // <div> gắn vào trang, chứa Shadow DOM
  let shadow = null;
  let btn = null;    // nút nổi
  let panel = null;  // popup (từ panel.js)

  // ---------- Shadow DOM: CSS của trang không làm vỡ giao diện ----------
  function ensureHost() {
    if (host && document.documentElement.contains(host)) return;
    host = document.createElement("div");
    host.style.cssText = "position:absolute;top:0;left:0;width:0;height:0;z-index:2147483647;";
    shadow = host.attachShadow({ mode: "closed" });
    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = chrome.runtime.getURL("ui.css");
    shadow.appendChild(css);
    document.documentElement.appendChild(host);
  }

  const isInsideUI = (e) => host && e.composedPath().includes(host);

  // ---------- Lấy vùng bôi đen ----------
  function readSelection() {
    const sel = window.getSelection();
    const text = sel ? sel.toString().trim() : "";
    if (!text || sel.rangeCount === 0) return null;
    const rect = sel.getRangeAt(0).getBoundingClientRect();
    if (!rect.width && !rect.height) return null;
    return { text, rect };
  }

  // Đổi toạ độ màn hình → toạ độ trang (để popup cuộn theo trang)
  const pageX = (x) => x + window.scrollX;
  const pageY = (y) => y + window.scrollY;

  // ---------- Nút nổi ----------
  function showButton(info) {
    ensureHost();
    hideButton();
    btn = document.createElement("button");
    btn.className = "hl-btn";
    btn.textContent = "✦ Hỏi AI";
    const left = Math.min(info.rect.right, window.innerWidth - 100);
    btn.style.left = `${pageX(Math.max(8, left - 40))}px`;
    btn.style.top = `${pageY(info.rect.bottom + 6)}px`;
    btn.addEventListener("mousedown", (e) => e.preventDefault()); // giữ nguyên vùng bôi đen
    btn.addEventListener("click", () => openPanel(info));
    shadow.appendChild(btn);
  }

  function hideButton() {
    btn?.remove();
    btn = null;
  }

  // ---------- Popup ----------
  function placePanel(el, rect) {
    const width = Math.min(400, window.innerWidth - 16);
    const left = Math.min(Math.max(8, rect.left), window.innerWidth - width - 8);
    el.style.left = `${pageX(left)}px`;
    const spaceBelow = window.innerHeight - rect.bottom;
    if (spaceBelow < 260 && rect.top > spaceBelow) {
      // Sát mép dưới → lật popup lên phía trên vùng chọn
      el.classList.add("above");
      el.style.top = `${pageY(rect.top - 8)}px`;
    } else {
      el.style.top = `${pageY(rect.bottom + 8)}px`;
    }
  }

  function openPanel(info) {
    ensureHost();
    hideButton();
    closePanel();
    panel = createPanel({ text: info.text, pageTitle: document.title, onClose: closePanel });
    shadow.appendChild(panel.el);
    placePanel(panel.el, info.rect);
    panel.run();
  }

  function closePanel() {
    panel?.destroy();
    panel = null;
  }

  // ---------- Sự kiện ----------
  document.addEventListener("mouseup", (e) => {
    if (isInsideUI(e)) return;
    setTimeout(() => {
      const info = readSelection();
      if (info) showButton(info);
      else hideButton();
    }, 10);
  });

  document.addEventListener("mousedown", (e) => {
    if (isInsideUI(e)) return;
    hideButton();
    closePanel();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { hideButton(); closePanel(); }
  });

  // Chuột phải → "Hỏi AI": background báo sang đây để mở popup tại vùng chọn
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type !== "open-from-menu") return;
    const info = readSelection() || {
      text: msg.text,
      rect: new DOMRect(window.innerWidth / 2 - 200, 80, 0, 0),
    };
    openPanel(info);
    sendResponse({ ok: true });
  });
})();
