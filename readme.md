# 打字机效果流式 AI 卡片

更新于 2024-10-29以开发一个对接了通义千问大模型的 AI 机器人为例，学习如何通过发送和流式更新 AI 卡片来实现打字机效果的流式 AI 卡片。

## 前提条件

1. 
完成[创建企业内部应用机器人](/document/orgapp/the-creation-and-installation-of-the-application-robot-in-the#)的流程。

> 机器人接收消息模式选择 Stream 模式。

2. 
完成[添加企业机器人入群](/document/orgapp/add-enterprise-robot-to-group#)的流程。

3. 
申请权限：权限点 Code：`Card.Streaming.Write`。

![](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/9906372171/p785445.png)

## 阶段一：明确开发需求

正式开发 AI 机器人前，你需要明确本教程实现的具体场景及需要使用哪些能力。

- 
业务场景：机器人在回复用户消息时根据用户的输入调用大模型后回复一张流式更新内容的 AI 卡片。

- 
交互形态：机器人

- 
开发目标：开发一个 AI 机器人，他可以在收到用户在私聊、群聊中发送给机器人的消息，并根据收到的消息调用大模型获取答复，回复一张 AI 卡片并流式更新卡片内容（打字机效果）。

## 阶段二：搭建卡片模板

### 1. 登录卡片平台

你可以通过以下任一方式进入卡片平台：

- 
单击[这里](https://open-dev.dingtalk.com/fe/card#/)进入卡片平台

- 
登录[开发者后台](https://open-dev.dingtalk.com/#/)，单击顶部导航栏开放能力 > 卡片平台。

### 2. 新建卡片模板

1. 
在卡片平台页面，单击侧边导航栏新建模板。

2. 
配置卡片信息：

配置项

说明

模板名称

本示例填写：打字机效果 AI 卡片。

卡片类型

选择消息卡片。

卡片模板场景

选择 AI 卡片。

关联应用

选择前提条件创建机器人的所属应用。

配置完成后，单击创建，进入卡片模板搭建页面。

![](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/3421569271/p862299.png)

### 3. 配置模板内容

AI 卡片预置相关参数，你需要关注输入中的 Markdown 组件是否开启了流式组件开关和绑定的 markdown 变量。

![](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/3421569271/p862300.png)

配置完成后，保存模板。

## 阶段三：开发代码

本示例使用 DashScope SDK 接入通义千问大模型（有免费额度），具体 SDK 安装和 API-KEY 设置参考通义千问 [API详情](https://help.aliyun.com/zh/dashscope/developer-reference/api-details) 文档：

1. 
使用通义千问大模型前需要先将 API KEY 设置到环境变量 DASHSCOPE_API_KEY 当中：

环境

 临时设置环境变量

Linux/Mac

export DASHSCOPE_API_KEY=your-api-key

Windows

set DASHSCOPE_API_KEY=your-api-key

示例代码：

语言

说明

Python

1. 
以下示例使用 Stream SDK [dingtalk-stream-sdk-python](https://github.com/open-dingtalk/dingtalk-stream-sdk-python) 的 Python 代码示例，需要先安装依赖：`pip install dingtalk_stream loguru`。

2. 
创建`ai_card.py`文件，文件内容如下 Python 部分。

Java

创建 AICardDemo.java文件，内容如下的 Java 部分。

Python

1

2

3

4

5

6

7

8

9

10

11

12

13

14

15

16

17

18

19

20

21

import os

import logging

import asyncio

import argparse

from loguru import logger

from dingtalk_stream import AckMessage

import dingtalk_stream

from http import HTTPStatus

from dashscope import Generation

from typing import Callable

def define_options():

    parser = argparse.ArgumentParser()

    parser.add_argument(

        "--client_id",

        dest="client_id",

        default=os.getenv("DINGTALK_APP_CLIENT_ID"),

        help="app_key or suite_key from https://open-dev.digntalk.com",

Enter to Rename, ⇧Enter to Preview

Java

1

import java.util.Collections;

Enter to Rename, ⇧Enter to Preview

### 代码说明

语言

说明

Python

在上面的代码中，实现了一个调用通义千问大模型流式获取答复的函数`call_with_stream`，Stream 服务注册了机器人接收消息的回调函数 `CardBotHandler`，机器人在收到消息后会将该消息文本传入函数 `call_with_stream` 并传入一个 callback 函数，传入的 callback 函数会对通义千问返回的拼起来后的流式答复文本传入 AI 卡片流式更新 接口对卡片流式变量 content 进行流式更新。最终在通义千问返回所有答复文本后将卡片状态置为完成状态，如果执行过程代码报错则将卡片状态置为失败状态。

### 启动示例 demo

Python

1

python ai_card.py --client_id="your-client-id" --client_secret="your-client-secret"

Enter to Rename, ⇧Enter to Preview

Java

1

mvn clean package

Enter to Rename, ⇧Enter to Preview

参数

说明

your-client-id

应用 [Client ID](/document/orgapp/basic-concepts-beta#title-g14-h6j-ff5)。

your-client-secret

应用 [Client Secret](/document/orgapp/basic-concepts-beta#title-g14-h6j-ff5)。

## 效果演示

## 相关内容

- 
[AI卡片流式更新](/document/app/api-streamingupdate#)

如果你需要了解更多互动卡片示例，请参考[互动卡片示例中心](https://github.com/open-dingtalk/dingtalk-card-examples)