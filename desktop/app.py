"""App popup: phím tắt toàn cục + khung đáp án nhỏ ở góc màn hình.

Chạy (Windows):
    py -m desktop.app

Phím tắt mặc định (đổi trong .env: HOTKEY_SHOW, HOTKEY_HIDE, HOTKEY_CAPTURE):
    Ctrl+Alt+1   hiện khung đáp án
    Ctrl+Alt+2   ẩn khung (lịch sử vẫn giữ)
    Ctrl+Alt+3   chụp màn hình lúc đó rồi hỏi AI
    Ctrl+Alt+0   bật/tắt cả bộ phím trên (HOTKEY_TOGGLE)

Dừng: bấm Ctrl+C trong cửa sổ terminal đang chạy app.
"""
import argparse
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
    ap.add_argument("--auto-show", action="store_true", default=config.POPUP_AUTO_SHOW,
                    help="tự hiện khung khi chụp xong (mặc định: chỉ hiện khi bấm phím 'hiện')")
    args = ap.parse_args()

    if sys.platform != "win32":
        sys.exit("App popup hiện chỉ chạy trên Windows.")
    import tkinter as tk

    from .controller import Controller
    from .hotkeys import HotkeyListener, is_bare_typing_key
    from .popup import Popup
    from .screen import capture_png, enable_dpi_awareness

    keys = {"show": config.HOTKEY_SHOW, "hide": config.HOTKEY_HIDE, "capture": config.HOTKEY_CAPTURE}

    enable_dpi_awareness()  # trước khi tạo cửa sổ đầu tiên, nếu không khung popup sẽ lệch/co nhỏ trên màn hình phóng to
    root = tk.Tk()
    root.withdraw()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # in được tiếng Việt/emoji, không crash vì mã hóa
    popup = Popup(root)
    ctl = Controller(popup, capture_png, mode=args.mode, question=args.question, lang=args.lang,
                     auto_show=args.auto_show, capture_key=_pretty(keys["capture"]))
    popup.on_hide, popup.on_prev, popup.on_next = ctl.hide, ctl.prev, ctl.next

    import queue

    pressed: queue.Queue = queue.Queue()
    listener = HotkeyListener(keys, pressed.put, toggle=config.HOTKEY_TOGGLE)
    listener.start()
    listener.ready.wait(3)
    for err in listener.errors:
        print("⚠", err)
    print("Đã đăng ký phím:", ", ".join(_pretty(k) for k in listener.registered) or "KHÔNG CÓ PHÍM NÀO")
    bare = [_pretty(k) for k in (*keys.values(), config.HOTKEY_TOGGLE) if k and is_bare_typing_key(k)]
    if bare:
        print(f"⚠ Phím {', '.join(bare)} đang bị app chiếm: bấm các phím này ở app khác sẽ KHÔNG gõ ra ký tự. "
              "Muốn gõ lại thì tắt app (Ctrl+C), hoặc dùng num1/num2/num3 hay Ctrl+Alt+số.")

    def beep(kind: int) -> None:
        try:
            import ctypes

            ctypes.windll.user32.MessageBeep(kind)  # 0x40 = tiếng "bật", 0x10 = tiếng "tắt"
        except Exception:  # noqa: BLE001
            pass

    def on_key(name: str) -> None:
        print(f"⌨ nhận phím: {name}")  # để thấy phím có tới app hay không
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
            ctl.pump()
        except Exception as e:  # noqa: BLE001
            print(f"⚠ Lỗi nội bộ: {e!r}")
        finally:
            root.after(60, tick)

    print("Highlight AI (app popup) đang chạy — thứ tự thử: " + " → ".join(llm.provider_chain()))
    print(f"  {_pretty(keys['show'])}: hiện khung đáp án")
    print(f"  {_pretty(keys['hide'])}: ẩn khung (giữ lịch sử)")
    print(f"  {_pretty(keys['capture'])}: chụp màn hình và hỏi AI")
    if config.HOTKEY_TOGGLE:
        print(f"  {_pretty(config.HOTKEY_TOGGLE)}: BẬT/TẮT tất cả phím tắt ở trên")
    print("Dừng: Ctrl+C trong cửa sổ này.")
    root.after(60, tick)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()


if __name__ == "__main__":
    main()
