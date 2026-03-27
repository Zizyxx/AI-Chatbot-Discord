import discord
import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 1. Muat token dari file .env
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not DISCORD_TOKEN or not GEMINI_API_KEY:
    print("ERROR: Pastikan DISCORD_TOKEN dan GEMINI_API_KEY sudah diisi di file .env!")
    exit()

# 2. Konfigurasi AI Gemini
ai_client = genai.Client(api_key=GEMINI_API_KEY)

instruksi_bot = """
Kamu adalah asisten AI di server Discord yang ramah, membantu, dan pintar.
Gunakan bahasa Indonesia yang natural, santai, tapi tetap sopan.
Kamu memiliki ingatan jangka panjang tentang obrolan kita.
PENTING: Setiap pesan dari pengguna akan diawali dengan format "[NamaUser berkata]:". 
Gunakan nama tersebut untuk menyapa mereka secara personal atau mengingat identitas siapa yang sedang berbicara denganmu di obrolan sebelumnya. Jangan mengulangi format "[NamaUser berkata]:" dalam balasanmu.
"""

# 3. Sistem Ingatan Permanen (JSON)
FILE_INGATAN = 'ingatan_bot.json'
MAX_INGATAN = 20 # Batasi jumlah percakapan yang diingat agar tidak boros kuota token AI

def muat_ingatan():
    """Membaca riwayat obrolan dari file JSON."""
    if os.path.exists(FILE_INGATAN):
        with open(FILE_INGATAN, 'r', encoding='utf-8') as file:
            try:
                data = json.load(file)
                # Format ulang data JSON menjadi objek types.Content yang dikenali Gemini
                history = []
                for item in data:
                    history.append(types.Content(
                        role=item['role'],
                        parts=[types.Part.from_text(text=item['text'])]
                    ))
                return history
            except json.JSONDecodeError:
                return []
    return []

def simpan_ingatan(history_objects):
    """Menyimpan riwayat obrolan ke file JSON."""
    data_untuk_disimpan = []
    # Ambil maksimal MAX_INGATAN pesan terakhir agar file tidak terlalu besar
    pesan_terbaru = history_objects[-MAX_INGATAN:] if len(history_objects) > MAX_INGATAN else history_objects
    
    for content in pesan_terbaru:
        # Ekstrak teks dari objek types.Content
        teks = content.parts[0].text if content.parts else ""
        data_untuk_disimpan.append({
            'role': content.role,
            'text': teks
        })
        
    with open(FILE_INGATAN, 'w', encoding='utf-8') as file:
        json.dump(data_untuk_disimpan, file, indent=4, ensure_ascii=False)

# 4. Konfigurasi Bot Discord
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print('-----------------------------------')
    print(f'Bot berhasil online sebagai: {client.user}')
    print(f'Sistem ingatan aktif. Riwayat obrolan akan disimpan di {FILE_INGATAN}')
    print('-----------------------------------')

@client.event
async def on_message(message):
    # Abaikan pesan dari bot itu sendiri
    if message.author == client.user:
        return

    # Bot HANYA merespon jika dia di-tag (mention)
    if client.user.mentioned_in(message):
        
        # Hapus tag bot dari teks pesan
        pesan_user = message.content.replace(f'<@{client.user.id}>', '').strip()

        if not pesan_user:
            await message.reply("Halo! Ada yang bisa aku bantu?")
            return

        # Ambil nama user Discord yang mengirim pesan
        nama_pengirim = message.author.display_name
        
        # Sisipkan nama pengirim ke dalam pesan agar masuk ke ingatan AI
        pesan_dengan_nama = f"[{nama_pengirim} berkata]: {pesan_user}"

        # Tampilkan animasi "bot is typing..."
        async with message.channel.typing():
            try:
                # 1. Muat riwayat obrolan dari file
                history_sebelumnya = muat_ingatan()
                
                # 2. Buat sesi chat dengan AI menggunakan riwayat tersebut
                chat_session = ai_client.chats.create(
                    model="gemini-2.5-flash", 
                    config=types.GenerateContentConfig(
                        system_instruction=instruksi_bot,
                    ),
                    history=history_sebelumnya
                )

                # 3. Kirim pesan yang sudah disisipi nama ke AI
                response = chat_session.send_message(pesan_dengan_nama)
                jawaban_ai = response.text

                # 4. Simpan riwayat obrolan yang baru ke file JSON
                # chat_session.get_history() akan mengembalikan seluruh percakapan (lama + baru)
                simpan_ingatan(chat_session.get_history())

                # 5. Kirim jawaban ke Discord (potong jika kepanjangan)
                if len(jawaban_ai) > 2000:
                    await message.reply(jawaban_ai[:1996] + "...")
                else:
                    await message.reply(jawaban_ai)

            except Exception as e:
                print(f"Terjadi error AI: {e}")
                await message.reply("Waduh, otakku lagi nge-blank nih. Coba tanya lagi ya!")

# Jalankan bot
client.run(DISCORD_TOKEN)