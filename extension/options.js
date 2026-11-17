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
