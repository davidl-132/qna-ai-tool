// Service worker: menu chuột phải + gọi server Python.
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

// Gọi POST /ask (một lần, không stream)
async function askOnce(payload) {
  const s = await getSettings();
  if (!s.token) throw new Error("Chưa nhập token. Mở trang cài đặt của extension.");

  let res;
  try {
    res = await fetch(`${s.serverUrl}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Local-Token": s.token },
      body: JSON.stringify({ mode: s.mode, lang: s.lang, ...payload }),
    });
  } catch {
    throw new Error("Không kết nối được server. Đã chạy `python -m api.main` chưa?");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Lỗi server ${res.status}`);
  return data;
}

// content.js gửi { type: "ask", payload } → trả về { ok, data } hoặc { ok: false, error }
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "ask") return;
  askOnce(msg.payload)
    .then((data) => sendResponse({ ok: true, data }))
    .catch((e) => sendResponse({ ok: false, error: e.message }));
  return true; // giữ kênh mở cho câu trả lời bất đồng bộ
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "ask-ai" || !info.selectionText) return;
  try {
    // Nhờ content script trong đúng frame mở popup tại vùng chọn
    await chrome.tabs.sendMessage(tab.id, { type: "open-from-menu", text: info.selectionText },
      { frameId: info.frameId ?? 0 });
  } catch {
    // Không có content script (PDF, tab mở trước khi cài extension...) → in ra console
    const data = await askOnce({ selection: info.selectionText }).catch((e) => ({ answer: e.message }));
    console.log("[Highlight AI]", data.answer);
  }
});
