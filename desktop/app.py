"""App popup: phím tắt toàn cục + khung đáp án nhỏ ở góc màn hình.

Chạy (Windows):
    py -m desktop.app

Bấm đơn (không kèm phím khác): Left Alt = chụp màn hình hỏi AI, Left Shift = ẩn/hiện khung.
Bôi đen chữ ở bất kỳ app nào, giữ nguyên ~1 giây: tự tra, khung tự hiện đáp án.

Chỉ có 3 phím: Left Alt, Left Shift (bấm đơn) và Ctrl+Alt+0 (bật/tắt cả app; đổi bằng HOTKEY_TOGGLE).
Xem câu trước/sau: mũi tên Trái/Phải khi khung đang hiện (hoặc nút ‹ › trên khung).

Dừng: bấm Ctrl+C trong cửa sổ terminal đang chạy app.
"""
import argparse
import functools
import os
import sys

from core import config, llm, prompts


def _pretty(spec: str) -> str:
    return "+".join(p.capitalize() if len(p) > 1 else p.upper() for p in spec.split("+"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", default="answer", choices=sorted(prompts.IMAGE_MODES))
    ap.add_argument("--question", default="", help="câu hỏi thêm gửi kèm mỗi ảnh chụp")
    ap.add_argument("--lang", default=config.DEFAULT_LANG)
    ap.add_argument("--no-review", action="store_true", default=not config.AGENT_REVIEW,
                    help="tắt vòng tự kiểm tra (chỉ 1 lượt gọi AI, nhanh hơn)")
    ap.add_argument("--solid", action="store_true",
                    help="dùng khung đặc thay cho chế độ ghost (mặc định: ghost, nền trong suốt, chỉ còn chữ)")
    ap.add_argument("--no-select", action="store_true", default=not config.SELECT_AUTO,
                    help="tắt tự tra chữ bôi đen (vẫn giữ phím bấm đơn Alt/Shift)")
    ap.add_argument("--no-ensemble", action="store_true", default=not config.ENSEMBLE,
                    help="chỉ dùng 1 AI (tắt chế độ nhiều AI cùng trả lời rồi tổng hợp)")
    ap.add_argument("--no-nav-keys", action="store_true", default=not config.NAV_KEYS,
                    help="không dùng mũi tên Trái/Phải để xem câu trước/sau")
    ap.add_argument("--auto-show", action="store_true", default=config.POPUP_AUTO_SHOW,
                    help="tự hiện khung khi chụp xong (mặc định: chỉ hiện khi bấm phím 'hiện')")
    args = ap.parse_args()

    if sys.platform != "win32":
        sys.exit("App popup hiện chỉ chạy trên Windows.")
    import tkinter as tk

    from .controller import Controller
    from .hotkeys import HotkeyListener, is_bare_typing_key
    from .inputhooks import DEFAULT_BLOCK_APPS, InputHooks
    from .popup import Popup
    from .screen import capture_png, enable_dpi_awareness
    from .selection import parse_tap
    VK_LABELS = {"lalt": "Left Alt", "ralt": "Right Alt", "lshift": "Left Shift", "rshift": "Right Shift",
                 "lctrl": "Left Ctrl", "rctrl": "Right Ctrl"}

    enable_dpi_awareness()  # trước khi tạo cửa sổ đầu tiên, nếu không khung popup sẽ lệch/co nhỏ trên màn hình phóng to
    root = tk.Tk()
    root.withdraw()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # in được tiếng Việt/emoji, không crash vì mã hóa
    popup = Popup(root, alpha=config.POPUP_OPACITY, ghost=config.POPUP_GHOST and not args.solid)
    members, skipped = [], []
    if not args.no_ensemble:
        for name in dict.fromkeys(config.ENSEMBLE_PROVIDERS):
            if name not in llm.PROVIDERS or name == "mock":
                skipped.append(f"{name} (không hỗ trợ)")
            elif llm.provider_ready(name):
                members.append((name, functools.partial(llm.ask_stream_one, name)))
            else:
                skipped.append(f"{name} (chưa có key trong .env)")
    if len(members) < 2:
        members = []  # cần ít nhất 2 AI mới có "tổng hợp"; còn lại chạy đường cũ (1 AI + tự kiểm tra)
    ctl = Controller(popup, capture_png, mode=args.mode, question=args.question, lang=args.lang,
                     auto_show=args.auto_show, review=not args.no_review,
                     members=members, ensemble_text=config.ENSEMBLE_TEXT,
                     capture_key=VK_LABELS.get(config.TAP_CAPTURE.strip().lower(), "Left Alt"))
    popup.on_hide, popup.on_prev, popup.on_next = ctl.hide, ctl.prev, ctl.next

    import queue

    pressed: queue.Queue = queue.Queue()
    listener = HotkeyListener({}, pressed.put, toggle=config.HOTKEY_TOGGLE)
    listener.start()
    listener.ready.wait(3)
    for err in listener.errors:
        print("⚠", err)
    print("Đã đăng ký phím:", ", ".join(_pretty(k) for k in listener.registered) or "KHÔNG CÓ PHÍM NÀO")
    if config.HOTKEY_TOGGLE and is_bare_typing_key(config.HOTKEY_TOGGLE):
        print(f"⚠ Phím {_pretty(config.HOTKEY_TOGGLE)} đang bị app chiếm: bấm phím này ở app khác sẽ KHÔNG gõ ra ký tự. "
              "Nên dùng dạng có phím bổ trợ, ví dụ ctrl+alt+0.")

    taps: dict[int, str] = {}
    for spec, action in ((config.TAP_CAPTURE, "capture"), (config.TAP_POPUP, "toggle")):
        if spec:
            try:
                taps[parse_tap(spec)] = action
            except ValueError as e:
                print(f"⚠ {e}")
    hooks = None
    if taps or not args.no_select or not args.no_nav_keys:
        hooks = InputHooks(pressed.put, taps, select=not args.no_select, settle=config.SELECT_SETTLE,
                           block_apps=config.SELECT_BLOCK_APPS or DEFAULT_BLOCK_APPS,
                           only_apps=config.SELECT_ONLY_APPS, text_limit=config.MAX_SELECTION_CHARS,
                           nav=not args.no_nav_keys)
        hooks.start()
        hooks.ready.wait(3)
        for err in hooks.errors:
            print("⚠", err)

    def beep(kind: int) -> None:
        try:
            import ctypes

            ctypes.windll.user32.MessageBeep(kind)  # 0x40 = tiếng "bật", 0x10 = tiếng "tắt"
        except Exception:  # noqa: BLE001
            pass

    def on_key(name) -> None:
        if isinstance(name, tuple):  # ("text", chữ vừa bôi đen)
            text = name[1]
            print(f"🔎 Tra chữ bôi đen ({len(text)} ký tự): {text[:60]!r}")
            ctl.start_text(text)
            return
        print(f"⌨ nhận phím: {name}")  # để thấy phím có tới app hay không
        if name in ("on", "off") and hooks:
            hooks.enabled = name == "on"
        if name == "on":
            beep(0x40)
            print("🟢 BẬT: các phím tắt đang hoạt động.")
        elif name == "off":
            ctl.hide()  # tắt thì ẩn luôn khung; lịch sử vẫn giữ
            beep(0x10)
            print(f"🔴 TẮT: phím tắt đã nhả ra, gõ phím bình thường. Bấm {_pretty(config.HOTKEY_TOGGLE)} để bật lại.")
        else:
            ctl.handle(name)

    def tick() -> None:
        try:
            while True:
                try:
                    name = pressed.get_nowait()
                except queue.Empty:
                    break
                try:
                    on_key(name)
                except Exception as e:  # noqa: BLE001 - một lỗi không được làm dừng cả vòng lặp
                    print(f"⚠ Lỗi khi xử lý phím '{name}': {e!r}")
            if hooks:
                hooks.popup_rect = popup.rect()
                hooks.nav_active = popup.visible and len(ctl.history) > 1
            ctl.pump()
        except Exception as e:  # noqa: BLE001
            print(f"⚠ Lỗi nội bộ: {e!r}")
        finally:
            root.after(60, tick)

    print("Highlight AI (app popup) đang chạy — thứ tự thử: " + " → ".join(llm.provider_chain()))
    if config.HOTKEY_TOGGLE:
        print(f"  {_pretty(config.HOTKEY_TOGGLE)}: BẬT/TẮT toàn bộ app")
    if members:
        print("  NHIỀU AI: " + " + ".join(n for n, _ in members) + " trả lời song song, khác nhau thì tổng hợp lại"
              + ("" if config.ENSEMBLE_TEXT else " (tra chữ bôi đen chỉ dùng 1 AI)"))
    elif not args.no_ensemble:
        print("  ⚠ Chế độ nhiều AI chưa bật: cần ≥2 AI có key trong ENSEMBLE_PROVIDERS="
              + ",".join(config.ENSEMBLE_PROVIDERS) + (f" (bỏ qua: {', '.join(skipped)})" if skipped else ""))
    nav_line = ("  Mũi tên Trái/Phải (khi khung đang hiện): xem câu trước / sau, hoặc bấm nút ‹ › trên khung"
                if not args.no_nav_keys else "  Nút ‹ › trên khung: xem câu trước / sau")
    print(nav_line + ("  (chụp có tự kiểm tra lại đáp án)" if not args.no_review else ""))
    if hooks:
        if config.TAP_CAPTURE:
            print(f"  {VK_LABELS.get(config.TAP_CAPTURE.lower(), config.TAP_CAPTURE)} (bấm đơn): chụp màn hình và hỏi AI")
        if config.TAP_POPUP:
            print(f"  {VK_LABELS.get(config.TAP_POPUP.lower(), config.TAP_POPUP)} (bấm đơn): ẩn/hiện khung")
        if not args.no_select:
            print(f"  Bôi đen chữ ở mọi app, giữ {config.SELECT_SETTLE:g}s: tự tra (tắt bằng --no-select)")
    print("Dừng: Ctrl+C trong cửa sổ này.")
    root.after(60, tick)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
        if hooks:
            hooks.stop()


if __name__ == "__main__":
    main()
