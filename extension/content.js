// Chạy trong mọi trang web: bắt vùng bôi đen, hiện nút nổi và popup trả lời.
(() => {
  if (window.__highlightAI) return; // tránh chạy 2 lần trong cùng 1 frame
  window.__highlightAI = true;

  let host = null;   // <div> gắn vào trang, chứa Shadow DOM
  let shadow = null;
  let btn = null;    // nút nổi
  let panel = null;  // popup (từ panel.js)
  let settings = { ...DEFAULT_SETTINGS };

  // Đọc cài đặt một lần, cập nhật khi người dùng đổi ở trang Options
  getSettings().then((s) => (settings = s));
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    for (const [k, v] of Object.entries(changes)) settings[k] = v.newValue;
  });
  const excludedHere = () => isExcluded(location.hostname, settings.excludedSites || "");

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
    // Không bao giờ gửi nội dung ô mật khẩu
    const active = document.activeElement;
    if (active?.tagName === "INPUT" && active.type === "password") return null;

    const sel = window.getSelection();
    const text = sel ? sel.toString().trim() : "";
    if (!text || sel.rangeCount === 0) return null;
    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    if (!rect.width && !rect.height) return null;
    return { text, rect, context: getContext(range, text) };
  }

  // Lấy đoạn văn xung quanh vùng chọn (khoảng 1500 ký tự) để AI hiểu đúng ngữ cảnh
  const BLOCK = "p, li, td, th, dd, blockquote, pre, h1, h2, h3, h4, h5, h6, article, section, main, div";
  function getContext(range, text, limit = 1500) {
    let node = range.commonAncestorContainer;
    if (node.nodeType !== Node.ELEMENT_NODE) node = node.parentElement;
    let block = node?.closest(BLOCK) || document.body;
    // Leo lên khối cha cho tới khi đủ dài hơn hẳn phần bôi đen
    while (block.parentElement && block !== document.body && (block.innerText || "").length < text.length + 300) {
      block = block.parentElement.closest(BLOCK) || document.body;
    }
    const full = (block.innerText || "").replace(/\s+/g, " ").trim();
    if (full.length <= limit) return full === text ? "" : full;
    const at = Math.max(0, full.indexOf(text.slice(0, 50)));
    const start = Math.max(0, at - Math.floor((limit - Math.min(text.length, limit)) / 2));
    return full.slice(start, start + limit);
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
    panel = createPanel({
      text: info.text,
      context: info.context || "",
      pageTitle: document.title,
      mode: settings.mode,
      onClose: closePanel,
    });
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
    if (isInsideUI(e) || excludedHere()) return;
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
