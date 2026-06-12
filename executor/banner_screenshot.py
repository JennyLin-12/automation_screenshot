# screenshot.py
# -*- coding: utf-8 -*-
import asyncio
import argparse
import os
from datetime import datetime
from typing import Callable, Awaitable, Optional

from playwright.async_api import Page
from login import launch_and_login, HOME_URL

# 取得這支 script 的資料夾
script_dir = os.path.dirname(os.path.abspath(__file__))
# 圖片儲存資料夾
OUTPUT_DIR = os.path.join(script_dir, '..', 'banners')
# 最多截圖張數（避免無限）
MAX_SLIDES = 50

# =========================
# 內建工具：定位容器 & 觀察輪播
# =========================

BANNER_ATTR = 'data-banner-container'
BANNER_SELECTOR = f'[{BANNER_ATTR}="1"]'

async def wait_for_hero_carousel(page: Page, timeout_ms: int = 20000) -> None:
    """
    在頁面中尋找「hero banner 輪播容器」：
    規則：同一層底下包含 >=2 個 [data-ui-element-name="hero banner"]，
    且父層具備輪播容器常見特徵（flex/overflow hidden 等）。
    找到後會在該節點上標記 data-banner-container="1" 供後續使用。
    """
    await page.wait_for_function(
        """
        () => {
          const items = Array.from(document.querySelectorAll(
          'main [data-ui-element-name="hero banner"], section [data-ui-element-name="hero banner"]'
          ));
          if (items.length < 2) return false;

          const scoreMap = new Map();

          for (const el of items) {
            let p = el.parentElement;
            let depth = 0;
            while (p && depth < 6) {
              const count = p.querySelectorAll('[data-ui-element-name="hero banner"]').length;
              if (count >= 2) {
                const cs = getComputedStyle(p);
                const likely =
                  cs.display.includes('flex') ||
                  cs.overflowX === 'hidden' ||
                  cs.overflow === 'hidden';
                if (likely) {
                  scoreMap.set(p, (scoreMap.get(p) || 0) + 1);
                }
              }
              depth++;
              p = p.parentElement;
            }
          }

          // 取分數最高的父層
          let best = null, bestScore = 0;
          for (const [node, score] of scoreMap.entries()) {
            if (score > bestScore) { best = node; bestScore = score; }
          }
          if (!best) return false;

          best.setAttribute('data-banner-container', '1');
          return true;
        }
        """,
        timeout=timeout_ms,
    )

async def observe_banner_rotations(
    page: Page,
    on_switch: Callable[[int, int], Awaitable[None]],
    *,
    container_selector: str = BANNER_SELECTOR,
    max_switches: Optional[int] = None,   # None = 持續觀察直到外部停止
    stable_frames: int = 10,              # 需要連續多少幀「穩定」才算完成
    velocity_eps: float = 0.5,            # 單幀位移 <= 此值 視為停止（px/幀）
    include_initial: bool = True,         # 是否先對當前第一張觸發一次
) -> None:
    """
    觀察 container_selector 的輪播容器，每次「切換完成」就呼叫 on_switch(call_index, current_index)。
    current_index 以 0 為第一張。
    """
    # 確保容器已標記好
    await wait_for_hero_carousel(page)

    # 在頁面端掛一個 rAF 監聽器，完成一次就 push 索引到 queue
    await page.evaluate(
        """
        ({ stableFrames, velocityEps, includeInitial, sel }) => {
          if (window.__bannerWatcher && window.__bannerWatcher.stop) {
            window.__bannerWatcher.stop();
          }
          window.__bannerQueue = [];

          const container = document.querySelector(sel);
          if (!container) throw new Error("banner container not found: " + sel);

          function parseTranslateX(el) {
            const tf = getComputedStyle(el).transform || el.style.transform || "none";
            if (tf === "none") return 0;
            if (tf.startsWith("matrix3d(")) {
              const a = tf.slice(9,-1).split(",").map(s => parseFloat(s.trim()));
              return a[12] || 0; // tx
            }
            if (tf.startsWith("matrix(")) {
              const a = tf.slice(7,-1).split(",").map(s => parseFloat(s.trim()));
              return a[4] || 0;  // tx
            }
            const m = tf.match(/translate3d\\((-?\\d+(?:\\.\\d+)?)px/);
            if (m) return parseFloat(m[1]);
            const m2 = tf.match(/translate\\((-?\\d+(?:\\.\\d+)?)px/);
            if (m2) return parseFloat(m2[1]);
            return 0;
          }

          function slideWidth() {
            const first = container.querySelector('[data-ui-element-name="hero banner"]') || container.firstElementChild;
            if (!first) return 1;
            const r = first.getBoundingClientRect();
            return r.width || 1;
          }

          function currentIndex(w) {
            const x = parseTranslateX(container);
            if (w <= 1) return 0;
            return Math.round(Math.abs(x) / w);
          }

          let w = slideWidth() || 1;
          let prevIdx = currentIndex(w);
          let lastX = parseTranslateX(container);
          let stableCount = 0;
          let targetIdx = prevIdx;
          let step = 0; // 0: 等索引變化；1: 等穩定
          let stopped = false;
          let rafId = 0;

          if (includeInitial) window.__bannerQueue.push(prevIdx);

          const resizeObs = new ResizeObserver(() => { w = slideWidth() || 1; });
          resizeObs.observe(container);

          function loop() {
            if (stopped) return;
            const x = parseTranslateX(container);
            const curIdx = currentIndex(w);
            const v = Math.abs(x - lastX);

            if (step === 0) {
              if (curIdx !== prevIdx) { step = 1; targetIdx = curIdx; stableCount = 0; }
            } else {
              if (curIdx === targetIdx && v <= velocityEps) {
                stableCount++;
                if (stableCount >= stableFrames) {
                  prevIdx = targetIdx;
                  step = 0;
                  stableCount = 0;
                  window.__bannerQueue.push(prevIdx);
                }
              } else {
                if (curIdx !== targetIdx) targetIdx = curIdx;
                stableCount = 0;
              }
            }

            lastX = x;
            rafId = requestAnimationFrame(loop);
          }
          rafId = requestAnimationFrame(loop);

          window.__bannerWatcher = {
            stop() {
              stopped = true;
              if (rafId) cancelAnimationFrame(rafId);
              resizeObs.disconnect();
            }
          };
        }
        """,
        arg={
            "stableFrames": stable_frames,
            "velocityEps": velocity_eps,
            "includeInitial": include_initial,
            "sel": container_selector,
        },
    )

    # 循環等待 queue 事件並交給 callback
    fired = 0
    while True:
        if max_switches is not None and fired >= max_switches:
            await page.evaluate("window.__bannerWatcher && window.__bannerWatcher.stop();")
            break
        await page.wait_for_function("() => Array.isArray(window.__bannerQueue) && window.__bannerQueue.length > 0")
        idx = await page.evaluate("() => window.__bannerQueue.shift()")
        fired += 1
        await on_switch(fired, int(idx))

# =========================
# 主流程
# =========================

async def take_screenshots(email: str, password: str):
    print("[Screenshot] 啟動 Playwright 自動化")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    async with launch_and_login(email=email, password=password) as page:
        print("[Screenshot] 登入完成，開始截圖流程。")

        await page.set_viewport_size({"width": 1280, "height": 800})
        print("[Screenshot] 已設定視窗大小為 1280x800")

        # 導航 & 等待基礎載入
        await page.goto(HOME_URL, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except:
            pass

        # 自動定位「hero banner 容器」並打標記
        await wait_for_hero_carousel(page)
        print("[Screenshot] 已定位 hero banner 容器")

        # 計算輪播張數（以標記容器底下的 hero banner 為準）
        img_count = await page.eval_on_selector(
            '[data-banner-container="1"]',
            "el => el.querySelectorAll('[data-ui-element-name=\"hero banner\"]').length"
        )
        if not img_count or img_count <= 0:
            img_count = 1
        img_count = min(int(img_count), MAX_SLIDES)
        print(f"[Screenshot] 輪播中共偵測到 {img_count} 個 banner 項目")

        # 計算 Y 偏移（是否有 Extension 版頭）
        selector = (
            'div.bg_sbds-background-color-dark'
            '.h_0'
            '.transition_height_0\\.3s'
        )
        try:
            has_ext_header = await page.is_visible(selector, timeout=1000)
        except:
            has_ext_header = False
        y_offset = 64 if has_ext_header else 0
        print(f"[Screenshot] y_offset = {y_offset}")

        # 定義 callback：每次切換完成就截圖
        async def on_switch(call_index: int, current_index: int):
            filename = os.path.join(OUTPUT_DIR, f"banner_{call_index}.png")
            print(f"[Screenshot] 觸發第 {call_index} 次（索引 {current_index}）→ 截圖：{filename}")
            try:
                await page.screenshot(path=filename, clip={
                    "x": 0,
                    "y": y_offset,
                    "width": await page.evaluate("() => window.innerWidth"),
                    "height": (await page.evaluate("() => window.innerHeight")) - y_offset
                })
            except Exception as e:
                print(f"[Screenshot] 截圖失敗：{e!r}")

        # 觀察並觸發截圖：
        # - include_initial=True：先對目前第一張也截 1 次
        # - max_switches=img_count：總共觸發 img_count 次（含第一張）
        await observe_banner_rotations(
            page,
            on_switch,
            container_selector='[data-banner-container="1"]',
            max_switches=img_count,
            include_initial=True,
            stable_frames=10,
            velocity_eps=0.5,
        )

        print("[Screenshot] 截圖流程結束，瀏覽器已關閉。")

# =========================
# 入口
# =========================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Screenshot banners")
    parser.add_argument('-a', '--account', required=True, help='ShopBack login email')
    parser.add_argument('-p', '--password', required=True, help='ShopBack login password')
    args = parser.parse_args()

    asyncio.run(take_screenshots(email=args.account, password=args.password))
