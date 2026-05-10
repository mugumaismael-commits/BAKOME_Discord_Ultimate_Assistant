#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ██████╗  █████╗ ██╗  ██╗ ██████╗ ███╗   ███╗███████╗                        ║
║   ██╔══██╗██╔══██╗██║ ██╔╝██╔═══██╗████╗ ████║██╔════╝                        ║
║   ██████╔╝███████║█████╔╝ ██║   ██║██╔████╔██║█████╗                          ║
║   ██╔══██╗██╔══██║██╔═██╗ ██║   ██║██║╚██╔╝██║██╔══╝                          ║
║   ██████╔╝██║  ██║██║  ██╗╚██████╔╝██║ ╚═╝ ██║███████╗                        ║
║   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝                        ║
║                                                                               ║
║                    BAKOME DISCORD ULTIMATE ASSISTANT v3.0                     ║
║              IA locale · Modération · Reddit Monitor · Trading               ║
║                50+ langues · Tickets · Reconnaissance membres                 ║
║                      1800+ lignes · Prêt pour sponsors                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import aiohttp
import aiosqlite
import asyncpraw
import discord
import json
import logging
import os
import re
import sys
import time
import psutil
import yfinance as yf
import ccxt
import feedparser
import langdetect
import sqlite3

from datetime import datetime, timedelta
from collections import defaultdict, deque
from discord.ext import commands, tasks
from discord import app_commands
from googletrans import Translator
from typing import Optional, List, Dict, Any, Tuple

# ============================================================================
# CONFIGURATION - À MODIFIER AVEC TES VALEURS
# ============================================================================

TOKEN = "TON_DISCORD_TOKEN_ICI"
PREFIX = "!"
OWNER_ID = 1234567890  # Remplace par ton ID Discord personnel

# Reddit API
REDDIT_CLIENT_ID = "TON_REDDIT_CLIENT_ID"
REDDIT_CLIENT_SECRET = "TON_REDDIT_CLIENT_SECRET"
REDDIT_USER_AGENT = "BAKOME_Ultimate_Bot/3.0 (by u/BAKOME-Hub)"

# Ollama (IA locale)
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:3b"  # Ou mistral, phi, etc.

# Canaux et catégories (à remplacer par les IDs réels)
LOG_CHANNEL_ID = 0
TICKET_CATEGORY_ID = 0
WELCOME_CHANNEL_ID = 0
RULES_CHANNEL_ID = 0

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler("bakome_discord.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("BAKOME_Ultimate_Bot")

# ============================================================================
# CONSTANTES
# ============================================================================

# Langues supportées (50+)
SUPPORTED_LANGUAGES = {
    'fr': 'Français', 'en': 'English', 'es': 'Español', 'de': 'Deutsch',
    'it': 'Italiano', 'pt': 'Português', 'nl': 'Nederlands', 'pl': 'Polski',
    'ru': 'Русский', 'uk': 'Українська', 'tr': 'Türkçe', 'el': 'Ελληνικά',
    'cs': 'Čeština', 'sv': 'Svenska', 'da': 'Dansk', 'fi': 'Suomi',
    'no': 'Norsk', 'hu': 'Magyar', 'ro': 'Română', 'bg': 'Български',
    'sr': 'Српски', 'hr': 'Hrvatski', 'sk': 'Slovenčina', 'sl': 'Slovenščina',
    'et': 'Eesti', 'lv': 'Latviešu', 'lt': 'Lietuvių', 'zh-cn': '中文(简体)',
    'zh-tw': '中文(繁體)', 'ja': '日本語', 'ko': '한국어', 'hi': 'हिन्दी',
    'bn': 'বাংলা', 'ur': 'اردو', 'te': 'తెలుగు', 'ta': 'தமிழ்',
    'mr': 'मराठी', 'ne': 'नेपाली', 'th': 'ไทย', 'vi': 'Tiếng Việt',
    'id': 'Bahasa Indonesia', 'ms': 'Bahasa Melayu', 'fil': 'Filipino',
    'km': 'ខ្មែរ', 'lo': 'ລາວ', 'my': 'မြန်မာ', 'mn': 'Монгол',
    'ka': 'ქართული', 'hy': 'Հայերեն', 'az': 'Azərbaycanca', 'kk': 'Қазақша',
    'uz': 'Oʻzbekcha', 'ar': 'العربية', 'sw': 'Kiswahili', 'ha': 'Hausa',
    'yo': 'Yorùbá', 'ig': 'Igbo', 'am': 'አማርኛ', 'so': 'Soomaali',
    'mg': 'Malagasy', 'st': 'Sesotho', 'zu': 'Zulu', 'xh': 'isiXhosa',
    'mi': 'Māori', 'haw': 'Hawaiʻi', 'fj': 'Vosa Vakaviti', 'iu': 'ᐃᓄᒃᑎᑐᑦ',
    'kl': 'Kalaallisut'
}

# Mots-clés Reddit
REDDIT_SUBREDDITS = ["opensource", "LocalLLaMA", "SideProject", "startups", "SaaS"]
REDDIT_KEYWORDS = ["sponsor", "grant", "funding", "bounty", "open source", "donate"]

# Limites et sécurité
MAX_COMMANDS_PER_MINUTE = 5
MAX_MESSAGES_PER_MINUTE = 20
AI_MEMORY_LIMIT = 20

# ============================================================================
# BASE DE DONNÉES SQLITE (mémoire, tickets, logs, niveaux)
# ============================================================================

class DatabaseManager:
    def __init__(self, db_path="database/bakome_memory.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Mémoire conversationnelle
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    language TEXT DEFAULT 'en',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Tickets de support
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    status TEXT DEFAULT 'open',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Logs de modération
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mod_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    admin_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Niveaux / XP
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS levels (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    last_message DATETIME
                )
            """)
            # Commandes tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS command_stats (
                    command_name TEXT PRIMARY KEY,
                    usage_count INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def add_chat_history(self, user_id, username, role, content, language='en'):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ai_memory (user_id, username, role, content, language) VALUES (?, ?, ?, ?, ?)",
                (str(user_id), username, role, content, language)
            )
            conn.commit()

    def get_chat_history(self, user_id, limit=10):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM ai_memory WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                (str(user_id), limit)
            )
            rows = cursor.fetchall()
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def clear_chat_history(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ai_memory WHERE user_id = ?", (str(user_id),))
            conn.commit()

    def add_ticket(self, ticket_id, user_id, channel_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tickets (ticket_id, user_id, channel_id, status) VALUES (?, ?, ?, ?)",
                (ticket_id, str(user_id), str(channel_id), 'open')
            )
            conn.commit()

    def close_ticket(self, ticket_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tickets SET status = 'closed' WHERE ticket_id = ?", (ticket_id,))
            conn.commit()

    def add_xp(self, user_id, username, xp_amount=10):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO levels (user_id, username, xp, level, last_message) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET xp = xp + ?, last_message = ?",
                (str(user_id), username, xp_amount, 1, datetime.now(), xp_amount, datetime.now())
            )
            # Calcul du niveau (100 XP par niveau)
            cursor.execute("SELECT xp FROM levels WHERE user_id = ?", (str(user_id),))
            row = cursor.fetchone()
            if row:
                new_level = 1 + (row[0] // 100)
                cursor.execute("UPDATE levels SET level = ? WHERE user_id = ?", (new_level, str(user_id)))
            conn.commit()

    def get_level(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT xp, level FROM levels WHERE user_id = ?", (str(user_id),))
            row = cursor.fetchone()
            return row if row else (0, 1)

    def log_command(self, command_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO command_stats (command_name, usage_count) VALUES (?, 1) "
                "ON CONFLICT(command_name) DO UPDATE SET usage_count = usage_count + 1",
                (command_name,)
            )
            conn.commit()

    def get_command_stats(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT command_name, usage_count FROM command_stats ORDER BY usage_count DESC LIMIT 10")
            return cursor.fetchall()

    def log_mod_action(self, guild_id, admin_id, target_id, action, reason):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO mod_logs (guild_id, admin_id, target_id, action, reason) VALUES (?, ?, ?, ?, ?)",
                (str(guild_id), str(admin_id), str(target_id), action, reason)
            )
            conn.commit()

db = DatabaseManager()

# ============================================================================
# CLIENTS API
# ============================================================================

reddit_client = None
translator = Translator()
exchange = ccxt.binance()

# ============================================================================
# BOT PRINCIPAL
# ============================================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.message_content = True

class BakomeUltimateBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or(PREFIX),
            intents=intents,
            help_command=None
        )
        self.start_time = datetime.now()
        self.command_cooldown = defaultdict(list)

    async def setup_hook(self):
        logger.info("Initialisation du bot...")
        # Initialisation Reddit
        global reddit_client
        if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET:
            reddit_client = asyncpraw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                user_agent=REDDIT_USER_AGENT
            )
            logger.info("Reddit client initialisé")
        # Chargement des cogs (modules)
        await self.load_extension("cogs.ai")
        await self.load_extension("cogs.reddit")
        await self.load_extension("cogs.trading")
        await self.load_extension("cogs.tickets")
        await self.load_extension("cogs.moderation")
        await self.load_extension("cogs.utils")
        await self.load_extension("cogs.devtools")
        logger.info("Tous les cogs chargés")
        # Synchronisation des commandes slash
        await self.tree.sync()
        logger.info("Commandes slash synchronisées")

    async def on_ready(self):
        logger.info(f"Connecté en tant que {self.user} (ID: {self.user.id})")
        logger.info(f"Présent sur {len(self.guilds)} serveurs")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{PREFIX}help | BAKOME"))

    async def on_message(self, message):
        if message.author.bot:
            return
        # Anti-spam
        now = datetime.now()
        user_history = self.command_cooldown[message.author.id]
        user_history = [t for t in user_history if (now - t).total_seconds() < 60]
        if len(user_history) >= MAX_MESSAGES_PER_MINUTE:
            await message.channel.send(f"⚠️ {message.author.mention}, ralentissez !", delete_after=5)
            return
        self.command_cooldown[message.author.id] = user_history + [now]
        # Ajout XP
        await db.add_xp(message.author.id, str(message.author), 5)
        # Sauvegarde mémoire pour IA
        try:
            lang = langdetect.detect(message.content)
        except:
            lang = "en"
        db.add_chat_history(message.author.id, str(message.author), "user", message.content, lang)
        # Réponse IA si mentionné
        if self.user in message.mentions:
            async with message.channel.typing():
                memory = db.get_chat_history(message.author.id, AI_MEMORY_LIMIT)
                response = await self.get_ai_response(message.content, memory, lang)
                await message.reply(response[:1900])
        await self.process_commands(message)

    async def get_ai_response(self, prompt, memory, lang):
        # Appel à Ollama local
        try:
            async with aiohttp.ClientSession() as session:
                context = "\n".join([f"{m['role']}: {m['content']}" for m in memory[-5:]])
                full_prompt = f"Previous conversation:\n{context}\n\nUser ({lang}): {prompt}\nAssistant:"
                async with session.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": OLLAMA_MODEL, "prompt": full_prompt, "stream": False, "temperature": 0.7}
                ) as resp:
                    data = await resp.json()
                    response = data.get("response", "Je n'ai pas pu générer de réponse.")
                    return response
        except:
            return "⚠️ L'IA locale n'est pas disponible. Vérifiez qu'Ollama est lancé (`ollama serve`)."

bot = BakomeUltimateBot()

# ============================================================================
# COG: IA (INTELLIGENCE ARTIFICIELLE)
# ============================================================================

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ask", description="Pose une question à l'IA locale")
    async def ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        memory = db.get_chat_history(interaction.user.id, AI_MEMORY_LIMIT)
        response = await bot.get_ai_response(question, memory, "en")
        embed = discord.Embed(title="🤖 IA Response", description=response[:1900], color=discord.Color.green())
        embed.set_footer(text="IA locale via Ollama | 100% privé")
        await interaction.followup.send(embed=embed)
        db.add_chat_history(interaction.user.id, str(interaction.user), "assistant", response[:500])

    @app_commands.command(name="clear_memory", description="Efface ton historique de conversation avec l'IA")
    async def clear_memory(self, interaction: discord.Interaction):
        db.clear_chat_history(interaction.user.id)
        await interaction.response.send_message("🧹 Ton historique de conversation a été effacé.", ephemeral=True)

    @app_commands.command(name="languages", description="Affiche les langues supportées par le bot")
    async def languages(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🌍 Langues supportées", color=discord.Color.blue())
        langs = "\n".join([f"• {name} (`{code}`)" for code, name in list(SUPPORTED_LANGUAGES.items())[:25]])
        embed.description = f"{langs}\n\n... et 25 autres langues."
        await interaction.response.send_message(embed=embed)

# ============================================================================
# COG: REDDIT MONITOR
# ============================================================================

class RedditCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sent_posts = set()
        self.reddit_monitor.start()

    def cog_unload(self):
        self.reddit_monitor.cancel()

    @tasks.loop(minutes=10)
    async def reddit_monitor(self):
        if not reddit_client:
            return
        channel = self.bot.get_channel(LOG_CHANNEL_ID) if LOG_CHANNEL_ID else None
        for sub_name in REDDIT_SUBREDDITS:
            try:
                subreddit = await reddit_client.subreddit(sub_name)
                async for submission in subreddit.new(limit=5):
                    if submission.id in self.sent_posts:
                        continue
                    title_lower = submission.title.lower()
                    if any(kw in title_lower for kw in REDDIT_KEYWORDS):
                        msg = f"📢 **Nouveau post intéressant sur r/{sub_name}**\n**{submission.title}**\n{submission.url}"
                        if channel:
                            await channel.send(msg)
                        self.sent_posts.add(submission.id)
            except Exception as e:
                logger.error(f"Erreur Reddit: {e}")

    @reddit_monitor.before_loop
    async def before_monitor(self):
        await self.bot.wait_until_ready()

# ============================================================================
# COG: TRADING (CRYPTO, FOREX)
# ============================================================================

class TradingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="crypto", description="Prix des cryptomonnaies (BTC, ETH, BNB, etc.)")
    async def crypto(self, interaction: discord.Interaction, symbol: str = "BTC"):
        try:
            ticker = exchange.fetch_ticker(f"{symbol.upper()}/USDT")
            price = ticker['last']
            change = ticker.get('percentage', 0)
            emoji = "🟢" if change >= 0 else "🔴"
            embed = discord.Embed(title=f"💰 {symbol.upper()}/USDT", description=f"{emoji} ${price:,.2f} ({change:+.2f}%)", color=discord.Color.gold())
            await interaction.response.send_message(embed=embed)
        except:
            await interaction.response.send_message(f"❌ Impossible de récupérer le prix de {symbol}.", ephemeral=True)

    @app_commands.command(name="forex", description="Taux de change Forex (EUR/USD, GBP/USD, etc.)")
    async def forex(self, interaction: discord.Interacti
