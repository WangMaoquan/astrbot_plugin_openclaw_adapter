"""
OpenClaw Adapter - HTTP API 智能回复版
支持 responses 和 chat_completions 两种端点切换
"""
import os
os.environ['no_proxy'] = '*'

import asyncio
import json
from typing import Any, Dict, List, Optional

import aiohttp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.message.components import Plain
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot.core.platform.message_type import MessageType
from astrbot.core.star.filter.event_message_type import EventMessageType


# ===== 主适配器类 =====
@register(
    "openclaw_adapter",
    "OpenClaw",
    "OpenClaw 适配器 - HTTP API 智能回复版",
    "1.2.0"
)
class OpenClawAdapter(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.session = None
        
        # 直接打印 config 对象的属性用于调试
        
        # 配置参数 - 处理可能的 None 值
        ip_val = getattr(config, 'IP', None)
        port_val = getattr(config, 'PORT', None)
        base_url = f"http://{ip_val if ip_val else 'localhost'}:{port_val if port_val else '18789'}"
        
        adapter_type_val = getattr(config, 'ADAPTER_TYPE', None) or getattr(config, 'ADAPTER_TYPE_', None)
        adapter_type = adapter_type_val if adapter_type_val else 'responses'
        
        # 根据 adapter_type 选择端点
        if adapter_type == 'chat_completions':
            self.API_URL = f"{base_url}/v1/chat/completions"
            self.api_type = 'chat_completions'
        else:
            self.API_URL = f"{base_url}/v1/responses"
            self.api_type = 'responses'
        
        token_val = getattr(config, 'OPENCLAW_TOKEN', None)
        self.API_TOKEN = token_val if token_val else '01a616687c305d7a460e411dae07c076ad95e8849dd80744'
        
        agent_val = getattr(config, 'AGENT_ID', None)
        self.AGENT_ID = agent_val if agent_val else 'main'
        
        # 硬编码超时配置，不再从 schema 读取
        self.TIMEOUT = 30
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 1.0
        
        
        # 打印配置信息用于调试
        token_display = self.API_TOKEN[:10] + '...' if len(self.API_TOKEN) > 10 else self.API_TOKEN

    async def async_init(self):
        """异步初始化"""
        logger.info("[OpenClaw] 适配器加载中...")
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
        )
        logger.info("[OpenClaw] 适配器加载完成")

    async def call_openclaw_chat_completions(self, user_message: str, user_id: str) -> str:
        """调用 Chat Completions API"""
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
        
        try:
            async with self.session.post(
                self.API_URL,
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
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
        
        try:
            async with self.session.post(
                self.API_URL,
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
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
        """处理所有QQ消息并转发给OpenClaw获取智能回复"""
        if not self.session:
            await self.async_init()
        
        # 获取消息基本信息
        user_name = event.get_sender_name()
        user_id = str(event.get_sender_id())
        message_text = event.message_str
        
        if not message_text.strip():
            return
        
        # 确保 session 已初始化
        if not self.session:
            await self.async_init()
        
        # 调用 OpenClaw HTTP API 获取智能回复
        try:
            reply = await self.call_openclaw_api(message_text, user_id)
            logger.info(f"[OpenClaw] 收到回复")
        except Exception as e:
            logger.error(f"[OpenClaw] API调用异常: {e}")
            reply = f"处理消息失败"
        
        # 发送回复到QQ
        try:
            # 构造 session（使用 event 的信息）
            session = MessageSesion(
                event.get_platform_id() or event.get_self_id(),
                event.get_message_type(),
                event.get_session_id()
            )
            
            msg_chain = MessageChain()
            msg_chain.chain.append(Plain(reply))
            
            await self.context.send_message(session, msg_chain)
            logger.info(f"[OpenClaw] 回复发送成功")
        except Exception as e:
            logger.error(f"[OpenClaw] 发送回复失败: {e}")

    async def terminate(self):
        """清理资源"""
        if self.session:
            await self.session.close()