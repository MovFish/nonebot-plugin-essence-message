from asyncio import gather
from typing import Union

from nonebot import get_plugin_config, on_type
from nonebot.adapters.onebot.v11 import (
    NoticeEvent,
    MessageSegment,
    GroupMessageEvent,
)
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import GROUP_ADMIN, GROUP_OWNER
from nonebot.adapters.onebot.v11.bot import Bot
from nonebot.plugin import PluginMetadata
from nonebot import require


require("nonebot_plugin_alconna")
from arclet.alconna import Alconna, Args, Subcommand
from nonebot_plugin_alconna import AlconnaMatch, Match, Query, on_alconna
from .dataset import DatabaseHandler
from .config import config
from .Helper import (
    ReactGoodNoticeEvent,
    EssenceEvent,
    GoodCounter,
    ReactWhaleNoticeEvent,
    SaveMsg,
    RateLimiter,
    SendMsg,
    SendMsgData,
    NoticePermission,
    get_name,
    fetchpic,
    whale_essnece_set,
)

__plugin_meta__ = PluginMetadata(
    name="精华消息管理",
    description="用于整理精华消息",
    usage=("自动存储精华消息备份并提供一些查询功能"),
    type="application",
    homepage="https://github.com/BEISNWKZNAN/nonebot-plugin-essence-message",
    config=config,
    supported_adapters={"~onebot.v11"},
)


def trigger_rule(event: Union[GroupMessageEvent, NoticeEvent]) -> bool:
    return (int(event.group_id) in cfg.essence_enable_groups) or (str(event.group_id) in cfg.essence_enable_groups) or ("all" in cfg.essence_enable_groups)  # type: ignore


cfg = get_plugin_config(config)
db = DatabaseHandler(str(config.db()))
goodcount = GoodCounter(config.cache() / "good_cache.json", cfg.good_bound)
ratelimiter = RateLimiter(cfg.essence_random_limit, 43200, cfg.essence_random_CD)


whale_essnece = on_type(
    (NoticeEvent,),
    rule=trigger_rule,
    priority=9,
    permission=NoticePermission,
    block=False,
)
essence_set = on_type((NoticeEvent,), rule=trigger_rule, priority=10, block=False)
trigood = on_type((NoticeEvent,), rule=trigger_rule, priority=11, block=False)

essence_cmd = on_alconna(
    Alconna(
        "essence",
        Subcommand("help"),
        Subcommand("random"),
        Subcommand("search", Args["keyword", str]),
        Subcommand("rank", Args["type", str]),
    ),
    rule=trigger_rule,
    priority=5,
    block=False,
)

essence_cmd_admin = on_alconna(
    Alconna(
        "essence",
        Subcommand("cancel"),
        Subcommand("fetchall"),
        Subcommand("export"),
        Subcommand("saveall"),
        Subcommand("clean"),
    ),
    rule=trigger_rule,
    priority=6,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
    block=False,
)
cleanning_flag = False


# 10024
@whale_essnece.handle()
async def _(event: NoticeEvent, bot: Bot):
    try:
        event = ReactWhaleNoticeEvent(**event.model_dump())
    except:
        await essence_set.finish()
    if (
        int(event.group_id) in cfg.whale_essnece_enable_groups
        or str(event.group_id) in cfg.whale_essnece_enable_groups
    ):
        if event.sub_type == "add":
            try:
                msg = await bot.get_msg(message_id=event.message_id)
            except:
                await whale_essnece.finish()
            await SaveMsg(
                db,
                msg,
                bot,
                event.time,
                event.group_id,
                msg["sender"]["user_id"],
                event.operator_id,
            ).add_to_dataset()
            await bot.set_group_reaction(
                group_id=event.group_id,
                message_id=event.message_id,
                code="10024",
                is_add=True,
            )
        else:
            try:
                msg = await bot.get_msg(message_id=event.message_id)
            except:
                await whale_essnece.finish()
            await SaveMsg(
                db,
                msg,
                bot,
                event.time,
                event.group_id,
                msg["sender"]["user_id"],
                event.operator_id,
            ).del_from_dataset()
            await bot.set_group_reaction(
                group_id=event.group_id,
                message_id=event.message_id,
                code="10024",
                is_add=False,
            )
    else:
        await essence_set.finish()


@essence_set.handle()
async def ___(event: NoticeEvent, bot: Bot):
    try:
        event = EssenceEvent(**event.model_dump())
    except:
        await essence_set.finish()
    try:
        msg = await bot.get_msg(message_id=event.message_id)
    except:
        if event.sub_type == "add":
            essencelist = await bot.get_essence_msg_list(group_id=event.group_id)
            for essence in essencelist:
                if essence["message_id"] == event.message_id:
                    msg = {"message": essence["content"]}
                    break
    if event.sub_type == "add":
        await SaveMsg(
            db, msg, bot, event.time, event.group_id, event.sender_id, event.operator_id
        ).add_to_dataset()
    elif event.sub_type == "delete":
        global cleanning_flag
        if cleanning_flag:
            await essence_cmd.finish()
        await SaveMsg(
            db, msg, bot, event.time, event.group_id, event.sender_id, event.operator_id
        ).del_from_dataset()
    await essence_cmd.finish()


@trigood.handle()
async def __(event: NoticeEvent, bot: Bot):
    try:
        event = ReactGoodNoticeEvent(**event.model_dump())
    except:
        await essence_set.finish()
    if (
        int(event.group_id) in cfg.good_essence_enable_groups
        or str(event.group_id) in cfg.good_essence_enable_groups
    ):
        msg_session = f"{event.group_id}_{event.message_id}"
        if isinstance(event.count, int):
            oldcount: int = goodcount.get(msg_session)
            goodcount.modify(msg_session, event.count)
            if oldcount <= event.count and goodcount.ToogoodToessence(msg_session):
                await whale_essnece_set(
                    int(event.group_id) in cfg.whale_essnece_enable_groups
                    or str(event.group_id) in cfg.whale_essnece_enable_groups,
                    event.group_id,
                    event.message_id,
                    True,
                    bot,
                )
            if oldcount > event.count and not goodcount.ToogoodToessence(msg_session):
                try:
                    msg = await bot.get_msg(message_id=event.message_id)
                    sender = msg["sender"]["user_id"]
                except:
                    essencelist = await bot.get_essence_msg_list(
                        group_id=event.group_id
                    )
                    for essence in essencelist:
                        if essence["message_id"] == event.message_id:
                            msg = {"message": essence["content"]}
                            break
                await SaveMsg(
                    db, msg, bot, event.time, event.group_id, sender, int(bot.self_id)
                ).del_from_dataset()
                try:
                    await whale_essnece_set(
                        int(event.group_id) in cfg.whale_essnece_enable_groups
                        or str(event.group_id) in cfg.whale_essnece_enable_groups,
                        event.group_id,
                        event.message_id,
                        False,
                        bot,
                    )
                except:
                    await trigood.finish()
        else:
            if event.sub_type == "add":
                goodcount.add(msg_session)
                if goodcount.ToogoodToessence(msg_session):
                    await whale_essnece_set(
                        int(event.group_id) in cfg.whale_essnece_enable_groups
                        or str(event.group_id) in cfg.whale_essnece_enable_groups,
                        event.group_id,
                        event.message_id,
                        True,
                        bot,
                    )
            elif event.sub_type == "remove":
                goodcount.remove(msg_session)
                if not goodcount.ToogoodToessence(msg_session):
                    try:
                        msg = await bot.get_msg(message_id=event.message_id)
                        sender = msg["sender"]["user_id"]
                    except:
                        essencelist = await bot.get_essence_msg_list(
                            group_id=event.group_id
                        )
                        for essence in essencelist:
                            if essence["message_id"] == event.message_id:
                                msg = {"message": essence["content"]}
                                break
                    await SaveMsg(
                        db,
                        msg,
                        bot,
                        event.time,
                        event.group_id,
                        sender,
                        int(bot.self_id),
                    ).del_from_dataset()
                    await whale_essnece_set(
                        int(event.group_id) in cfg.whale_essnece_enable_groups
                        or str(event.group_id) in cfg.whale_essnece_enable_groups,
                        event.group_id,
                        event.message_id,
                        False,
                        bot,
                    )


@essence_cmd.assign("help")
async def help_cmd():
    await essence_cmd.finish(
        "使用说明:\n"
        + "essence help - 显示此帮助信息\n"
        + "essence random - 随机发送一条精华消息\n"
        + "essence rank sender - 显示发送者精华消息排行榜\n"
        + "essence rank operator - 显示管理员设精数量精华消息排行榜\n"
        + "essence fetchall - 获取群内所有精华消息\n"
        + "essence export - 导出精华消息\n"
        + "essence saveall - 将群内所有精华消息图片存至本地\n"
        + "essence clean - 删除群里所有精华消息(数据库中保留)"
    )


@essence_cmd.assign("random")
async def random_cmd(event: GroupMessageEvent, bot: Bot):
    if ratelimiter.reach_limit(event.get_session_id()):
        await essence_cmd.finish("过量抽精华有害身心健康")
    else:
        msg = await db.random_essence(event.group_id)
        if msg == None:
            await essence_cmd.finish(
                MessageSegment.text(
                    "目前数据库里没有精华消息，可以使用essence fetchall抓取群里的精华消息"
                )
            )
        else:
            rand = SendMsg(SendMsgData(msg[4], msg[5]), db, bot, msg[1])
            random = (
                MessageSegment.text(f"{await rand.get_name(msg[2])}:")
                + await rand.get_msg()
            )
            random.reduce()
            await essence_cmd.finish(random)


@essence_cmd.assign("search")
async def search_cmd(
    event: GroupMessageEvent, bot: Bot, keyword: Match[str] = AlconnaMatch("keyword")
):
    msg = await db.search_entries(event.group_id, keyword.result)
    if not any(msg):
        await essence_cmd.finish("没有找到")
    sender_ids = [sender_id for _, _, sender_id, _, _, data in msg]
    msg_data = [data for _, _, _, _, _, data in msg]
    names = await gather(
        *[get_name(db, bot, event.group_id, sender_id) for sender_id in sender_ids]
    )
    result = [f"{name}: {data}" for name, data in zip(names, msg_data)]
    await essence_cmd.finish(MessageSegment.text("\n".join(result)))


@essence_cmd.assign("rank")
async def rank_cmd(
    event: GroupMessageEvent, bot: Bot, type: Query[str] = Query("~type")
):
    if type.result == "sender":
        rank = await db.sender_rank(event.group_id, event.user_id)
    elif type.result == "operator":
        rank = await db.operator_rank(event.group_id, event.user_id)

    names = await gather(*[get_name(db, bot, event.group_id, id) for id, _, _ in rank])
    result = [
        f"第{r}名: {name}, {count}条精华消息"
        for name, (_, count, r) in zip(names, rank)
    ]
    await essence_cmd.finish(MessageSegment.text("\n".join(result)))


@essence_cmd_admin.assign("fetchall")
async def fetchall_cmd(event: GroupMessageEvent, bot: Bot):
    essencelist = await bot.get_essence_msg_list(group_id=event.group_id)
    savecount = 0
    for essence in essencelist:
        msg = {"message": essence["content"]}
        savecount += int(
            await SaveMsg(
                db,
                msg,
                bot,
                event.time,
                event.group_id,
                essence["sender_id"],
                essence["operator_id"],
            ).add_to_dataset()
        )
    await essence_cmd.finish(f"成功保存 {savecount}/{len(essencelist)} 条精华消息")


@essence_cmd_admin.assign(
    "saveall",
)
async def sevaall_cmd(event: GroupMessageEvent, bot: Bot):
    essencelist = await bot.get_essence_msg_list(group_id=event.group_id)
    savecount = await fetchpic(essencelist, config.img())
    await essence_cmd.finish(
        f"总共找到 {len(essencelist)} 条精华消息，成功保存 {savecount} 张图片"
    )


@essence_cmd_admin.assign(
    "export",
)
async def export_cmd(event: GroupMessageEvent, bot: Bot):
    path = await db.export_group_data(event.group_id)
    await bot.upload_group_file(group_id=event.group_id, file=path, name="essence.db")
    await essence_cmd.finish(f"请检查群文件")


@essence_cmd_admin.assign(
    "clean",
)
async def clean_cmd(event: GroupMessageEvent, bot: Bot):
    global cleanning_flag
    essencelist = await bot.get_essence_msg_list(group_id=event.group_id)
    await essence_cmd.send("开始抓取目前精华消息")
    savecount = 0
    for essence in essencelist:
        msg = {"message": essence["content"]}
        savecount += int(
            await SaveMsg(
                db,
                msg,
                bot,
                event.time,
                event.group_id,
                essence["sender_id"],
                essence["operator_id"],
            ).add_to_dataset()
        )
    await essence_cmd.send("开始清理")
    cleanning_flag = True
    delcount = 0
    for essence in essencelist:
        try:
            await bot.delete_essence_msg(message_id=essence["message_id"])
            delcount += 1
        except Exception:
            continue
    cleanning_flag = False
    await essence_cmd.finish(f"成功删除 {delcount}/{len(essencelist)} 条精华消息")
