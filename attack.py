# Приложение для защиты комментариев
from telethon import TelegramClient, events, errors
from telethon.tl.functions.messages import GetDiscussionMessageRequest
from telethon.tl.functions.channels import GetFullChannelRequest, JoinChannelRequest
from upstash_redis.asyncio import Redis
import re
import os
import dotenv

dotenv.load_dotenv()
redis = Redis.from_env()

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
client = TelegramClient("anon", api_id, api_hash)

targets = None
channel_name = None
admins = [
    6121153070, # miqqil
    7393231125, # notrevr
    1873913712, # britesh23
    5144214173, # damskiy_ugodnik2014
    5173821719, # FugaBot42_555
    1994833659, # svyatoslav_platonoff
    5009372187, # Dima_Fonov
    6219223020, # @DDD3555
    1672847914, # typoikentrysamper
]

async def link_to_objects(message_link):
    expression = r"((https://)?)t\.me/(?P<username>\w+)/(?P<number>\d+)/?"
    try:
        m = re.match(expression, message_link)
        channel = await client.get_entity(m.group("username"))
        message = await client.get_messages(channel, ids=int(m.group("number")))
        return channel, message
    except AttributeError:
        raise Exception("неправильная ссылка")
    except ValueError:
        raise Exception("пост не найден")

async def award_points(user_id):
    key = f"points.{user_id}"
    await redis.hincrby(key, channel_name, 1)

async def message_handler(event):
    if event.reply_to_msg_id in targets:
        await award_points(event.sender_id)

async def create_message_tracker(battalion_members):
    active_attacks = client.list_event_handlers()[1:]
    if active_attacks:
        raise Exception("уже есть активная атака")
    client.add_event_handler(
        message_handler, 
        events.NewMessage(from_users=battalion_members)
    )

async def delete_message_tracker():
    removed_count = client.remove_event_handler(message_handler)
    if removed_count == 0:
        raise Exception("нет атак")

async def join_to_discussion(channel):
    full_channel = await client(GetFullChannelRequest(channel))
    discussion_chat = await client.get_entity(full_channel.full_chat.linked_chat_id)
    try:
        await client(JoinChannelRequest(discussion_chat))
    except errors.ChannelsTooMuchError, errors.UserAlreadyParticipantError:
        raise Exception("не получилось присоединится к комментариям")

async def set_targets(channel, id_in_channel):
    global targets, channel_name
    channel_name = channel.username
    result = await client(GetDiscussionMessageRequest(channel, id_in_channel))
    targets = [m.id for m in result.messages]

async def start_attack(event, target_link):
    channel, message = await link_to_objects(target_link)
    battalion_members = await client.get_participants(2992401166)
    await join_to_discussion(channel)
    await set_targets(channel, message.id)
    await create_message_tracker(battalion_members)
    await event.reply("✓ комментарии отслеживаются")

async def end_attack(event):
    global targets, channel_name
    await delete_message_tracker()
    targets = channel_name = None
    await event.reply("✓ отслеживание завершено")

async def get_stats(event, username):
    try:
        user = await client.get_entity(username)
    except ValueError:
        raise Exception("пользователь не найден")
    stats = await redis.hgetall(f"points.{user.id}")
    if stats:
        await event.reply(
            "статистика:\n" + "\n".join([
                f"{key} - {value}" for key, value in stats.items()
            ])
        )
    else:
        await event.reply("боец не примал участие в атаках")
        
@client.on(events.NewMessage(pattern=r"\!атака", chats=[3320766140, 2992401166, 6632468692]))
async def command_handler(event):
    args = event.raw_text.split()
    try:
        if len(args) == 3 and args[1] == "начать" and event.sender_id in admins:
            await start_attack(event, args[2])
        elif len(args) == 2 and args[1] == "завершить" and event.sender_id in admins:
            await end_attack(event)
        elif len(args) == 3 and args[1] == "опыт":
            await get_stats(event, args[2])
        else:
            await event.reply("""помощь:
        !атака начать <ссылка>
        !атака завершить
        !атака опыт <пользователь>""")
    except Exception as e:
        await event.reply(f"{e}")

with client:
    client.run_until_disconnected()