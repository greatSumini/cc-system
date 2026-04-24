"""persuasion-review UX probe용 얇은 Playwright CLI.

각 invocation은 fresh chromium을 띄우고, state 파일에서 storage_state + 직전 URL을
복원한 뒤, 단일 명령을 수행하고 state를 저장한 후 종료한다. Claude 세션의 Bash 툴이
독립 호출 단위로 쓰기에 적합한 구조.

Commands:
  open URL                                         — 페이지로 이동.
  click SELECTOR                                   — 요소 클릭 (HTMX 버튼 추가 등).
  form --fill SEL VAL [--fill SEL VAL ...] [--submit SEL]
                                                   — 폼 여러 필드 채우고 (선택) 버튼 클릭.
                                                     fill 값은 invocation 간 DOM에 보존되지 않으므로
                                                     다단 폼은 이 명령 하나로 처리할 것.
  screenshot NAME                                  — 전체 페이지 PNG 저장 (--screenshots-dir/NAME.png).
  text SELECTOR                                    — innerText 출력.
  snapshot                                         — 현재 페이지의 간이 DOM 요약.
  url                                              — 현재 URL 출력.
  close                                            — state 파일 제거.

Exit codes: 0 성공 / 2 인자 오류 / 3 런타임 오류 (selector 미매치, timeout 등).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


DEFAULT_TIMEOUT_MS = 8000


def load_state(state_file: Path) -> dict:
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"url": None, "storage_state": None}
    return {"url": None, "storage_state": None}


def save_state(state_file: Path, url: str | None, context) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"url": url, "storage_state": context.storage_state()}
    state_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


SNAPSHOT_JS = """
() => {
  const out = [];
  out.push('URL: ' + location.href);
  out.push('TITLE: ' + document.title);
  out.push('--- HEADINGS ---');
  document.querySelectorAll('h1,h2,h3').forEach(h => out.push(h.tagName + ': ' + (h.innerText || '').trim()));
  out.push('--- FORM FIELDS ---');
  document.querySelectorAll('input,select,textarea').forEach(el => {
    out.push(`${el.tagName} name=${el.name||''} type=${el.type||''} placeholder=${el.placeholder||''} value=${(el.value||'').slice(0,60)}`);
  });
  out.push('--- BUTTONS ---');
  document.querySelectorAll('button,input[type=submit]').forEach(b => out.push('BUTTON: ' + (b.innerText || b.value || '').trim()));
  out.push('--- LINKS ---');
  [...document.querySelectorAll('a')].slice(0, 40).forEach(a => out.push(`A href=${a.getAttribute('href')||''} text=${(a.innerText||'').trim().slice(0,60)}`));
  return out.join('\\n');
}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-file", required=True, type=Path)
    ap.add_argument("--screenshots-dir", type=Path)
    ap.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_open = sub.add_parser("open"); p_open.add_argument("url")
    p_click = sub.add_parser("click"); p_click.add_argument("selector")
    p_form = sub.add_parser("form")
    p_form.add_argument("--fill", nargs=2, action="append", metavar=("SELECTOR", "VALUE"), default=[])
    p_form.add_argument("--submit", help="submit 버튼 selector (fill 이후 클릭)")
    p_ss = sub.add_parser("screenshot"); p_ss.add_argument("name")
    p_text = sub.add_parser("text"); p_text.add_argument("selector")
    sub.add_parser("snapshot")
    sub.add_parser("url")
    sub.add_parser("close")

    args = ap.parse_args()

    if args.cmd == "close":
        if args.state_file.exists():
            args.state_file.unlink()
        print("closed")
        return 0

    state = load_state(args.state_file)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx_kwargs = {"viewport": {"width": 1280, "height": 800}}
        if state.get("storage_state"):
            ctx_kwargs["storage_state"] = state["storage_state"]
        ctx = browser.new_context(**ctx_kwargs)
        page = ctx.new_page()
        page.set_default_timeout(args.timeout_ms)

        if args.cmd != "open" and state.get("url"):
            try:
                page.goto(state["url"])
            except PWTimeoutError as e:
                print(f"TIMEOUT resuming URL: {e}", file=sys.stderr)
                ctx.close(); browser.close()
                return 3

        rc = 0
        try:
            if args.cmd == "open":
                page.goto(args.url)
                print(f"OK url={page.url} title={page.title()!r}")
            elif args.cmd == "click":
                page.click(args.selector)
                print(f"OK url={page.url}")
            elif args.cmd == "form":
                for sel, val in args.fill:
                    page.fill(sel, val)
                if args.submit:
                    page.click(args.submit)
                print(f"OK url={page.url}")
            elif args.cmd == "screenshot":
                if not args.screenshots_dir:
                    print("ERROR: --screenshots-dir required", file=sys.stderr)
                    rc = 2
                else:
                    args.screenshots_dir.mkdir(parents=True, exist_ok=True)
                    path = args.screenshots_dir / f"{args.name}.png"
                    page.screenshot(path=str(path), full_page=True)
                    print(f"OK saved {path}")
            elif args.cmd == "text":
                print(page.locator(args.selector).first.inner_text())
            elif args.cmd == "snapshot":
                print(page.evaluate(SNAPSHOT_JS))
            elif args.cmd == "url":
                print(page.url)
        except PWTimeoutError as e:
            print(f"TIMEOUT: {e}", file=sys.stderr)
            rc = 3
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            rc = 3
        finally:
            try:
                save_state(args.state_file, page.url, ctx)
            except Exception as e:
                print(f"WARN: state save failed: {e}", file=sys.stderr)
            ctx.close()
            browser.close()
        return rc


if __name__ == "__main__":
    sys.exit(main())
