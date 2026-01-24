# bot.py

import discord
from discord.ext import commands
import logging
import os
import asyncio

    # Forcer la mise à jour de Render v1.1

# --- CONFIGURATION DE BASE ---
# ✅ NOUVELLES LIGNES (à ajouter au début de ton fichier)
import os
from dotenv import load_dotenv

load_dotenv() # Cette ligne est utile pour tester sur ton PC
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# --- DÉMARRAGE ASYNCHRONE ET CHARGEMENT DES COGS ---
async def main():
    # On utilise 'async with' pour une gestion propre de la connexion et déconnexion.
    async with bot:
        # On parcourt tous les fichiers dans le dossier 'cogs'.
        for filename in os.listdir('./cogs'):
            # On ne charge que les fichiers qui se terminent par .py
            if filename.endswith('.py'):
                try:
                    # On charge le cog en utilisant son nom de fichier (sans le .py)
                    await bot.load_extension(f'cogs.{filename[:-3]}')
                    logging.info(f"✅ Cog '{filename}' chargé avec succès.")
                except Exception as e:
                    logging.error(f"❌ Erreur lors du chargement du cog '{filename}': {e}")
        
        # On démarre le bot APRÈS avoir chargé les cogs.
        await bot.start(DISCORD_TOKEN)

# --- ÉVÉNEMENT DE DÉMARRAGE ---
@bot.event
async def on_ready():
    logging.info(f'--- {bot.user.name} est en ligne ! ---')
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synchronisé {len(synced)} commande(s).")
    except Exception as e:
        logging.error(f"Erreur de synchronisation : {e}")

# --- DÉMARRAGE DU BOT (LA PARTIE LA PLUS IMPORTANTE !) ---
# C'est cette section qui lance toute la machine.
# Si elle manque, le script ne fait rien.
if __name__ == "__main__":
    asyncio.run(main())