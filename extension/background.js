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

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== "ask-ai" || !info.selectionText) return;
  try {
    const data = await askOnce({ selection: info.selectionText });
    console.log(`[Highlight AI] (${data.provider})`, data.answer);
  } catch (e) {
    console.error("[Highlight AI]", e.message);
  }
});
