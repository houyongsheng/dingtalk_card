import os
import logging
import asyncio
import argparse
from loguru import logger
from dingtalk_stream import AckMessage
import dingtalk_stream

from typing import Callable
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage


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
    return options


async def call_with_stream(request_content: str, callback: Callable[[str], None]):
    """调用智谱AI并流式更新卡片"""
    try:
        llm = ChatOpenAI(
            model="glm-4-flash",
            temperature=0.7,
            openai_api_key=os.getenv("ZHIPU_API_KEY"),
            openai_api_base="https://open.bigmodel.cn/api/paas/v4/chat/completions",
            streaming=True
        )
        
        full_content = ""
        length = 0
        
        async for chunk in await llm.astream([HumanMessage(content=request_content)]):
            if chunk.content:
                full_content += chunk.content
                full_content_length = len(full_content)
                if full_content_length - length > 20:  # 每累积20个字符更新一次
                    await callback(full_content)
                    logger.info(
                        f"调用流式更新接口更新内容：current_length: {length}, next_length: {full_content_length}"
                    )
                    length = full_content_length
                    
        await callback(full_content)  # 最后一次更新
        logger.info(
            f"Request Content: {request_content}\nFull response: {full_content}\nFull response length: {len(full_content)}"
        )
        return full_content
        
    except Exception as e:
        logger.error(f"调用AI模型失败: {str(e)}")
        raise


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


class CardBotHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, logger: logging.Logger = logger):
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


def main():
    """主函数"""
    # 设置日志
    logger.add(
        "ai_card.log",
        rotation="500 MB",
        encoding="utf-8",
        enqueue=True,
        retention="10 days"
    )
    
    # 加载配置
    options = define_options()

    # 创建客户端
    credential = dingtalk_stream.Credential(options.client_id, options.client_secret)
    client = dingtalk_stream.DingTalkStreamClient(credential)
    
    # 注册回调处理器
    client.register_callback_handler(
        dingtalk_stream.ChatbotMessage.TOPIC, CardBotHandler()
    )
    
    # 启动客户端
    logger.info("Starting stream client...")
    client.start_forever()


if __name__ == "__main__":
    main()
