// Service worker: menu chuột phải + gọi server Python (stream).
importScripts("settings.js");

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "ask-ai",
    title: 'Hỏi AI: "%s"',
    contexts: ["selection"],
  });
});

// Bấm vào icon extension → mở trang cài đặt
chrome.action.onClicked.addListener(() => chrome.runtime.openOptionsPage());

// ---------- Gọi POST /ask/stream và đọc từng sự kiện SSE ----------
async function askStream(payload, signal, emit) {
  const s = await getSettings();
  if (!s.token) throw new Error("Chưa nhập token. Bấm icon extension để mở trang cài đặt.");

  let res;
  try {
    res = await fetch(`${s.serverUrl}/ask/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Local-Token": s.token },
      body: JSON.stringify({ mode: s.mode, lang: s.lang, ...payload }),
      signal,
    });
  } catch (e) {
    if (signal.aborted) return;
    throw new Error("Không kết nối được server. Đã chạy `python -m api.main` chưa?");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = Array.isArray(data.detail) ? "Dữ liệu gửi lên không hợp lệ" : data.detail;
    throw new Error(detail || `Lỗi server ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      const obj = data ? JSON.parse(data) : {};
      if (event === "message") emit({ type: "chunk", text: obj.t });
      else if (event === "meta") emit({ type: "meta", ...obj });
      else if (event === "done") emit({ type: "done" });
      else if (event === "error") emit({ type: "error", message: obj.message });
    }
  }
}

// content.js / answer.js mở một "port" tên "ask"; đóng port = bấm Dừng → huỷ request.
chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== "ask") return;
  const ctrl = new AbortController();
  port.onDisconnect.addListener(() => ctrl.abort());
  const send = (msg) => {
    if (!ctrl.signal.aborted) port.postMessage(msg);
  };
  port.onMessage.addListener(async (msg) => {
    if (msg.type !== "ask") return;
    try {
      await askStream(msg.payload, ctrl.signal, send);
    } catch (e) {
      if (!ctrl.signal.aborted) send({ type: "error", message: e.message });
    }
  });
});

// ---------- Chuột phải "Hỏi AI" ----------
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "ask-ai" || !info.selectionText) return;
  try {
    // Nhờ content script trong đúng frame mở popup tại vùng chọn
    await chrome.tabs.sendMessage(tab.id, { type: "open-from-menu", text: info.selectionText },
      { frameId: info.frameId ?? 0 });
  } catch {
    // Không có content script (PDF viewer, tab mở trước khi cài extension...)
    // → mở cửa sổ trả lời riêng
    const id = crypto.randomUUID();
    await chrome.storage.session.set({
      [`pending-${id}`]: { selection: info.selectionText, page_title: tab?.title || "" },
    });
    chrome.windows.create({
      url: chrome.runtime.getURL(`answer.html?id=${id}`),
      type: "popup",
      width: 480,
      height: 600,
    });
  }
});
