"""Offline regression tests; fixtures contain no account data or login state."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import crawler
import renderer


class RouteTests(unittest.TestCase):
    def test_work_route_and_invalid_ids(self):
        self.assertEqual(crawler._work_detail_url("123"),
                         "https://creator.douyin.com/creator-micro/work-management/work-detail/123")
        for invalid in ["", "../other", "123?item_id=456", "１２３"]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                crawler._work_detail_url(invalid)

    def test_allowlist_excludes_account_overview_and_foreign_hosts(self):
        for path in ["/web/api/creator/data/item/summarize/?item_id=123&signature=secret",
                     "/janus/douyin/creator/data/realtime/analysis/data_center",
                     "/janus/douyin/creator/data/item/play/source"]:
            self.assertTrue(crawler._is_detail_response("https://creator.douyin.com" + path))
        for url in ["https://creator.douyin.com/janus/douyin/creator/data/overview/dashboard",
                    "https://example.com/web/api/creator/data/item/summarize/",
                    "https://creator.douyin.com/creator-micro/data/following/media"]:
            self.assertFalse(crawler._is_detail_response(url))

    def test_report_retains_traffic_text_without_api_capture(self):
        text = renderer.render_report({"aweme_id": "123"}, "", [], [],
                                      {"流量分析": "平均播放时长\n12秒\n留存分析"})
        self.assertIn("平均播放时长\n12秒", text)
        self.assertIn("detail.json", text)
        self.assertIn("- 播放：-", text)


    def test_pr61_structured_metrics_remain_available(self):
        captures = [{"data": {"items": [{"metrics": {"completion_rate": .25,
                                                   "avg_view_second": 12}}]}}]
        text = renderer.render_report({"aweme_id": "123"}, "", [], captures,
                                      {"总览": "synthetic overview"})
        self.assertIn("完播率：25.00%", text)
        self.assertIn("平均观看时长：12.00s", text)
        self.assertIn("synthetic overview", text)


class CollectionTests(unittest.IsolatedAsyncioTestCase):
    def make_page(self):
        page = MagicMock()
        page.goto = AsyncMock()
        page.close = AsyncMock()
        locator = MagicMock()
        locator.wait_for = AsyncMock()
        locator.click = AsyncMock()
        locator.count = AsyncMock(return_value=0)
        page.get_by_text.return_value = locator
        page.locator.return_value.inner_text = AsyncMock(return_value="平均播放时长\n12秒")
        return page

    async def test_login_or_wrong_page_fails_and_closes(self):
        page = self.make_page()
        page.get_by_text.return_value.wait_for.side_effect = TimeoutError("no work tabs")
        session = SimpleNamespace(ctx=SimpleNamespace(new_page=AsyncMock(return_value=page)))
        with self.assertRaises(TimeoutError):
            await crawler.fetch_video_detail(session, "123")
        page.close.assert_awaited_once()

    async def test_no_responses_is_not_silent_success(self):
        page = self.make_page()
        session = SimpleNamespace(ctx=SimpleNamespace(new_page=AsyncMock(return_value=page)))
        with patch.object(crawler.asyncio, "sleep", new=AsyncMock()):
            with self.assertRaisesRegex(RuntimeError, "No work-detail responses"):
                await crawler.fetch_video_detail(session, "123")
        page.close.assert_awaited_once()

    async def test_lazy_traffic_capture_preserves_data_and_strips_query(self):
        page = self.make_page()
        listener = None
        def listen(event, handler):
            nonlocal listener
            listener = handler
        page.on.side_effect = listen
        async def click():
            response = SimpleNamespace(
                url="https://creator.douyin.com/janus/douyin/creator/data/realtime/analysis/data_center?signature=secret",
                json=AsyncMock(return_value={"analysis_trend": {"current_item": [{"key": "00:02", "value": .7}]}}))
            listener(response)
        page.get_by_text.return_value.click.side_effect = click
        optional = MagicMock()
        optional.count = AsyncMock(return_value=1)
        optional.is_visible = AsyncMock(return_value=True)
        optional.click = AsyncMock()
        primary = page.get_by_text.return_value
        page.get_by_text.side_effect = lambda name, **kw: optional if name in ("观众分析", "评论热词") else primary
        session = SimpleNamespace(ctx=SimpleNamespace(new_page=AsyncMock(return_value=page)))
        with patch.object(crawler.asyncio, "sleep", new=AsyncMock()):
            data = await crawler.fetch_video_detail(session, "123")
        self.assertEqual(data["aweme_id"], "123")
        self.assertEqual(set(data["sections"]), {"总览", "流量分析", "观众分析", "评论热词"})
        self.assertEqual(optional.click.await_count, 2)
        self.assertEqual(data["captured"][0]["data"]["analysis_trend"]["current_item"][0]["value"], .7)
        self.assertNotIn("?", data["captured"][0]["url"])
        page.get_by_text.assert_any_call("流量分析", exact=True)
        page.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
