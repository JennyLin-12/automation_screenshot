# utils/banner.py
# -*- coding: utf-8 -*-
from typing import Callable, Awaitable, Optional
from playwright.async_api import Page

DEFAULT_CONTAINER = ".carousel-container"

async def observe_banner_rotations(
    page: Page,
    on_switch: Callable[[int, int], Awaitable[None]],
    *,
    container_selector: str = DEFAULT_CONTAINER,
    max_switches: Optional[int] = None,  # None 表示無限觀察直到外部中止
    stable_frames: int = 10,             # 連續幀穩定的門檻
    velocity_eps: float = 0.5,           # 速度近似 0 的閾值（px/幀）
    include_initial: bool = True,        # 是否先對目前顯示的那張觸發一次
) -> None:
    """
    觀察唯一的 .carousel-container，每當「切換完成」就觸發 on_switch(call_index, current_index)
      - call_index 從 1 開始計數
      - current_index 是 0-based 的穩定索引

    注意：不在此方法內做任何截圖或 I/O，全部交給 on_switch。
    """
    # 等容器出現
    await page.wait_for_selector(container_selector, timeout=15000)

    # 在頁面端設置觀察器，完成一次切換就 push 索引到 queue
    await page.evaluate(
        """
        ({ sel, stableFrames, velocityEps, includeInitial }) => {
          // 清理舊 watcher
          if (window.__bannerWatcher && window.__bannerWatcher.stop) {
            window.__bannerWatcher.stop();
          }
          // 用 queue 跟 Python 溝通（Python 端用 wait_for_function 取值）
          window.__bannerQueue = [];

          const container = document.querySelector(sel);
          if (!container) throw new Error("container not found: " + sel);

          function parseTranslateX(el) {
            const cs = getComputedStyle(el);
            const tf = cs.transform || el.style.transform || "none";
            if (tf === "none") return 0;
            if (tf.startsWith("matrix3d(")) {
              const parts = tf.slice(9,-1).split(",").map(v => parseFloat(v.trim()));
              return parts[12] || 0; // tx
            }
            if (tf.startsWith("matrix(")) {
              const parts = tf.slice(7,-1).split(",").map(v => parseFloat(v.trim()));
              return parts[4] || 0;  // tx
            }
            const m = tf.match(/translate3d\\((-?\\d+(?:\\.\\d+)?)px/);
            if (m) return parseFloat(m[1]);
            const m2 = tf.match(/translate\\((-?\\d+(?:\\.\\d+)?)px/);
            if (m2) return parseFloat(m2[1]);
            return 0;
          }

          function slideWidth(container) {
            const first = container.querySelector('[data-ui-element-name="hero banner"]') || container.firstElementChild;
            if (!first) return 0;
            const r = first.getBoundingClientRect();
            return r.width || 0;
          }

          function currentIndex(container, w) {
            const x = parseTranslateX(container);
            if (w <= 1) return 0;
            return Math.round(Math.abs(x) / w);
          }

          const w = slideWidth(container) || 1;
          let prevIdx = currentIndex(container, w);
          let lastX = parseTranslateX(container);
          let stableCount = 0;
          let targetIdx = prevIdx;
          let step = 0; // 0: 等待索引變化；1: 等待穩定
          let stopped = false;
          let rafId = 0;

          if (includeInitial) {
            // 先把當前 index 當作第 1 次事件
            window.__bannerQueue.push(prevIdx);
          }

          function loop() {
            if (stopped) return;
            const x = parseTranslateX(container);
            const curIdx = currentIndex(container, w);
            const v = Math.abs(x - lastX);

            if (step === 0) {
              if (curIdx !== prevIdx) {
                step = 1;
                targetIdx = curIdx;
                stableCount = 0;
              }
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
            }
          };
        }
        """,
        arg={
            "sel": container_selector,
            "stableFrames": stable_frames,
            "velocityEps": velocity_eps,
            "includeInitial": include_initial,
        },
    )

    # 逐次等 queue 有值，取出索引後呼叫 callback
    fired = 0
    while True:
        if max_switches is not None and fired >= max_switches:
            # 停止頁面端 watcher
            await page.evaluate("window.__bannerWatcher && window.__bannerWatcher.stop();")
            break

        # 等到有事件進 queue
        await page.wait_for_function("() => Array.isArray(window.__bannerQueue) && window.__bannerQueue.length > 0")
        idx = await page.evaluate("() => window.__bannerQueue.shift()")
        fired += 1
        # 呼叫外部 callback
        await on_switch(fired, int(idx))
