"""Offline browser regressions using synthetic pages and intercepted responses.

Requires the Playwright Chromium installation used by the adapter. No account,
network access, cookies or real work data are used.
"""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from playwright.async_api import async_playwright

import crawler
import review


class DetailBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        self.addAsyncCleanup(self.pw.stop)
        self.addAsyncCleanup(self.browser.close)

    async def check_post(self, *, image, cached=False):
        metrics = ({"image_avg_view_count": 2.5, "description_spread_rate": .2}
                   if image else {"avg_view_second": 12, "completion_rate": .25})
        payload = {"status_code": 0, "items": [{"metrics": metrics}]}
        heading = "平均浏览图片数" if image else "平均播放时长"
        html = """<!doctype html><html><body>
          <button onclick="loadTraffic()">流量分析</button>
          <button>观众分析</button><button>评论热词</button>
          <section id="metrics">总览</section>
          <script>
          async function loadTraffic() {
            document.getElementById('metrics').textContent = %s;
            await fetch('/web/api/creator/item/mget?item_id=123');
          }
          </script></body></html>""" % json.dumps(heading)

        if cached:
            html = html.replace("await fetch('/web/api/creator/item/mget?item_id=123');", "")
            html = html.replace("</script>", "fetch('/web/api/creator/item/mget?item_id=123');</script>")

        async def respond(route):
            if "/web/api/creator/item/mget" in route.request.url:
                await route.fulfill(json=payload)
            else:
                await route.fulfill(content_type="text/html; charset=utf-8", body=html)
        await self.context.route("**/*", respond)
        session = SimpleNamespace(ctx=self.context)
        # Keep browser/event I/O real; omit only production settling delays.
        with patch.object(crawler.asyncio, "sleep", new=AsyncMock()):
            detail = await asyncio.wait_for(crawler.fetch_video_detail(session, "123"), timeout=5)
        self.assertEqual(len(detail["captured"]), 1)
        self.assertEqual(detail["captured"][0]["data"], payload)
        self.assertIn(heading, detail["sections"]["流量分析"])
        self.assertEqual(set(detail["sections"]), {"总览", "流量分析", "观众分析", "评论热词"})
        if image:
            self.assertNotIn("平均播放时长", "".join(detail["sections"].values()))

        # Exercise the real report-writing path after browser collection.
        with tempfile.TemporaryDirectory() as tmp:
            result = {"video": {"aweme_id": "123"}, "detail": detail, "comments": []}
            with patch.object(review.crawler, "fetch_all", new=AsyncMock(return_value=result)), \
                 patch.object(review, "videos_dir", return_value=Path(tmp)):
                await review.run_with_id("123", None)
            evidence = list(Path(tmp).rglob("detail.json"))
            reports = list(Path(tmp).rglob("report.md"))
            self.assertEqual(len(evidence), 1)
            self.assertEqual(len(reports), 1)
            saved = json.loads(evidence[0].read_text(encoding="utf-8"))
            self.assertEqual(saved["captured"][0]["data"], payload)
            text = reports[0].read_text(encoding="utf-8")
            self.assertIn(heading, text)
            self.assertIn("平均浏览图片数：2.50" if image else "平均观看时长：12.00s", text)

    async def test_image_post_without_video_duration_label_keeps_metrics_and_report(self):
        await self.check_post(image=True)

    async def test_image_metrics_received_before_tab_click_are_retained(self):
        await self.check_post(image=True, cached=True)

    async def test_video_post_keeps_metrics_and_report(self):
        await self.check_post(image=False)


if __name__ == "__main__":
    unittest.main()
