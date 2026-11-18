"""Giao diện terminal: làm câu trả lời của AI nổi bật, dễ phân biệt với phần còn lại.

- RichTerminal: dùng thư viện `rich` (khung màu, Markdown, hiệu ứng chờ).
- PlainTerminal: chữ thường, không màu (dùng khi chạy với --plain, hoặc chưa cài rich).
  Phù hợp khi muốn copy câu trả lời mà không dính đường viền.
"""
import time
from typing import Iterator

# Gợi ý cách xử lý cho các lỗi hay gặp: (từ khóa trong thông báo, lời khuyên)
HINTS = [
    ("503", "Google đang quá tải. Đợi vài phút rồi chụp lại, hoặc chạy `python -m scripts.test_models` để chọn model khác."),
    ("404", "Model này đã ngừng cấp cho key của bạn. Bỏ nó khỏi GEMINI_MODEL / GEMINI_FALLBACK_MODELS trong .env."),
    ("429", "Hết lượt miễn phí. Đợi một lúc, hoặc điền GROQ_API_KEY để có dự phòng."),
    ("không đọc được ảnh", "Gemini đang lỗi nên chuyển sang Groq, mà Groq mặc định chỉ đọc chữ. Chọn lại model Gemini chạy được."),
    ("Thiếu", "Chưa điền API key trong file .env. Điền xong, tắt rồi chạy lại chương trình."),
    ("Ảnh quá lớn", "Chụp vùng nhỏ hơn, hoặc tăng MAX_IMAGE_BYTES trong .env."),
]


def hint_for(message: str) -> str | None:
    for key, advice in HINTS:
        if key in message:
            return advice
    return None


def _fmt_elapsed(seconds: float) -> str:
    return f"{seconds:.1f}s"


class PlainTerminal:
    """Giao diện chữ thường (giống bản đầu tiên)."""

    def banner(self, mode: str, providers: list[str], lang: str) -> None:
        print("Đang theo dõi clipboard. Bấm Win+Shift+S để chụp, Ctrl+C để dừng.")
        print(f"Chế độ: {mode} | Ngôn ngữ: {lang} | Nhà cung cấp: {' → '.join(providers)}")

    def image_received(self, width: int, height: int, kb: int) -> None:
        print(f"\n[{time.strftime('%H:%M:%S')}] Nhận ảnh {width}x{height} ({kb} KB), đang hỏi AI…\n")

    def answer(self, pieces: Iterator[str], info: dict) -> str:
        start, text = time.time(), ""
        for piece in pieces:
            text += piece
            print(piece, end="", flush=True)
        print(f"\n\n[{info.get('provider')} / {info.get('model')} · {_fmt_elapsed(time.time() - start)}]")
        return text

    def error(self, message: str) -> None:
        print(f"⚠ {message}")
        hint = hint_for(message)
        if hint:
            print(f"→ {hint}")

    def separator(self) -> None:
        print("-" * 60)

    def stopped(self) -> None:
        print("\nĐã dừng.")


class RichTerminal(PlainTerminal):
    """Giao diện màu bằng `rich`."""

    def __init__(self, console=None) -> None:
        from rich.console import Console

        self.console = console or Console()

    # ----- các khối hiển thị -----

    def banner(self, mode: str, providers: list[str], lang: str) -> None:
        from rich import box
        from rich.panel import Panel
        from rich.table import Table

        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="dim", justify="right")
        grid.add_column()
        grid.add_row("Cách dùng", "Bấm [bold cyan]Win+Shift+S[/], kéo chọn vùng cần hỏi")
        grid.add_row("Chế độ", f"[bold]{mode}[/]  [dim](ngôn ngữ: {lang})[/]")
        grid.add_row("Nhà cung cấp", " [dim]→[/] ".join(f"[bold]{p}[/]" for p in providers))
        grid.add_row("Dừng", "[bold]Ctrl+C[/]")
        self.console.print(
            Panel(grid, title="[bold cyan]Highlight AI · Chụp ảnh", title_align="left",
                  border_style="cyan", box=box.ROUNDED, padding=(1, 2))
        )

    def image_received(self, width: int, height: int, kb: int) -> None:
        from rich.rule import Rule

        self.console.print()
        self.console.print(
            Rule(f"[bold cyan]◆ Ảnh {width}×{height} · {kb} KB · {time.strftime('%H:%M:%S')}", style="cyan")
        )

    def _panel(self, text: str, info: dict, elapsed: float | None):
        from rich import box
        from rich.markdown import Markdown
        from rich.panel import Panel

        sub = ""
        if info.get("model"):
            sub = f"{info.get('provider')} · {info['model']}"
            if elapsed is not None:
                sub += f" · {_fmt_elapsed(elapsed)}"
        return Panel(
            Markdown(text or "…"),
            title="[bold green]✦ Trả lời", title_align="left",
            subtitle=f"[dim]{sub}[/]" if sub else None, subtitle_align="right",
            border_style="green", box=box.ROUNDED, padding=(1, 2),
        )

    def answer(self, pieces: Iterator[str], info: dict) -> str:
        """Hiện hiệu ứng chờ, rồi chữ chạy dần; xong thì in lại khung trả lời hoàn chỉnh."""
        from rich.live import Live
        from rich.segment import Segment

        ui, start, text = self, time.time(), ""

        class Tail:
            """Chỉ vẽ phần CUỐI của khung khi câu trả lời dài hơn màn hình (tránh bị cắt mất chữ mới)."""

            def __rich_console__(self, console, options):
                lines = console.render_lines(
                    ui._panel(text, info, None), options.reset_height(), pad=False
                )
                room = max(console.size.height - 2, 6)
                for line in lines[-room:]:
                    yield from line
                    yield Segment.line()

        status = self.console.status("[cyan]AI đang đọc ảnh…", spinner="dots")
        status.start()
        live = None
        try:
            for piece in pieces:
                if live is None:
                    status.stop()
                    live = Live(Tail(), console=self.console, refresh_per_second=12, transient=True)
                    live.start()
                text += piece
                live.update(Tail(), refresh=False)
        finally:
            status.stop()
            if live is not None:
                live.stop()
        if text:
            self.console.print(self._panel(text, info, time.time() - start))
        return text

    def error(self, message: str) -> None:
        from rich import box
        from rich.console import Group
        from rich.panel import Panel
        from rich.text import Text

        parts = [Text(message)]
        hint = hint_for(message)
        if hint:
            parts.append(Text())
            parts.append(Text.from_markup(f"[yellow]→ {hint}[/]"))
        self.console.print(
            Panel(Group(*parts), title="[bold red]✖ Lỗi", title_align="left",
                  border_style="red", box=box.ROUNDED, padding=(1, 2))
        )

    def separator(self) -> None:
        pass  # các khối đã tự ngăn cách bằng khung và đường kẻ

    def stopped(self) -> None:
        self.console.print("\n[dim]Đã dừng.[/]")


def make_terminal(plain: bool = False) -> PlainTerminal:
    """RichTerminal nếu có thư viện rich và không yêu cầu --plain; ngược lại PlainTerminal."""
    if plain:
        return PlainTerminal()
    try:
        return RichTerminal()
    except ImportError:
        return PlainTerminal()
