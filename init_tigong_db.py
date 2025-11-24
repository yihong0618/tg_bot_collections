#!/usr/bin/env python3
"""初始化提肛提醒数据库"""

from handlers.summary.messages import MessageStore


def main():
    print("正在初始化提肛提醒数据库...")

    # 初始化数据库
    store = MessageStore("data/messages.db")

    print("✅ 数据库初始化完成！")
    print("\n数据库位置: data/messages.db")
    print("\n已创建的表:")
    print("  - messages: 存储聊天消息")
    print("  - tigong_alerts: 存储提肛提醒用户队列")
    print("\n可用的命令:")
    print("  /alert_me - 加入提肛提醒队列")
    print("  /confirm - 确认完成今日提肛")
    print("  /standup - 手动发送提肛提醒")
    print("\n功能:")
    print("  - 每天北京时间 8:00-18:00，每2小时自动提醒")
    print("  - 每达到100条消息的整数倍时自动提醒")
    print("  - 提醒会 @ 所有未确认的用户")


if __name__ == "__main__":
    main()
