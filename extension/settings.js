// Cài đặt dùng chung cho background, options và các trang của extension.
const DEFAULT_SETTINGS = {
  serverUrl: "http://127.0.0.1:8765",
  token: "",
  mode: "explain",
  lang: "vi",
  excludedSites: "", // mỗi dòng một tên miền, ví dụ: vietcombank.com.vn
};

// true nếu `hostname` thuộc danh sách trang bị loại trừ (tính cả tên miền con)
function isExcluded(hostname, excludedSites) {
  return excludedSites
    .split(/[\s,]+/)
    .map((d) => d.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\/.*$/, ""))
    .filter(Boolean)
    .some((d) => hostname === d || hostname.endsWith("." + d));
}

async function getSettings() {
  const saved = await chrome.storage.local.get(Object.keys(DEFAULT_SETTINGS));
  return { ...DEFAULT_SETTINGS, ...saved };
}
