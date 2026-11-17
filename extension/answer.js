// Trang trả lời dự phòng (PDF...): đọc selection từ storage.session rồi dùng chung Panel.
(async () => {
  const id = new URLSearchParams(location.search).get("id");
  const key = `pending-${id}`;
  const data = (await chrome.storage.session.get(key))[key];
  await chrome.storage.session.remove(key);

  const root = document.getElementById("root");
  if (!data) {
    root.textContent = "Không tìm thấy nội dung cần hỏi. Hãy bôi đen và chuột phải lại.";
    return;
  }
  document.title = `Highlight AI – ${data.selection.slice(0, 40)}`;
  const { mode } = await getSettings();
  const panel = createPanel({
    text: data.selection,
    pageTitle: data.page_title,
    mode,
    onClose: () => window.close(),
  });
  root.appendChild(panel.el);
  panel.run();
})();
