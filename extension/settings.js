// Cài đặt dùng chung cho background, options và các trang của extension.
const DEFAULT_SETTINGS = {
  serverUrl: "http://127.0.0.1:8765",
  token: "",
  mode: "explain",
  lang: "vi",
};

async function getSettings() {
  const saved = await chrome.storage.local.get(Object.keys(DEFAULT_SETTINGS));
  return { ...DEFAULT_SETTINGS, ...saved };
}
