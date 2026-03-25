"""
OpenClaw Adapter - HTTP API 智能回复版
支持 responses 和 chat_completions 两种端点切换
"""
import asyncio
import os
from typing import Any, Dict, List, Optional

import aiohttp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.api import message_components as Comp
from astrbot.core.star.filter.event_message_type import EventMessageType


# ===== 主适配器类 =====
@register(
    "astrbot_plugin_openclaw_adapter",
    "OpenClaw",
    "OpenClaw 适配器 - HTTP API 智能回复版",
    "1.3.0"
)
class OpenClawAdapter(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.session = None
        self._session_lock = asyncio.Lock()

        # 设置环境变量
        os.environ['no_proxy'] = '*'

        # 配置参数 - 使用字典方式读取
        ip_val = config.get('IP', 'localhost')
        port_val = config.get('PORT', '18789')
        base_url = f"http://{ip_val}:{port_val}"

        adapter_type = config.get('ADAPTER_TYPE', 'responses')

        # 根据 adapter_type 选择端点
        if adapter_type == 'chat_completions':
            self.API_URL = f"{base_url}/v1/chat/completions"
            self.api_type = 'chat_completions'
        else:
            self.API_URL = f"{base_url}/v1/responses"
            self.api_type = 'responses'

        # Token 必须配置，不允许硬编码默认值
        self.API_TOKEN = config.get('OPENCLAW_TOKEN')
        if not self.API_TOKEN:
            logger.error("[OpenClaw] 未配置 OPENCLAW_TOKEN，请在插件配置中设置")
            raise ValueError("OPENCLAW_TOKEN 未配置")

        self.AGENT_ID = config.get('AGENT_ID', 'main')

        # 超时和重试配置
        self.TIMEOUT = 60  # 增加超时时间
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 1.0

        logger.info(f"[OpenClaw] 初始化完成 - API: {self.API_URL}, Agent: {self.AGENT_ID}")

    def _is_mentioned(self, event: AstrMessageEvent) -> bool:
        """检查机器人是否被@"""
        self_id = str(event.get_self_id())
        
        # 遍历消息链，检查是否有 At 组件
        for component in event.message_obj.message:
            if isinstance(component, Comp.At):
                # 检查是否 @ 的是机器人自己
                if str(component.qq) == self_id:
                    return True
        
        return False

    def _should_reply(self, event: AstrMessageEvent) -> tuple[bool, str]:
        """判断是否应该回复，返回 (是否回复, 原因)"""
        user_id = str(event.get_sender_id())
        self_id = str(event.get_self_id())
        
        # 过滤机器人自己的消息
        if user_id == self_id:
            return False, "自己的消息"
        
        group_id = event.get_group_id()
        
        if group_id:
            # 群聊：只有被@才回复
            if self._is_mentioned(event):
                return True, f"群聊@触发 (群: {group_id})"
            else:
                return False, f"群聊未@ (群: {group_id})"
        else:
            # 私聊：所有消息都回复
            return True, "私聊消息"

    async def _ensure_session(self):
        """确保 session 已初始化（线程安全）"""
        async with self._session_lock:
            if self.session is None or self.session.closed:
                logger.info("[OpenClaw] 初始化 HTTP Session...")
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
                )
                logger.info("[OpenClaw] HTTP Session 初始化完成")

    async def call_openclaw_chat_completions(self, user_message: str, user_id: str) -> str:
        """调用 Chat Completions API"""
        await self._ensure_session()
        headers = {
            "Authorization": f"Bearer {self.API_TOKEN}",
            "Content-Type": "application/json",
            "x-openclaw-agent-id": self.AGENT_ID
        }
        
        payload = {
            "model": f"openclaw:{self.AGENT_ID}",
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            "user": user_id
        }
        
        logger.debug(f"[OpenClaw-Chat] 请求: {user_message[:50]}...")
        try:
            async with self.session.post(
                self.API_URL,
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"[OpenClaw-Chat] 响应: {data}")
                    return data["choices"][0]["message"]["content"]
                else:
                    error_text = await response.text()
                    logger.error(f"[OpenClaw-Chat] API错误 {response.status}: {error_text}")
                    return f"API调用失败: {response.status}"
        except Exception as e:
            logger.error(f"[OpenClaw-Chat] 请求异常: {e}")
            return "连接OpenClaw服务失败"

    async def call_openclaw_responses(self, user_message: str, user_id: str) -> str:
        """调用 OpenResponses API"""
        await self._ensure_session()
        headers = {
            "Authorization": f"Bearer {self.API_TOKEN}",
            "Content-Type": "application/json",
            "x-openclaw-agent-id": self.AGENT_ID
        }
        
        payload = {
            "model": f"openclaw:{self.AGENT_ID}",
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": user_message
                }
            ],
            "user": user_id,
            "instructions": "你是糖浆，一个温和粘人的AI助手，用🍯表情符号保持友好风格"
        }
        
        logger.debug(f"[OpenClaw-Responses] 请求: {user_message[:50]}...")
        try:
            async with self.session.post(
                self.API_URL,
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"[OpenClaw-Responses] 响应: {data}")
                    # 解析响应内容
                    if "output" in data and len(data["output"]) > 0:
                        output_item = data["output"][0]
                        if output_item.get("type") == "message":
                            # content 是列表，需要提取 text
                            content_list = output_item.get("content", [])
                            if content_list and isinstance(content_list, list):
                                for item in content_list:
                                    if item.get("type") == "output_text":
                                        return item.get("text", "")
                            return str(content_list)
                    return "收到响应但格式异常"
                else:
                    error_text = await response.text()
                    logger.error(f"[OpenClaw-Responses] API错误 {response.status}: {error_text}")
                    return f"API调用失败: {response.status}"
        except Exception as e:
            logger.error(f"[OpenClaw-Responses] 请求异常: {e}")
            return "连接OpenClaw服务失败"

    async def call_openclaw_api(self, user_message: str, user_id: str, max_retries: int = 3, retry_delay: float = 1.0) -> str:
        """根据配置调用对应的 API，带重试机制"""
        last_error = ""
        
        for attempt in range(max_retries):
            try:
                if self.api_type == 'chat_completions':
                    result = await self.call_openclaw_chat_completions(user_message, user_id)
                else:
                    result = await self.call_openclaw_responses(user_message, user_id)
                
                # 检查是否成功（不是错误消息）
                if result and "失败" not in result and "异常" not in result and "错误" not in result:
                    return result
                
                # 如果是错误，记录并重试
                last_error = result
                logger.warning(f"[OpenClaw] 第 {attempt + 1} 次调用失败: {result[:50]}...")
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[OpenClaw] 第 {attempt + 1} 次调用异常: {e}")
            
            # 如果不是最后一次，等待后重试
            if attempt < max_retries - 1:
                logger.info(f"[OpenClaw] 等待 {retry_delay} 秒后重试...")
                await asyncio.sleep(retry_delay)
        
        # 所有重试都失败
        logger.error(f"[OpenClaw] 重试 {max_retries} 次后仍失败: {last_error}")
        return f"连接OpenClaw服务失败（已重试{max_retries}次）"

    @filter.event_message_type(EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        """处理消息并转发给OpenClaw获取智能回复
        
        规则：
        - 私聊：所有消息都回复
        - 群聊：只有 @机器人 时才回复
        """
        # 获取消息基本信息
        user_name = event.get_sender_name()
        user_id = str(event.get_sender_id())
        message_text = event.message_str

        # 过滤空消息
        if not message_text or not message_text.strip():
            return

        # 判断是否应该回复
        should_reply, reason = self._should_reply(event)
        if not should_reply:
            logger.debug(f"[OpenClaw] 跳过消息 - 原因: {reason}")
            return

        logger.info(f"[OpenClaw] 收到消息 - 用户: {user_name}, 触发: {reason}, 内容: {message_text[:50]}...")

        # 调用 OpenClaw HTTP API 获取智能回复
        try:
            reply = await self.call_openclaw_api(message_text, user_id)
            logger.info(f"[OpenClaw] 回复: {reply[:50]}...")
        except Exception as e:
            logger.error(f"[OpenClaw] API调用异常: {e}")
            reply = "处理消息失败"

        yield event.plain_result(reply)

    async def terminate(self):
        """清理资源"""
        if self.session:
            await self.session.close()