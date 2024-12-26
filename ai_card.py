import os
import logging
import asyncio
import argparse
from loguru import logger
from typing import Callable
from dingtalk_stream import AckMessage
import dingtalk_stream
import requests
import json
import platform
import urllib.parse
import aiohttp
import websockets
import time
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
    
    endpoint = os.getenv('DIFY_API_ENDPOINT', 'chat-messages')
    
    # 根据不同的 endpoint 使用不同的请求数据格式
    if endpoint == 'workflows/run':
        data = {
            "inputs": {
                "query": query
            },
            "user": "dify",
            "response_mode": "streaming",
        }
    else:
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
                                        # 消息事件,包含实际的回答内容
                                        answer = chunk_data.get("answer", "")
                                        if answer:
                                            # 累加新内容
                                            full_content += answer
                                            await callback(full_content)
                                            logger.debug(f"Updated content: {full_content}")
                                            
                                    elif event_type == "text_chunk":
                                        # 文本块事件
                                        text = chunk_data.get("data", {}).get("text", "")
                                        if text:
                                            # 累加新内容
                                            full_content += text
                                            await callback(full_content)
                                            logger.debug(f"Updated content from chunk: {text}")
                                            
                                    elif event_type == "workflow_started":
                                        # 工作流开始
                                        workflow_id = chunk_data.get("workflow_run_id")
                                        logger.debug(f"Workflow started: {workflow_id}")
                                        
                                    elif event_type == "node_started":
                                        # 节点开始
                                        data = chunk_data.get("data", {})
                                        node_id = data.get("node_id")
                                        node_type = data.get("node_type")
                                        title = data.get("title")
                                        logger.debug(f"Node started - type: {node_type}, title: {title}")
                                        
                                    elif event_type == "node_finished":
                                        # 节点完成
                                        data = chunk_data.get("data", {})
                                        node_type = data.get("node_type")
                                        title = data.get("title")
                                        status = data.get("status")
                                        error = data.get("error")
                                        if error:
                                            logger.warning(f"Node failed - type: {node_type}, title: {title}, error: {error}")
                                        else:
                                            logger.debug(f"Node finished - type: {node_type}, title: {title}, status: {status}")
                                            
                                    elif event_type == "workflow_finished":
                                        # 工作流完成
                                        data = chunk_data.get("data", {})
                                        status = data.get("status")
                                        error = data.get("error")
                                        if error:
                                            logger.warning(f"Workflow failed: {error}")
                                        else:
                                            logger.debug(f"Workflow finished with status: {status}")
                                            
                                    elif event_type == "error":
                                        # 错误事件
                                        error_msg = chunk_data.get("data", {}).get("message", "Unknown error")
                                        logger.error(f"Error event received: {error_msg}")
                                        raise Exception(f"Error from server: {error_msg}")
                                        
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


async def download_image(download_code: str, client: dingtalk_stream.DingTalkStreamClient, robot_code: str) -> bytes:
    """下载图片"""
    try:
        # 获取access token
        access_token = client.get_access_token()
        
        if not access_token:
            raise ValueError("Failed to get access token")
            
        # 构建下载URL
        download_url = f"https://api.dingtalk.com/v1.0/robot/messageFiles/download"
        headers = {
            "x-acs-dingtalk-access-token": access_token,
            "Content-Type": "application/json"
        }
        data = {
            "downloadCode": download_code,
            "robotCode": robot_code
        }
        
        logger.info(f"下载图片, URL: {download_url}, headers: {headers}, data: {data}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(download_url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"Download failed with status {response.status}: {error_text}")
                    
                return await response.read()
                
    except Exception as e:
        logger.exception("下载图片失败")
        raise


async def upload_to_dify(file_path: str) -> str:
    """上传文件到dify"""
    try:
        api_key = os.getenv('API_KEY')
        if not api_key:
            raise ValueError("API_KEY not found in environment variables")
            
        base_url = os.getenv('DIFY_BASE_URL')
        if not base_url:
            raise ValueError("DIFY_BASE_URL must be set in environment variables")
            
        upload_url = f"{base_url}/files/upload"
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        # 准备FormData
        form = aiohttp.FormData()
        form.add_field('type', 'image')
        form.add_field('file',
                      open(file_path, 'rb'),
                      filename=os.path.basename(file_path),
                      content_type='image/jpeg')
        
        logger.info(f"正在上传文件到dify: {upload_url}")
        async with aiohttp.ClientSession() as session:
            async with session.post(upload_url, headers=headers, data=form) as response:
                result = await response.json()
                if response.status not in [200, 201]:  # 200和201都是成功状态码
                    raise ValueError(f"Upload failed with status {response.status}: {result}")
                    
                logger.info(f"文件上传成功: {result}")
                return result.get('id')
                    
    except Exception as e:
        logger.exception("上传文件到dify失败")
        raise


async def call_dify_workflow(image_id: str, callback = None) -> str:
    """调用dify workflow处理图片"""
    try:
        api_key = os.getenv('API_KEY')
        if not api_key:
            raise ValueError("API_KEY not found in environment variables")
            
        base_url = os.getenv('DIFY_BASE_URL')
        if not base_url:
            raise ValueError("DIFY_BASE_URL must be set in environment variables")
            
        workflow_url = f"{base_url}/workflows/run"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"  # 接收SSE流
        }
        
        data = {
            "inputs": {
                "query": "请分析这张图片的内容,告诉我这是什么"
            },
            "files": [{
                "type": "image",
                "transfer_method": "local_file",
                "upload_file_id": image_id
            }],
            "response_mode": "streaming",  # 使用streaming模式
            "user": "dingtalk"
        }
        
        logger.info(f"调用workflow处理图片: {workflow_url}, data: {data}")
        result_text = ""
        async with aiohttp.ClientSession() as session:
            async with session.post(workflow_url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"Workflow failed with status {response.status}: {error_text}")
                
                # 处理SSE流
                async for line in response.content:
                    if line:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            try:
                                event_data = json.loads(line[6:])  # 去掉'data: '前缀
                                logger.info(f"收到事件: {event_data}")
                                
                                # 处理text_chunk事件
                                if event_data.get('event') == 'text_chunk':
                                    chunk_text = event_data.get('data', {}).get('text', '')
                                    if chunk_text:
                                        result_text += chunk_text
                                        # 如果有callback,实时更新卡片
                                        if callback:
                                            await callback(result_text)
                                elif event_data.get('event') == 'error':
                                    raise ValueError(f"Workflow error: {event_data.get('message')}")
                                    
                            except json.JSONDecodeError:
                                logger.warning(f"无法解析事件数据: {line}")
                                
        if not result_text:
            result_text = "处理完成,但没有返回结果"
            
        return result_text
                
    except Exception as e:
        logger.exception("调用workflow失败")
        raise


async def process_image(image_data: bytes, callback: Callable[[str], None] = None) -> str:
    """处理图片并返回结果"""
    try:
        # 保存图片到临时文件
        temp_path = "temp_image.jpg"
        with open(temp_path, "wb") as f:
            f.write(image_data)
            
        logger.info(f"图片已保存到: {temp_path}")
        
        try:
            # 上传到dify
            image_id = await upload_to_dify(temp_path)
            
            # 调用workflow处理
            result = await call_dify_workflow(image_id, callback)
            
        finally:
            # 清理临时文件
            os.remove(temp_path)
            logger.info("临时文件已清理")
        
        return result
        
    except Exception as e:
        logger.exception("处理图片失败")
        raise


async def handle_reply_and_update_card(self: dingtalk_stream.ChatbotHandler, incoming_message: dingtalk_stream.ChatbotMessage, callback_data: dict = None):
    """处理回复并更新卡片"""
    # 卡片模板 ID
    card_template_id = os.getenv("CARD_TEMPLATE_ID")  # 从环境变量获取模板ID
    content_key = "content"
    card_data = {content_key: ""}
    
    try:
        card_instance = dingtalk_stream.AICardReplier(
            self.dingtalk_client, incoming_message
        )
        # 先投放卡片
        card_instance_id = await card_instance.async_create_and_deliver_card(
            card_template_id, card_data
        )

        if incoming_message.message_type in ["picture", "richText"]:
            try:
                # 获取图片信息
                if not callback_data:
                    raise ValueError("缺少callback_data")
                    
                robot_code = callback_data.get("robotCode")
                if not robot_code:
                    raise ValueError("未找到robotCode")
                    
                # 处理不同类型的消息内容
                if incoming_message.message_type == "picture":
                    content = callback_data.get("content", {})
                    download_code = content.get("downloadCode")
                    picture_download_code = content.get("pictureDownloadCode")
                else:  # richText
                    rich_text = callback_data.get("content", {}).get("richText", [])
                    # 找到第一个picture类型的元素
                    picture_item = next((item for item in rich_text if item.get("type") == "picture"), None)
                    if not picture_item:
                        raise ValueError("未在richText中找到图片")
                    download_code = picture_item.get("downloadCode")
                    picture_download_code = picture_item.get("pictureDownloadCode")
                    
                logger.info(f"图片消息内容: {content if incoming_message.message_type == 'picture' else picture_item}")
                
                if not download_code and not picture_download_code:
                    raise ValueError("未找到图片下载码")
                    
                # 下载图片
                image_data = await download_image(download_code, self.dingtalk_client, robot_code)
                
                # 定义回调函数用于实时更新卡片
                async def update_card(content: str):
                    await card_instance.async_streaming(
                        card_instance_id,
                        content_key=content_key,
                        content_value=content,
                        append=False,
                        finished=False,
                        failed=False
                    )
                
                # 处理图片
                result = await process_image(image_data, update_card)
                
                # 更新卡片显示最终结果
                await card_instance.async_streaming(
                    card_instance_id,
                    content_key=content_key,
                    content_value=result,
                    append=False,
                    finished=True,
                    failed=False,
                )
                
            except Exception as e:
                logger.exception(f"处理图片消息失败: {str(e)}")
                await card_instance.async_streaming(
                    card_instance_id,
                    content_key=content_key,
                    content_value=f"处理图片失败: {str(e)}",
                    append=False,
                    finished=False,
                    failed=True,
                )
        else:  # 处理文本消息
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


class CardBotHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, logger: logging.Logger = None):
        super(dingtalk_stream.ChatbotHandler, self).__init__()
        if logger:
            self.logger = logger

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        """处理消息回调"""
        incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
        self.logger.info(f"收到消息：{incoming_message}")

        if incoming_message.message_type not in ["text", "picture", "richText"]:
            self.reply_text("俺只看得懂文字和图片喔~", incoming_message)
            return AckMessage.STATUS_OK, "OK"

        # 创建异步任务处理消息
        asyncio.create_task(handle_reply_and_update_card(self, incoming_message, callback.data))
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


def setup_logger():
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter('%(asctime)s %(name)-8s %(levelname)-8s %(message)s [%(filename)s:%(lineno)d]'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


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
