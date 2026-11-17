const FIELDS = Object.keys(DEFAULT_SETTINGS);
const $ = (id) => document.getElementById(id);
const status = (msg, ok = true) => {
  $("status").textContent = msg;
  $("status").className = ok ? "ok" : "err";
};

async function load() {
  const s = await getSettings();
  FIELDS.forEach((k) => ($(k).value = s[k]));
}

async function save() {
  const data = {};
  FIELDS.forEach((k) => (data[k] = $(k).value.trim()));
  data.serverUrl = data.serverUrl.replace(/\/+$/, "") || DEFAULT_SETTINGS.serverUrl;
  await chrome.storage.local.set(data);
  status("Đã lưu.");
}

async function test() {
  await save();
  const s = await getSettings();
  try {
    const health = await fetch(`${s.serverUrl}/health`).then((r) => r.json());
    const auth = await fetch(`${s.serverUrl}/auth-check`, { headers: { "X-Local-Token": s.token } });
    if (auth.status === 401) return status("Server chạy, nhưng token SAI.", false);
    if (!auth.ok) return status(`Server trả lỗi ${auth.status}.`, false);
    status(`Kết nối OK. Nhà cung cấp: ${health.providers.join(" → ")}`);
  } catch {
    status("Không kết nối được. Hãy chạy `python -m api.main` trước.", false);
  }
}

$("save").addEventListener("click", save);
$("test").addEventListener("click", test);
load();

// ---------- Lịch sử (lưu trong SQLite phía Python) ----------
const MODE_NAMES = { explain: "Giải thích", translate: "Dịch", summarize: "Tóm tắt", answer: "Trả lời" };

async function api(path, init = {}) {
  const s = await getSettings();
  const res = await fetch(`${s.serverUrl}${path}`, {
    ...init,
    headers: { "X-Local-Token": s.token, ...(init.headers || {}) },
  });
  if (!res.ok) throw new Error(res.status === 401 ? "Token sai" : `Lỗi ${res.status}`);
  return res.json();
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text) e.textContent = text; // textContent: không bao giờ chèn HTML
  return e;
}

async function loadHistory() {
  const box = $("history");
  box.textContent = "Đang tải…";
  try {
    const { items } = await api("/history?limit=30");
    box.textContent = items.length ? "" : "Chưa có lịch sử.";
    for (const it of items) {
      const card = el("div", "item");
      const when = new Date(it.created_at * 1000).toLocaleString("vi-VN");
      const what = [MODE_NAMES[it.mode] || it.mode, it.page_title, it.model].filter(Boolean).join(" · ");
      card.append(el("div", "meta", `${when} — ${what}`), el("div", "sel", it.selection.slice(0, 300)));
      if (it.question) card.append(el("div", "meta", `Hỏi tiếp: ${it.question}`));
      card.append(el("div", "ans", it.answer));
      box.append(card);
    }
  } catch (e) {
    box.textContent = `Không tải được lịch sử: ${e.message}. Server đã chạy chưa?`;
  }
}

let clearArmed = false;
async function clearHistory() {
  const b = $("clearHistory");
  if (!clearArmed) {
    clearArmed = true;
    b.textContent = "Bấm lần nữa để xoá";
    setTimeout(() => { clearArmed = false; b.textContent = "Xoá toàn bộ"; }, 3000);
    return;
  }
  clearArmed = false;
  b.textContent = "Xoá toàn bộ";
  try {
    const { deleted } = await api("/history", { method: "DELETE" });
    status(`Đã xoá ${deleted} mục.`);
    loadHistory();
  } catch (e) {
    status(`Không xoá được: ${e.message}`, false);
  }
}

$("loadHistory").addEventListener("click", loadHistory);
$("clearHistory").addEventListener("click", clearHistory);
