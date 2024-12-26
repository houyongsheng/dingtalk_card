import os
import logging
import asyncio
import argparse
from loguru import logger
from dingtalk_stream import AckMessage
import dingtalk_stream
import requests
import json
import platform
import urllib.parse
import aiohttp
import websockets
import time
from typing import Callable
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def define_options():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client_id",
        dest="client_id",
        default=os.getenv("DINGTALK_APP_KEY"),
        help="app_key from https://open-dev.digntalk.com",
    )
    parser.add_argument(
        "--client_secret",
        dest="client_secret",
        default=os.getenv("DINGTALK_APP_SECRET"),
        help="app_secret from https://open-dev.digntalk.com",
    )
    options = parser.parse_args()
    
    # 检查环境变量
    if not options.client_id or not options.client_secret:
        raise ValueError("DINGTALK_APP_KEY 和 DINGTALK_APP_SECRET 必须在环境变量中设置")
        
    return options


async def call_with_stream(query: str, callback: Callable[[str], None]):
    """调用AI模型并处理流式响应"""
    full_content = ""
    api_key = os.getenv('API_KEY')
    
    if not api_key:
        raise Exception("API_KEY not found in environment variables")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }
    
    data = {
        "inputs": {},
        "query": query,
        "user": "dify",
        "response_mode": "streaming",
    }
    
    logger.debug(f"Making API request with headers: {headers}")
    logger.debug(f"Request data: {data}")
    
    try:
        async with aiohttp.ClientSession() as session:
            base_url = os.getenv('DIFY_BASE_URL')
            if not base_url:
                raise ValueError("DIFY_BASE_URL must be set in environment variables")
                
            endpoint = os.getenv('DIFY_API_ENDPOINT', 'chat-messages')
            api_url = f"{base_url}/{endpoint}"
                
            async with session.post(
                api_url,
                headers=headers,
                json=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"API request failed with status {response.status}")
                    logger.error(f"Response headers: {dict(response.headers)}")
                    logger.error(f"Error text: {error_text}")
                    raise Exception(f"API request failed with status {response.status}: {error_text}")
            
                logger.debug("开始接收流式响应...")
                buffer = ""
                async for chunk, _ in response.content.iter_chunks():
                    if chunk:
                        chunk_text = chunk.decode('utf-8')
                        logger.debug(f"Raw chunk received: {chunk_text}")
                        buffer += chunk_text
                        lines = buffer.split('\n')
                        buffer = lines[-1]  # 保留最后一个不完整的行
                        
                        for line in lines[:-1]:  # 处理完整的行
                            line = line.strip()
                            if not line:
                                continue
                                
                            if line.startswith('data: '):
                                try:
                                    json_str = line[6:]
                                    if json_str == "[DONE]":
                                        logger.debug("Received [DONE] marker")
                                        continue
                                        
                                    chunk_data = json.loads(json_str)
                                    logger.debug(f"Parsed chunk data: {chunk_data}")
                                    
                                    # 处理不同类型的事件
                                    event_type = chunk_data.get("event")
                                    if event_type == "message":
                                        # 消息事件，包含实际的回答内容
                                        new_content = chunk_data.get("answer", "")
                                        if new_content:
                                            # 累加新内容而不是替换
                                            full_content += new_content
                                            await callback(full_content)
                                            logger.debug(f"Updated content: {full_content}")
                                    elif event_type == "error":
                                        # 错误事件
                                        error_msg = chunk_data.get("data", {}).get("message", "Unknown error")
                                        logger.error(f"Error event received: {error_msg}")
                                        raise Exception(f"Error from server: {error_msg}")
                                    else:
                                        # 其他工作流事件（workflow_started, node_started 等）
                                        logger.debug(f"Workflow event received: {event_type}")
                                        
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Failed to parse chunk as JSON: {line}")
                                    logger.warning(f"Error: {str(e)}")
                                    continue
                            else:
                                logger.debug(f"Received non-data line: {line}")

    except Exception as e:
        logger.error(f"调用AI模型失败: {str(e)}")
        raise
        
    return full_content


async def handle_reply_and_update_card(self: dingtalk_stream.ChatbotHandler, incoming_message: dingtalk_stream.ChatbotMessage):
    """处理回复并更新卡片"""
    # 卡片模板 ID
    card_template_id = os.getenv("CARD_TEMPLATE_ID")  # 从环境变量获取模板ID
    content_key = "content"
    card_data = {content_key: ""}
    
    try:
        card_instance = dingtalk_stream.AICardReplier(
            self.dingtalk_client, incoming_message
        )
        # 先投放卡片: https://open.dingtalk.com/document/orgapp/create-and-deliver-cards
        card_instance_id = await card_instance.async_create_and_deliver_card(
            card_template_id, card_data
        )

        # 再流式更新卡片: https://open.dingtalk.com/document/isvapp/api-streamingupdate
        async def callback(content_value: str):
            return await card_instance.async_streaming(
                card_instance_id,
                content_key=content_key,
                content_value=content_value,
                append=False,
                finished=False,
                failed=False,
            )

        try:
            full_content_value = await call_with_stream(
                incoming_message.text.content, callback
            )
            # 设置完成状态
            await card_instance.async_streaming(
                card_instance_id,
                content_key=content_key,
                content_value=full_content_value,
                append=False,
                finished=True,
                failed=False,
            )
        except Exception as e:
            logger.exception(e)
            # 设置失败状态
            await card_instance.async_streaming(
                card_instance_id,
                content_key=content_key,
                content_value=f"处理失败: {str(e)}",
                append=False,
                finished=False,
                failed=True,
            )
    except Exception as e:
        logger.exception(f"处理消息失败: {str(e)}")


def setup_logger():
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter('%(asctime)s %(name)-8s %(levelname)-8s %(message)s [%(filename)s:%(lineno)d]'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


class CardBotHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, logger: logging.Logger = None):
        super(dingtalk_stream.ChatbotHandler, self).__init__()
        if logger:
            self.logger = logger

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        """处理消息回调"""
        incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
        self.logger.info(f"收到消息：{incoming_message}")

        if incoming_message.message_type != "text":
            self.reply_text("俺只看得懂文字喔~", incoming_message)
            return AckMessage.STATUS_OK, "OK"

        # 创建异步任务处理消息
        asyncio.create_task(handle_reply_and_update_card(self, incoming_message))
        return AckMessage.STATUS_OK, "OK"


class DebugDingTalkStreamClient(dingtalk_stream.DingTalkStreamClient):
    def __init__(self, credential, logger):
        super().__init__(credential)
        self.logger = logger

    async def start(self):
        self.pre_start()

        while True:
            connection = self.open_connection()

            if not connection:
                self.logger.error('open connection failed')
                time.sleep(10)
                continue

            endpoint = connection.get('endpoint')
            ticket = connection.get('ticket')
            self.logger.info(f'Connecting to WebSocket endpoint: {endpoint}')
            self.logger.info(f'Using ticket: {ticket}')
            
            # 将 ticket 作为 URL 参数
            uri = f"{endpoint}?ticket={urllib.parse.quote_plus(ticket)}"
            self.logger.info(f'Full URI: {uri}')
            
            try:
                async with websockets.connect(uri) as websocket:
                    self.websocket = websocket
                    self.logger.info('WebSocket connection established')

                    async for message in websocket:
                        self.logger.info(f'Received message: {message}')
                        await self.background_task(json.loads(message))
            except Exception as e:
                self.logger.error(f'WebSocket connection failed: {str(e)}')
                time.sleep(3)
                continue


def main():
    """主函数"""
    # 设置日志
    logger = setup_logger()
    
    # 加载配置
    options = define_options()
    logger.info(f"App Key: {options.client_id}")
    logger.info(f"App Secret length: {len(options.client_secret) if options.client_secret else 0}")

    # 创建客户端
    credential = dingtalk_stream.Credential(options.client_id, options.client_secret)
    client = DebugDingTalkStreamClient(credential, logger)
    
    # 注册回调处理器
    handler = CardBotHandler(logger)
    client.register_callback_handler(
        dingtalk_stream.ChatbotMessage.TOPIC, handler
    )
    
    # 预启动并获取 token
    client.pre_start()
    token = client.get_access_token()
    if not token:
        logger.error("Failed to get access token")
        return
    
    # 启动客户端
    logger.info("Starting stream client...")
    asyncio.run(client.start())


if __name__ == "__main__":
    main()
