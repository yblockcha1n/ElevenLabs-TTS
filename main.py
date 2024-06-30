import discord
from discord import app_commands
import aiohttp
import json
import re

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

try:
    with open("settings/config.json", "r") as f:
        config = json.load(f)
    DISCORD_TOKEN = config["DISCORD_TOKEN"]
    CHUNK_SIZE = config["CHUNK_SIZE"]
    ELEVENLABS_API_KEY = config["ELEVENLABS_API_KEY"]
    ELEVENLABS_VOICE_ID = config["ELEVENLABS_VOICE_ID"]
    THREAD_ID = config["THREAD_ID"]
    OWNER_ID = config["OWNER_ID"]
except FileNotFoundError:
    print("Error: 設定ファイルが存在しません。")
    exit(1)
except json.JSONDecodeError:
    print("Error: 設定ファイルが空白でした。")
    exit(1)
except KeyError as e:
    print(f"Error: Missing key {e} in config.json")
    exit(1)

try:
    with open("settings/fix-reading.json", "r") as f:
        fix_reading_data = json.load(f)
except FileNotFoundError:
    print("Warning: Fixファイルが存在しません。")
    fix_reading_data = {}
    with open("settings/fix-reading.json", "w") as f:
        json.dump(fix_reading_data, f)
except json.JSONDecodeError:
    print("Error!: Fixファイルが空白でした。")
    fix_reading_data = {}
    with open("settings/fix-reading.json", "w") as f:
        json.dump(fix_reading_data, f)

def load_voice_list():
    global voice_list
    try:
        with open("settings/voice-list.json", "r") as f:
            voice_list = json.load(f)
    except FileNotFoundError:
        print("Warning!: VCファイルが存在しません。")
        voice_list = {}
        save_voice_list()
    except json.JSONDecodeError:
        print("Error!: VCファイルが空白でした。")
        voice_list = {}
        save_voice_list()

load_voice_list()
current_voice_id = ELEVENLABS_VOICE_ID

def save_voice_list():
    with open("settings/voice-list.json", "w") as f:
        json.dump(voice_list, f, ensure_ascii=False, indent=2)

@client.event
async def on_ready():
    print(f"Logged in as {client.user.name}")
    await tree.sync()

def create_embed(title, description, color=discord.Color.blue()):
    return discord.Embed(title=title, description=description, color=color)

@tree.command(name="join", description="ボイスチャンネルに参加します")
async def join(interaction: discord.Interaction):
    if interaction.user.voice:
        voice_channel = interaction.user.voice.channel
        await voice_channel.connect()
        embed = create_embed("ボイスチャンネル参加", "ボイスチャンネルに参加しました。")
        await interaction.response.send_message(embed=embed)
    else:
        embed = create_embed("エラー", "ボイスチャンネルに参加していません。", discord.Color.red())
        await interaction.response.send_message(embed=embed)

@tree.command(name="leave", description="ボイスチャンネルから退出します")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        embed = create_embed("ボイスチャンネル退出", "ボイスチャンネルから退出しました。")
        await interaction.response.send_message(embed=embed)
    else:
        embed = create_embed("エラー", "ボイスチャンネルに参加していません。", discord.Color.red())
        await interaction.response.send_message(embed=embed)

@tree.command(name="fix", description="単語の読み方を修正します")
async def fix(interaction: discord.Interaction, original: str, reading: str):
    fix_reading_data[original] = reading
    with open("settings/fix-reading.json", "w") as f:
        json.dump(fix_reading_data, f, ensure_ascii=False)
    embed = create_embed("読み方修正", f"{original} の読み方を {reading} に修正しました。")
    await interaction.response.send_message(embed=embed)

@tree.command(name='sync', description='オーナー専用のコマンド同期')
async def sync(interaction: discord.Interaction):
    if interaction.user.id == OWNER_ID:
        await interaction.response.defer(ephemeral=True)
        try:
            await tree.sync()
            embed = create_embed("コマンド同期", "コマンドツリーが同期されました。")
            await interaction.followup.send(embed=embed)
            print('Command tree synced.')
        except Exception as e:
            embed = create_embed("エラー", f"同期中にエラーが発生しました: {str(e)}", discord.Color.red())
            await interaction.followup.send(embed=embed)
    else:
        embed = create_embed("権限エラー", "このコマンドはオーナーのみが使用できます。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="add-voice", description="新しい音声を登録します")
async def add_voice(interaction: discord.Interaction, name: str, voice_id: str):
    voice_list[name] = voice_id
    save_voice_list()
    embed = create_embed("音声登録", f"音声 '{name}' (ID: {voice_id}) を登録しました。")
    await interaction.response.send_message(embed=embed)

@tree.command(name="change-voice", description="使用する音声を変更します")
async def change_voice(interaction: discord.Interaction):
    global current_voice_id
    
    current_voice_name = "デフォルト"
    for name, voice_id in voice_list.items():
        if voice_id == current_voice_id:
            current_voice_name = name
            break

    choices = [
        discord.SelectOption(label=name, value=name)
        for name in voice_list.keys()
        if voice_list[name] != current_voice_id
    ]
    
    if not choices:
        embed = create_embed("エラー", "変更可能な音声がありません。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    view = discord.ui.View()
    select = discord.ui.Select(placeholder="音声を選択してください", options=choices)

    async def select_callback(interaction: discord.Interaction):
        global current_voice_id
        selected_voice_name = select.values[0]
        current_voice_id = voice_list[selected_voice_name]
        embed = create_embed("音声変更", f"音声を '{selected_voice_name}' に変更しました。")
        await interaction.response.send_message(embed=embed)
        view.stop()

    select.callback = select_callback
    view.add_item(select)

    await interaction.response.send_message(f"現在の音声: {current_voice_name}\n変更する音声を選択してください：", view=view)

@tree.command(name="edit-voice", description="登録済みの音声情報を編集します")
async def edit_voice(interaction: discord.Interaction):
    choices = [discord.SelectOption(label=name, value=name) for name in voice_list.keys()]
    
    if not choices:
        embed = create_embed("エラー", "編集可能な音声がありません。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    view = discord.ui.View()
    select = discord.ui.Select(placeholder="編集する音声を選択してください", options=choices)

    async def select_callback(interaction: discord.Interaction):
        old_name = select.values[0]
        await interaction.response.send_modal(EditVoiceModal(old_name))
        view.stop()

    select.callback = select_callback
    view.add_item(select)

    await interaction.response.send_message("編集する音声を選択してください：", view=view)

class EditVoiceModal(discord.ui.Modal, title="音声情報の編集"):
    def __init__(self, old_name):
        super().__init__()
        self.old_name = old_name
        self.new_name = discord.ui.TextInput(label="新しい名前", placeholder="新しい音声名を入力してください")
        self.new_voice_id = discord.ui.TextInput(label="新しい音声ID", placeholder="新しい音声IDを入力してください")
        self.add_item(self.new_name)
        self.add_item(self.new_voice_id)

    async def on_submit(self, interaction: discord.Interaction):
        del voice_list[self.old_name]
        voice_list[self.new_name.value] = self.new_voice_id.value
        save_voice_list()
        embed = create_embed("音声編集", f"音声 '{self.old_name}' を '{self.new_name.value}' (ID: {self.new_voice_id.value}) に更新しました。")
        await interaction.response.send_message(embed=embed)

@tree.command(name="check-voice", description="現在使用中の音声を確認します")
async def check_voice(interaction: discord.Interaction):
    global current_voice_id
    
    current_voice_name = "不明"
    for name, voice_id in voice_list.items():
        if voice_id == current_voice_id:
            current_voice_name = name
            break
    
    if current_voice_id == ELEVENLABS_VOICE_ID and current_voice_name == "不明":
        current_voice_name = "デフォルト"

    embed = create_embed("現在の音声設定", f"現在使用中の音声: {current_voice_name}")
    
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_connected():
        embed.add_field(name="ステータス", value="ボイスチャンネルに接続中", inline=False)
    else:
        embed.add_field(name="ステータス", value="ボイスチャンネルに未接続", inline=False)

    await interaction.response.send_message(embed=embed)

@tree.command(name="revoke-voice", description="登録済みの音声を削除します")
async def revoke_voice(interaction: discord.Interaction):
    global current_voice_id
    
    choices = [
        discord.SelectOption(label=name, value=name)
        for name, voice_id in voice_list.items()
        if voice_id != current_voice_id
    ]
    
    if not choices:
        embed = create_embed("エラー", "削除可能な音声がありません。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    view = discord.ui.View()
    select = discord.ui.Select(placeholder="削除する音声を選択してください", options=choices)

    async def select_callback(interaction: discord.Interaction):
        name = select.values[0]
        del voice_list[name]
        save_voice_list()
        embed = create_embed("音声削除", f"音声 '{name}' を削除しました。")
        await interaction.response.send_message(embed=embed)
        view.stop()

    select.callback = select_callback
    view.add_item(select)

    await interaction.response.send_message("削除する音声を選択してください：", view=view)

@tree.command(name="list-voices", description="登録済みの音声一覧を表示します")
async def list_voices(interaction: discord.Interaction):
    load_voice_list()
    if voice_list:
        voice_info = "\n".join([f"{name}: {voice_id}" for name, voice_id in voice_list.items()])
        embed = create_embed("登録済み音声一覧", voice_info)
    else:
        embed = create_embed("登録済み音声一覧", "登録済みの音声はありません。")
    await interaction.response.send_message(embed=embed)

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == THREAD_ID:
        await process_message(message)

async def process_message(message):
    if message.attachments:
        return

    text = message.content

    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    text = url_pattern.sub('', text)

    for mention in message.mentions:
        text = text.replace(f'<@!{mention.id}>', '')
        text = text.replace(f'<@{mention.id}>', '')

    if not text.strip():
        return

    for original, reading in fix_reading_data.items():
        text = re.sub(original, reading, text)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{current_voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as response:
            if response.status == 200:
                with open('output.mp3', 'wb') as f:
                    while True:
                        chunk = await response.content.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)

                voice_client = message.guild.voice_client
                if voice_client:
                    audio_source = discord.FFmpegPCMAudio('output.mp3')
                    voice_client.play(audio_source, after=lambda e: print(f'Player error: {e}') if e else None)
            else:
                error_message = await response.text()
                print(f"Error from ElevenLabs API: {error_message}")
                await message.channel.send("音声の生成中にエラーが発生しました。")

client.run(DISCORD_TOKEN)
